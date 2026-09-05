import copy
import importlib.util
import json
from pathlib import Path
import unittest

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('story_plan',root/'plan.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class StoryPlanTests(unittest.TestCase):
    def setUp(self):
        self.story=p.parse_story((root/'tests/fixtures/story.json').read_text())
        self.sig=lambda _: [120,999]
    def test_exact_duration_and_overlap(self):
        for seconds in (1,5,15):
            for context in (0,5,22,39,56):
                b=p.frame_budget(seconds,context)
                self.assertEqual(b['sample_frames']%17,5)
                self.assertGreaterEqual(b['sample_frames']-context,round(seconds*24))
                self.assertEqual(b['visible_frames'],round(seconds*24))
    def test_edit_invalidates_only_current_and_descendants(self):
        a=p.chain_keys(self.story,'recipe',self.sig)
        self.story['scenes'][1]['prompt']+=' New action.'
        b=p.chain_keys(self.story,'recipe',self.sig)
        self.assertEqual(a[0],b[0]);self.assertNotEqual(a[1],b[1]);self.assertNotEqual(a[2],b[2])
    def test_refile_invalidates(self):
        self.assertNotEqual(p.chain_keys(self.story,'r',self.sig),p.chain_keys(self.story,'r',lambda _: [120,1000]))
    def test_title_does_not_invalidate(self):
        a=p.chain_keys(self.story,'r',self.sig)
        self.story['title']='Another';self.story['scenes'][0]['title']='Rename'
        self.assertEqual(a,p.chain_keys(self.story,'r',self.sig))
    def test_retake_invalidates_descendants_even_same_seed(self):
        keys=p.chain_keys(self.story,'r',self.sig)
        rows={str(i):{'key':key,'video':'x.mp4','context':'x.pt','revision':str(i),'parent_revision':str(i-1) if i else None} for i,key in enumerate(keys)}
        self.assertTrue(all(p.valid_records({'scenes':rows},keys,bool)))
        rows['0']['revision']='retake'
        valid=p.valid_records({'scenes':rows},keys,bool)
        self.assertIsNotNone(valid[0]);self.assertIsNone(valid[1]);self.assertIsNone(valid[2])
    def test_runtime_fields_not_recipe(self):
        a={'500':{'class_type':'XavierH3StoryStudio','inputs':{'width':512,'story_json':'a','scene_index':1,'execution_token':'a'}}}
        b=copy.deepcopy(a);b['500']['inputs'].update(story_json='b',scene_index=2,execution_token='b')
        self.assertEqual(p.recipe_hash(a),p.recipe_hash(b))
        b['500']['is_changed']=[float('nan')]
        self.assertEqual(p.recipe_hash(a),p.recipe_hash(b))
        b['500']['inputs']['width']=1024
        self.assertNotEqual(p.recipe_hash(a),p.recipe_hash(b))
    def test_paths_and_limits(self):
        for value in ('../secret','/etc/passwd','a/../../b','a\x00b'):
            with self.assertRaises(ValueError):p.media_path(value)
        self.story['references']['images']=[{'path':'a.png'}]*10
        with self.assertRaises(ValueError):p.parse_story(self.story)
    def test_restart_missing_checkpoint(self):
        keys=p.chain_keys(self.story,'r',self.sig)
        r={'key':keys[0],'video':'x.mp4','context':'missing','revision':'1','parent_revision':None}
        self.assertIsNone(p.valid_records({'scenes':{'0':r}},keys,lambda x:x!='missing')[0])

if __name__=='__main__':unittest.main()
