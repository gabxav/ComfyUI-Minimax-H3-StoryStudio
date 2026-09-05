"""Regression: AAC padding must not add time or drop frames across joins."""
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

pkg = types.ModuleType('_story_assembly_tests')
pkg.__path__ = [str(Path(__file__).resolve().parents[1])]
sys.modules[pkg.__name__] = pkg
runtime = importlib.import_module(pkg.__name__ + '.runtime')


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class AssemblyTests(unittest.TestCase):
    def test_aac_padding_does_not_accumulate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=64x64:r=24:d=1',
                            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=32000:duration=1',
                            '-c:v', 'libx264', '-c:a', 'aac', '-y', str(root/'clip.mp4')], check=True)
            before = runtime.output_root
            runtime.output_root = lambda: root
            try:
                path = root / runtime.assemble('test', [{'video':'clip.mp4','seconds':1}]*3)
            finally:
                runtime.output_root = before
            data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                    'stream=codec_type,duration,nb_frames', '-show_entries', 'format=duration', '-of', 'json', str(path)]))
            video, audio = data['streams']
            self.assertEqual(video['nb_frames'], '72')
            self.assertEqual(video['duration'], '3.000000')
            self.assertEqual(audio['duration'], '3.000000')
            self.assertEqual(data['format']['duration'], '3.000000')

if __name__ == '__main__': unittest.main()
