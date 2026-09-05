import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import uuid

from .plan import chain_keys, media_path, project_id, valid_records


def output_root():
    import folder_paths
    return Path(folder_paths.get_output_directory()).resolve()


def project_root(pid):
    root = output_root() / 'story_director' / project_id(pid)
    root.mkdir(parents=True, exist_ok=True)
    return root


def input_file(name):
    import folder_paths
    root = Path(folder_paths.get_input_directory()).resolve()
    p = (root / media_path(name)).resolve()
    if not p.is_relative_to(root) or not p.is_file():
        raise ValueError(f'Referência não encontrada em input/: {name}')
    return p


def output_file(name):
    root = output_root()
    p = (root / media_path(name)).resolve()
    if not p.is_relative_to(root):
        raise ValueError('Caminho de saída inválido.')
    return p


def relative(path):
    return str(Path(path).relative_to(output_root()))


def signature(name):
    p = input_file(name)
    s = p.stat()
    return [s.st_size, s.st_mtime_ns]


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('w') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_manifest(pid):
    p = project_root(pid) / 'manifest.json'
    return json.loads(p.read_text()) if p.exists() else {'version': 1, 'scenes': {}}


def records_for(story, recipe):
    keys = chain_keys(story, recipe, signature)
    manifest = read_manifest(story['project_id'])
    def exists(name):
        try:
            return bool(name) and output_file(name).is_file()
        except ValueError:
            return False
    return keys, valid_records(manifest, keys, exists)


def motion_module():
    # Reuse the already imported Director helper, including its patch state.
    suffix = '/ComfyUI_MiniMaxH3_Director/director/h3_motion_context.py'
    for module in list(sys.modules.values()):
        if str(getattr(module, '__file__', '')).replace('\\', '/').endswith(suffix):
            return module
    import folder_paths
    for base in folder_paths.get_folder_paths('custom_nodes'):
        d = Path(base) / 'ComfyUI_MiniMaxH3_Director' / 'director'
        if (d / 'h3_motion_context.py').is_file():
            package = types.ModuleType('_xavier_story_motion')
            package.__path__ = [str(d)]
            sys.modules[package.__name__] = package
            return importlib.import_module(package.__name__ + '.h3_motion_context')
    raise RuntimeError('Instale o ComfyUI_MiniMaxH3_Director (AIMixer): ele fornece o contexto temporal H3.')


def load_audio(item):
    import numpy as np
    import torch
    path = input_file(item['path'])
    result = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', str(item['start']), '-i', str(path),
                             '-t', str(item['seconds']), '-vn', '-ac', '2', '-ar', '32000', '-f', 'f32le', 'pipe:1'],
                            capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError(f'Não foi possível ler o áudio {item["path"]}: {result.stderr.decode(errors="replace")[-500:]}')
    data = np.frombuffer(result.stdout, dtype=np.float32).copy()
    if data.size < 12800:
        raise ValueError(f'Referência de áudio muito curta ou vazia: {item["path"]}')
    return {'waveform': torch.from_numpy(data.reshape(-1, 2).T).unsqueeze(0), 'sample_rate': 32000}


def load_video(item):
    import av
    import numpy as np
    import torch
    images = []
    start, seconds = item['start'], item['seconds']
    target = start
    with av.open(str(input_file(item['path']))) as container:
        if not container.streams.video:
            raise ValueError(f'Arquivo sem vídeo: {item["path"]}')
        stream = container.streams.video[0]
        origin = float((stream.start_time or 0) * stream.time_base)
        if start:
            container.seek(int((start + origin) / float(stream.time_base)), stream=stream, backward=True)
        for frame in container.decode(stream):
            t = float(frame.time or 0) - origin
            if t + 1e-4 < target:
                continue
            if target >= start + seconds - 1e-4:
                break
            scale = min(1, 1024 / max(frame.width, frame.height))
            w, h = max(32, round(frame.width*scale/32)*32), max(32, round(frame.height*scale/32)*32)
            rgb = frame.reformat(width=w, height=h, format='rgb24').to_ndarray()
            while target <= t + 1e-4 and target < start + seconds - 1e-4:
                images.append(rgb)
                target += 1/24
        if len(images) < 5:
            raise ValueError(f'Referência de vídeo muito curta no intervalo escolhido: {item["path"]}')
    return torch.from_numpy(np.stack(images)).float().div_(255)


def load_references(refs):
    import nodes
    images = {f'ref_image_{i}': nodes.LoadImage().load_image(m['path'])[0] for i, m in enumerate(refs['images'])}
    videos = {f'ref_video_{i}': load_video(m) for i, m in enumerate(refs['videos'])}
    audios = {f'ref_audio_{i}': load_audio(m) for i, m in enumerate(refs['audios'])}
    return images, videos, audios


def assemble(pid, records):
    root = project_root(pid)
    if not records or any(r is None for r in records):
        raise ValueError('Gere todas as cenas atuais antes de montar o filme.')
    final = root / f'filme_{uuid.uuid4().hex[:12]}.mp4'
    cmd = ['ffmpeg', '-v', 'error', '-nostdin']
    filters, labels = [], []
    for i, record in enumerate(records):
        cmd += ['-i', str(output_file(record['video']))]
        frames = round(record['seconds'] * 24)
        samples = round(record['seconds'] * 32000)
        # Decode each segment separately: discard AAC padding and reset clocks.
        # Concat demuxer timestamps accumulate codec padding and can lose frames.
        filters.append(f'[{i}:v:0]trim=end_frame={frames},setpts=N/(24*TB)[v{i}]')
        filters.append(f'[{i}:a:0]aresample=32000,atrim=end_sample={samples},asetpts=N/SR/TB[a{i}]')
        labels.extend([f'[v{i}]', f'[a{i}]'])
    filters.append(''.join(labels) + f'concat=n={len(records)}:v=1:a=1[outv][outa]')
    cmd += ['-filter_complex', ';'.join(filters), '-map', '[outv]', '-map', '[outa]',
            '-r', '24', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-y', str(final)]
    result = subprocess.run(cmd, capture_output=True, timeout=1800)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-1500:])
    return relative(final)
