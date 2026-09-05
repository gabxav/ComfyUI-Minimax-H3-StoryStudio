"""Exercise the bundled RAM store with real tensors in the ComfyUI environment."""
import gc
import importlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest
import weakref


@unittest.skipUnless(importlib.util.find_spec('comfy'), 'Run with the ComfyUI Python environment')
class AudioRefineRAMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        package = types.ModuleType('_story_audio_tests')
        package.__path__ = [str(Path(__file__).resolve().parents[1])]
        sys.modules[package.__name__] = package
        cls.cache = importlib.import_module(package.__name__ + '.vendor.audio_refine.frozen_cache')

    def test_pageable_copy_and_release(self):
        torch = self.torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        source = torch.arange(1024 * 1024, dtype=torch.float32, device=device).reshape(1024, 1024)
        store = self.cache._StoreRAM(1, None, 1024, 1024, device)
        store.put(0, source, None, source + 1, None)
        payload = store.k[0][0]
        self.assertEqual(payload.device.type, 'cpu')
        self.assertFalse(payload.is_pinned())
        self.assertEqual(payload.dtype, source.dtype)
        self.assertTrue(torch.equal(payload, source.cpu()))
        copy = weakref.ref(payload)
        self.assertNotEqual(payload.data_ptr(), source.data_ptr())
        del payload
        k, ks, v, vs = store.get(0, device)
        self.assertTrue(torch.equal(k, source))
        self.assertTrue(torch.equal(v, source + 1))
        self.assertIsNone(ks)
        self.assertIsNone(vs)
        del k, v
        store.free()
        gc.collect()
        self.assertIsNone(copy())

    def test_hidden_only_cache_and_optional_scales(self):
        torch = self.torch
        store = self.cache._StoreRAM(1, None, 4, 4, 'cpu', pair=False)
        source = torch.arange(16, dtype=torch.uint8).reshape(4, 4)
        scales = torch.ones((4, 1), dtype=torch.float16)
        store.put(0, source, scales, None, None)
        k, ks, v, vs = store.get(0, 'cpu')
        self.assertTrue(torch.equal(k, source))
        self.assertTrue(torch.equal(ks, scales))
        self.assertFalse(ks.is_pinned())
        self.assertIsNone(v)
        self.assertIsNone(vs)
        store.free()


if __name__ == '__main__':
    unittest.main()
