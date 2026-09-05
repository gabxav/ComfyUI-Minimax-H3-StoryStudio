"""Pure planning and fingerprinting; no ComfyUI or GPU imports."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path

VERSION = 1
FPS = 24
KINDS = {'images': 9, 'videos': 3, 'audios': 3}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def project_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', value):
        raise ValueError('O identificador da história deve usar apenas letras, números, _ e -.')
    return value


def media_path(value):
    value = str(value).replace('\\', '/')
    p = Path(value)
    if not value or p.is_absolute() or '..' in p.parts or '\x00' in value:
        raise ValueError('Referência inválida: use um arquivo dentro de input/.')
    return value


def media_list(value, kind):
    if not isinstance(value, list):
        raise ValueError(f'{kind}: lista de referências inválida.')
    out = []
    for item in value:
        item = {'path': item} if isinstance(item, str) else dict(item)
        item['path'] = media_path(item.get('path', ''))
        if kind in ('videos', 'audios'):
            item['start'] = float(item.get('start', 0))
            item['seconds'] = float(item.get('seconds', 15))
            if not math.isfinite(item['start']) or item['start'] < 0 or not math.isfinite(item['seconds']) or not 0.2 <= item['seconds'] <= 15:
                raise ValueError('Cada referência de vídeo/áudio deve selecionar até 15 segundos, com início >= 0.')
        # Video soundtracks are deliberately excluded: standalone Audio N is stable.
        out.append(item)
    return out


def parse_story(raw):
    d = json.loads(raw) if isinstance(raw, str) else copy.deepcopy(raw)
    if not isinstance(d, dict) or d.get('version', 1) != VERSION:
        raise ValueError('Formato da história não suportado.')
    d['version'] = VERSION
    d['project_id'] = project_id(d.get('project_id', ''))
    d['title'] = str(d.get('title', 'Minha história'))[:160]
    d['shared_prompt'] = str(d.get('shared_prompt', ''))
    d['context_frames'] = int(d.get('context_frames', 22))
    if d['context_frames'] not in (5, 22, 39, 56):
        raise ValueError('Contexto deve ser 5, 22, 39 ou 56 frames.')
    d['continue_audio'] = bool(d.get('continue_audio', True))
    d['seed'] = int(d.get('seed', 101967611122254))
    if not 0 <= d['seed'] < 2**53:
        raise ValueError('Seed fora do intervalo permitido (0 a 2^53-1).')
    d['ref_image_size'] = d.get('ref_image_size', 'max')
    if d['ref_image_size'] not in ('match', 'max'):
        raise ValueError('Tamanho de referência inválido.')
    shared = d.setdefault('references', {})
    for kind in KINDS:
        shared[kind] = media_list(shared.get(kind, []), kind)
    if not isinstance(d.get('scenes'), list) or not 1 <= len(d['scenes']) <= 100:
        raise ValueError('A história deve ter de 1 a 100 cenas.')
    for i, s in enumerate(d['scenes']):
        s['title'] = str(s.get('title', f'Cena {i+1}'))[:160]
        s['prompt'] = str(s.get('prompt', ''))
        if not s['prompt'].strip():
            raise ValueError(f'Escreva o prompt da cena {i+1}.')
        duration = float(s.get('seconds', 15))
        if not math.isfinite(duration) or not 1 <= duration <= 15:
            raise ValueError('A duração de cada cena deve estar entre 1 e 15 segundos.')
        s['seconds'] = duration
        s['continue_previous'] = bool(s.get('continue_previous', i > 0)) and i > 0
        refs = s.setdefault('references', {})
        for kind, limit in KINDS.items():
            refs[kind] = media_list(refs.get(kind, []), kind)
            if len(shared[kind]) + len(refs[kind]) > limit:
                raise ValueError(f'Cena {i+1}: limite de {limit} referências de {kind}, incluindo as comuns.')
    return d


def scene_media(story, index):
    return {k: story['references'][k] + story['scenes'][index]['references'][k] for k in KINDS}


def frame_budget(seconds, context=0):
    visible = round(seconds * FPS)
    total = visible + context
    sample = max(5, total) + (5 - max(5, total) % 17) % 17
    return {'visible_frames': visible, 'sample_frames': sample, 'trim_frames': context}


def recipe_hash(graph):
    graph = {k: {'class_type': v['class_type'], 'inputs': copy.deepcopy(v.get('inputs', {}))} for k,v in graph.items()}
    for node in graph.values():
        node.pop('_meta', None)
        if node.get('class_type') in ('XavierH3Story', 'XavierH3StoryStudio'):
            for key in ('story_json', 'scene_index', 'execution_token'):
                node.get('inputs', {}).pop(key, None)
    return digest(graph)


def chain_keys(story, recipe, asset_signature):
    base = {k: story[k] for k in ('version', 'seed', 'shared_prompt', 'context_frames', 'continue_audio', 'ref_image_size')}
    keys = []
    for i, scene in enumerate(story['scenes']):
        # Titles and project name do not change generation; prior outputs do.
        spec = {k: scene[k] for k in ('prompt', 'seconds', 'continue_previous')}
        refs = scene_media(story, i)
        assets = {k: [{**m, 'file': asset_signature(m['path'])} for m in refs[k]] for k in KINDS}
        keys.append(digest({'base': base, 'scene': spec, 'assets': assets, 'recipe': recipe,
                            'previous': keys[-1] if i and scene['continue_previous'] else None}))
    return keys


def valid_records(manifest, keys, exists):
    result = []
    for i, key in enumerate(keys):
        record = manifest.get('scenes', {}).get(str(i))
        if not record or record.get('key') != key or not all(exists(record.get(k, '')) for k in ('video', 'context')):
            result.append(None)
            continue
        parent = record.get('parent_revision')
        if parent is not None and (i == 0 or not result[i-1] or result[i-1]['revision'] != parent):
            result.append(None)
        else:
            result.append(record)
    return result
