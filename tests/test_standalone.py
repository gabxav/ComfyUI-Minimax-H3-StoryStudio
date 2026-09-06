"""Verify bundled continuity and graph expansion without external custom nodes."""
import importlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('comfy'), 'Run with the ComfyUI Python environment')
class StandaloneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        import comfy.ldm.minimax.model as mm
        import comfy.model_base as model_base
        cls.torch, cls.mm, cls.model_base = torch, mm, model_base
        cls.original_layout = mm.PackedLayout.__init__
        cls.original_payload = model_base.MiniMaxH3.extra_conds
        cls.root = Path(__file__).resolve().parents[1]
        cls.package = '_story_standalone_tests'
        package = types.ModuleType(cls.package)
        package.__path__ = [str(cls.root)]
        sys.modules[cls.package] = package
        cls.runtime = importlib.import_module(cls.package + '.runtime')
        cls.nodes = importlib.import_module(cls.package + '.nodes')

    @classmethod
    def tearDownClass(cls):
        # Runtime patches are process-global; restore the test process afterward.
        cls.mm.PackedLayout.__init__ = cls.original_layout
        cls.model_base.MiniMaxH3.extra_conds = cls.original_payload
        for name in list(sys.modules):
            if name == cls.package or name.startswith(cls.package + '.'):
                del sys.modules[name]

    def test_bundled_context_without_custom_node_discovery(self):
        import folder_paths
        with patch.object(folder_paths, 'get_folder_paths', side_effect=AssertionError('External lookup')):
            motion = self.runtime.motion_module()
        self.assertEqual(Path(motion.__file__).resolve().parent, self.root / 'vendor/director')
        torch = self.torch

        class VideoVAE:
            def encode(self, frames):
                steps = motion.steps_for_frames(frames.shape[0])
                return torch.ones(1, 16, steps, 2, 2)

        class AudioVAE:
            audio_sample_rate = 32000

            def encode(self, waveform):
                steps = round(waveform.shape[1] / self.audio_sample_rate * 40)
                return torch.ones(1, 64, 2, steps)

        reference = {'kind': 'image', 'latent': torch.ones(1, 16, 1, 2, 2)}
        positive = [[torch.zeros(1, 2, 8), {'minimax_refs': [reference]}]]
        latent = {'samples': [torch.zeros(1, 16, motion.steps_for_frames(56), 2, 2)]}
        audio = {'waveform': torch.ones(1, 2, round(22 / 24 * 32000)), 'sample_rate': 32000}
        out, trim, previous_trim = motion.apply_motion_context(
            positive, latent, vae=VideoVAE(), context_length=22,
            context_frames=torch.ones(22, 32, 32, 3), context_audio=audio,
            audio_vae=AudioVAE(), audio_context_length=22, keep_existing_keyframes=False,
        )
        self.assertEqual((trim, previous_trim), (22, 0))
        meta = out[0][1]
        self.assertEqual(len(meta['minimax_keyframes']), 7)
        self.assertEqual([k['director_context_index'] for k in meta['minimax_keyframes']],
                         [0, 1, 5, 9, 13, 17, 18])
        self.assertIs(meta['minimax_refs'][0], reference)
        self.assertEqual(meta['minimax_refs'][1]['kind'], 'audio')
        self.assertEqual(meta['minimax_refs'][1]['ref_audio_t'], 37)
        self.assertEqual(len(positive[0][1]['minimax_refs']), 1)

    def test_context_patch_is_idempotent_across_two_imports(self):
        first = importlib.import_module(self.package + '.vendor.director.h3_context_patches')
        first.ensure_layout_patch()
        first.ensure_payload_patch()
        layout, payload = self.mm.PackedLayout.__init__, self.model_base.MiniMaxH3.extra_conds
        spec = importlib.util.spec_from_file_location('_story_second_context', first.__file__)
        second = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(second)
        self.assertTrue(second.ensure_layout_patch())
        self.assertTrue(second.ensure_payload_patch())
        self.assertIs(self.mm.PackedLayout.__init__, layout)
        self.assertIs(self.model_base.MiniMaxH3.extra_conds, payload)

    def test_graph_uses_native_attention_without_kjnodes(self):
        self.assertEqual(self._sage_nodes(available=False, mode='auto'), 0)

    def test_graph_keeps_optional_sage_attention(self):
        self.assertEqual(self._sage_nodes(available=True, mode='auto'), 2)
        self.assertEqual(self._sage_nodes(available=True, mode='disabled'), 0)

    def _sage_nodes(self, available, mode):
        import nodes
        mappings = {'StoryStudioH3AudioRefineSampler': object(),
                    'StoryStudioH3FrozenVideoCache': object()}
        if available:
            mappings['PathchSageAttentionKJ'] = object()
        with patch.dict(nodes.NODE_CLASS_MAPPINGS, mappings, clear=True):
            out = self.nodes.XavierH3StoryStudio().generate(
                ref2va_model='ref2va.safetensors', fl2va_model='fl2va.safetensors',
                clip_name='clip.safetensors', video_vae_name='video.safetensors',
                audio_vae_name='audio.safetensors', turbo_lora='none', width=512, height=512,
                steps=8, sampler_name='euler', scheduler='simple', attention=mode,
                audio_refine=True, audio_steps=6, audio_denoise=0.5, audio_cache=True,
                story_json=(self.root / 'tests/fixtures/story.json').read_text(), scene_index=1,
            )
        classes = [node['class_type'] for node in out['expand'].values()]
        self.assertIn('StoryStudioH3AudioRefineSampler', classes)
        self.assertIn('StoryStudioH3FrozenVideoCache', classes)
        return classes.count('PathchSageAttentionKJ')


if __name__ == '__main__':
    unittest.main()
