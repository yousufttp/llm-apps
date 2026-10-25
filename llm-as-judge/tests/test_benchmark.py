import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.validate import validate, check_label
import json
ROOT=Path(__file__).resolve().parents[1]
class BenchmarkTests(unittest.TestCase):
    def test_valid_data(self):
        cases,candidates,errors=validate()
        self.assertFalse(errors,errors)
        self.assertGreaterEqual(len(cases),10)
        self.assertGreaterEqual(len(candidates),5)
    def test_split_isolation(self):
        cases,_,_=validate()
        ids=[c['id'] for c in cases]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual({'train','validation','test'},set(c['split'] for c in cases))
    def test_invalid_primary_rejected(self):
        t=json.loads((ROOT/'rubrics'/'taxonomy.json').read_text())
        a={k:'unknown' for k in t['attributes']}
        self.assertTrue(check_label({'primary':'made_up','attributes':a},t,'case'))
    def test_fail_rationales(self):
        _,candidates,_=validate()
        self.assertTrue(all(c['human_rationale'].strip() for c in candidates if c['human_verdict']=='FAIL'))
if __name__=='__main__': unittest.main()
