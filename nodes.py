import json
import time
import uuid

from .plan import FPS, frame_budget, parse_story, recipe_hash, scene_media
from .runtime import (atomic_json, load_references, motion_module, output_file, project_root,
                      read_manifest, records_for, relative)


class XavierH3Story:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'clip': ('CLIP',), 'vae': ('VAE',), 'audio_vae': ('VAE',),
            'width': ('INT', {'default': 1024, 'min': 32, 'max': 4096, 'step': 32}),
            'height': ('INT', {'default': 1024, 'min': 32, 'max': 4096, 'step': 32}),
            'story_json': ('STRING', {'default': '', 'multiline': True}),
            'scene_index': ('INT', {'default': 1, 'min': 1, 'max': 100}),
            'execution_token': ('STRING', {'default': ''}),
        }, 'optional': {'reference_image': ('IMAGE',), 'reference_video': ('IMAGE',), 'reference_audio': ('AUDIO',), 'recipe_fingerprint': ('STRING', {'default': ''})}, 'hidden': {'prompt': 'PROMPT', 'unique_id': 'UNIQUE_ID'}}

    RETURN_TYPES = ('CONDITIONING', 'LATENT', 'INT', 'XAVIER_STORY_SCENE')
    RETURN_NAMES = ('positive', 'latent', 'seed', 'scene')
    FUNCTION = 'prepare'
    CATEGORY = 'MiniMax H3/StoryStudio'
    DESCRIPTION = 'Prompts, referências e continuação por cena. Abra o editor para organizar a história.'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def prepare(self, clip, vae, audio_vae, width, height, story_json, scene_index,
                execution_token='', prompt=None, unique_id=None, reference_image=None, reference_video=None, reference_audio=None, recipe_fingerprint=''):
        import torch
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
        story = parse_story(story_json)
        index = int(scene_index)-1
        if not 0 <= index < len(story['scenes']):
            raise ValueError('Selecione uma cena existente.')
        recipe = recipe_fingerprint or recipe_hash(prompt or {})
        keys, records = records_for(story, recipe)
        scene = story['scenes'][index]
        previous = records[index-1] if index else None
        context_n = story['context_frames'] if scene['continue_previous'] else 0
        if context_n and previous is None:
            raise ValueError(f'Gere novamente a cena {index} antes de continuar a cena {index+1}. O contexto está ausente ou desatualizado.')
        budget = frame_budget(scene['seconds'], context_n)
        refs = scene_media(story, index)
        images, videos, audios = load_references(refs)
        for mapping, prefix, value, limit in [(images, 'ref_image_', reference_image, 9), (videos, 'ref_video_', reference_video, 3), (audios, 'ref_audio_', reference_audio, 3)]:
            if value is not None:
                if len(mapping) >= limit:
                    raise ValueError('As referências conectadas excedem o limite de mídia do H3.')
                mapping[prefix+str(len(mapping))] = value
        text = '\n\n'.join(t.strip() for t in (story['shared_prompt'], scene['prompt']) if t.strip())
        out = MiniMaxH3ReferenceToVideo.execute(clip, vae, audio_vae, text, width, height,
                budget['sample_frames'], story['ref_image_size'], images, videos, None, audios)
        positive, latent = out.result
        if context_n:
            checkpoint = torch.load(output_file(previous['context']), map_location='cpu', weights_only=True)
            frames = checkpoint['frames'].float()
            audio = {'waveform': checkpoint['audio'].float(), 'sample_rate': checkpoint['sample_rate']}
            positive, trim, previous_trim = motion_module().apply_motion_context(
                positive, latent, vae=vae, context_length=context_n,
                context_frames=frames, context_audio=audio, audio_vae=audio_vae,
                continue_audio=story['continue_audio'], audio_context_length=context_n,
                keep_existing_keyframes=False)
            if trim != context_n or previous_trim:
                raise RuntimeError('O contexto não corresponde ao final exportado; geração interrompida para evitar uma emenda incorreta.')
        metadata = {'project_id': story['project_id'], 'title': story['title'], 'index': index,
                    'scene_title': scene['title'], 'key': keys[index], 'recipe': recipe,
                    'parent_revision': previous['revision'] if context_n else None,
                    'context_frames': story['context_frames'], 'seed': (story['seed']+index) % (2**53),
                    'execution_token': execution_token, 'story': story, **budget}
        return positive, latent, metadata['seed'], metadata


class XavierH3StoryOutput:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'images': ('IMAGE',), 'audio': ('AUDIO',), 'scene': ('XAVIER_STORY_SCENE',)},
                'hidden': {'prompt': 'PROMPT', 'extra_pnginfo': 'EXTRA_PNGINFO'}}

    RETURN_TYPES = ('IMAGE', 'AUDIO', 'STRING')
    RETURN_NAMES = ('images', 'audio', 'saved_video')
    FUNCTION = 'save'
    OUTPUT_NODE = True
    CATEGORY = 'MiniMax H3/StoryStudio'
    DESCRIPTION = 'Salva o trecho final e o contexto para a cena seguinte, depois do refinamento de áudio.'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def save(self, images, audio, scene, prompt=None, extra_pnginfo=None):
        import torch
        from comfy_extras.nodes_video import CreateVideo
        from comfy_api.latest import Types
        start, count = scene['trim_frames'], scene['visible_frames']
        if images.shape[0] < start+count:
            raise ValueError(f'O decoder entregou {images.shape[0]} frames; são necessários {start+count}.')
        images = images[start:start+count].contiguous()
        sr = int(audio['sample_rate'])
        a0, a1 = round(start/FPS*sr), round((start+count)/FPS*sr)
        if audio['waveform'].shape[-1] < a1:
            raise ValueError('O áudio refinado ficou menor que a duração da cena. Não foi aplicado silêncio artificial.')
        audio = {'waveform': audio['waveform'][..., a0:a1].contiguous(), 'sample_rate': sr}
        if not torch.isfinite(images).all() or not torch.isfinite(audio['waveform']).all():
            raise ValueError('A geração contém valores não finitos.')
        pid, index = scene['project_id'], scene['index']
        root = project_root(pid)
        revision = uuid.uuid4().hex[:12]
        prefix = f'cena_{index+1:03d}_{revision}'
        file, ctx = root / f'{prefix}.mp4', root / f'{prefix}.pt'
        video = CreateVideo.execute(images, FPS, audio, 8, 'sRGB').result[0]
        video.save_to(str(file), format=Types.VideoContainer('mp4'), codec=Types.VideoCodec('h264'),
                      metadata={'workflow': (extra_pnginfo or {}).get('workflow', {}), 'story_scene': scene}, crf=18)
        n = min(scene['context_frames'], count)
        checkpoint = {'frames': images[-n:].detach().cpu().half().clone(),
                      'audio': audio['waveform'][..., -round(n/FPS*sr):].detach().cpu().clone(),
                      'sample_rate': sr}
        tmp = ctx.with_suffix('.tmp')
        torch.save(checkpoint, tmp)
        tmp.replace(ctx)
        manifest = read_manifest(pid)
        record = {k: scene[k] for k in ('key', 'parent_revision', 'seed', 'scene_title', 'visible_frames',
                                       'sample_frames', 'trim_frames', 'execution_token')}
        record.update({'revision': revision, 'video': relative(file), 'context': relative(ctx),
                       'seconds': count/FPS, 'width': images.shape[2], 'height': images.shape[1], 'created_at': time.time()})
        old = manifest['scenes'].get(str(index))
        if old:
            manifest.setdefault('previous_takes', []).append(old)
        manifest['scenes'][str(index)] = record
        manifest.update({'title': scene['title'], 'story': scene['story'], 'recipe': scene['recipe'], 'updated_at': time.time()})
        manifest.pop('assembled', None)
        atomic_json(root/'manifest.json', manifest)
        ui = {'videos': [{'filename': file.name, 'subfolder': relative(root), 'type': 'output', 'format': 'video/mp4'}],
              'text': [f'Cena {index+1}: {count/FPS:.3f}s · {relative(file)}']}
        return {'ui': ui, 'result': (images, audio, relative(file))}


class XavierH3StoryStudio:
    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths
        import comfy.samplers
        models = folder_paths.get_filename_list('diffusion_models')
        clips = folder_paths.get_filename_list('text_encoders')
        vaes = folder_paths.get_filename_list('vae')
        loras = ['none'] + folder_paths.get_filename_list('loras')
        def choice(values, preferred):
            return (values, {'default': next((v for v in values if preferred in v), values[0] if values else '')})
        return {'required': {
            'ref2va_model': choice(models, 'minimax_h3_ref2va_pruned_int8_convrot'),
            'fl2va_model': choice(models, 'minimax_h3_fl2va_pruned_int8_convrot'),
            'clip_name': choice(clips, 'qwen3vl_32b_minimax_h3_nvfp4_awq'),
            'video_vae_name': choice(vaes, 'minimax_h3_video_vae_fp16'),
            'audio_vae_name': choice(vaes, 'minimax_h3_audio_vae_fp32'),
            'turbo_lora': choice(loras, 'minimax_h3_ref2v_turbo_8step_v1.0_768p'),
            'width': ('INT', {'default': 1024, 'min': 128, 'max': 2048, 'step': 32}),
            'height': ('INT', {'default': 1024, 'min': 128, 'max': 2048, 'step': 32}),
            'steps': ('INT', {'default': 8, 'min': 1, 'max': 100}),
            'sampler_name': (comfy.samplers.KSampler.SAMPLERS, {'default': 'euler'}),
            'scheduler': (comfy.samplers.KSampler.SCHEDULERS, {'default': 'simple'}),
            'attention': (['auto', 'disabled'], {'default': 'auto'}),
            'audio_refine': ('BOOLEAN', {'default': True}),
            'audio_steps': ('INT', {'default': 6, 'min': 1, 'max': 100}),
            'audio_denoise': ('FLOAT', {'default': 0.5, 'min': 0.01, 'max': 1, 'step': 0.01}),
            'audio_cache': ('BOOLEAN', {'default': True}),
            'story_json': ('STRING', {'default': '', 'multiline': True}),
            'scene_index': ('INT', {'default': 1, 'min': 1, 'max': 100}),
            'execution_token': ('STRING', {'default': ''}),
        }, 'hidden': {'unique_id': 'UNIQUE_ID', 'prompt': 'PROMPT'}}

    RETURN_TYPES = ('IMAGE', 'AUDIO', 'STRING')
    RETURN_NAMES = ('images', 'audio', 'saved_video')
    FUNCTION = 'generate'
    OUTPUT_NODE = True
    CATEGORY = 'MiniMax H3/StoryStudio'
    DESCRIPTION = 'Studio completo: modelos, referências, cenas, contexto temporal e AudioRefine opcional. REF2VA gera o vídeo; FL2VA refina o áudio sem Turbo LoRA.'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def generate(self, ref2va_model, fl2va_model, clip_name, video_vae_name, audio_vae_name,
                 turbo_lora, width, height, steps, sampler_name, scheduler, attention,
                 audio_refine, audio_steps, audio_denoise, audio_cache, story_json, scene_index,
                 execution_token='', unique_id=None, prompt=None):
        import nodes
        from comfy_execution.graph_utils import GraphBuilder
        parse_story(story_json)
        for needed in (['StoryStudioH3AudioRefineSampler'] if audio_refine else []) + (['StoryStudioH3FrozenVideoCache'] if audio_refine and audio_cache else []) + (['PathchSageAttentionKJ'] if attention=='auto' else []):
            if needed not in nodes.NODE_CLASS_MAPPINGS:
                raise RuntimeError(f'Node necessário não instalado: {needed}')
        g = GraphBuilder()
        clip = g.node('CLIPLoader', clip_name=clip_name, type='minimax', device='default')
        vae = g.node('VAELoader', vae_name=video_vae_name)
        avae = g.node('VAELoader', vae_name=audio_vae_name)
        plan = g.node('XavierH3Story', clip=clip.out(0), vae=vae.out(0), audio_vae=avae.out(0),
                      width=width, height=height, story_json=story_json, scene_index=scene_index, execution_token=execution_token, recipe_fingerprint=recipe_hash(prompt or {}))
        model = g.node('UNETLoader', unet_name=ref2va_model, weight_dtype='default')
        if turbo_lora != 'none':
            model = g.node('LoraLoaderModelOnly', model=model.out(0), lora_name=turbo_lora, strength_model=1.0)
        model = g.node('MiniMaxH3SigmaShift', model=model.out(0), shift_video=12.0, shift_audio=3.0)
        if attention == 'auto':
            model = g.node('PathchSageAttentionKJ', model=model.out(0), sage_attention='auto', allow_compile=False)
        noise = g.node('RandomNoise', noise_seed=plan.out(2))
        guider = g.node('BasicGuider', model=model.out(0), conditioning=plan.out(0))
        sampler = g.node('KSamplerSelect', sampler_name=sampler_name)
        sigmas = g.node('BasicScheduler', model=model.out(0), scheduler=scheduler, steps=steps, denoise=1.0)
        sampled = g.node('SamplerCustomAdvanced', noise=noise.out(0), guider=guider.out(0), sampler=sampler.out(0), sigmas=sigmas.out(0), latent_image=plan.out(1))
        if audio_refine:
            refined_model = g.node('UNETLoader', unet_name=fl2va_model, weight_dtype='default')
            refined_model = g.node('MiniMaxH3SigmaShift', model=refined_model.out(0), shift_video=12.0, shift_audio=3.0)
            if attention == 'auto':
                refined_model = g.node('PathchSageAttentionKJ', model=refined_model.out(0), sage_attention='auto', allow_compile=False)
            if audio_cache:
                refined_model = g.node('StoryStudioH3FrozenVideoCache', model=refined_model.out(0), enabled=True, cache_contents='hidden',
                                       backend='auto', precision='int4', refresh_interval=0, verbose=False, allow_disk=False, vram_margin_gb=1.0)
            sampled = g.node('StoryStudioH3AudioRefineSampler', model=refined_model.out(0), positive=plan.out(0), negative=plan.out(0),
                             latent=sampled.out(0), seed=plan.out(2), steps=audio_steps, cfg=1.0, sampler_name=sampler_name,
                             scheduler=scheduler, audio_denoise=audio_denoise, video_denoise=0.0)
        images = g.node('VAEDecode', samples=sampled.out(0), vae=vae.out(0))
        audio = g.node('VAEDecodeAudio', samples=sampled.out(0), vae=avae.out(0))
        result = g.node('XavierH3StoryOutput', images=images.out(0), audio=audio.out(0), scene=plan.out(3))
        if unique_id:
            for n in g.nodes.values():
                n.set_override_display_id(unique_id)
        return {'result': (result.out(0), result.out(1), result.out(2)), 'expand': g.finalize()}
