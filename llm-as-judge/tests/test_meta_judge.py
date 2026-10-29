import json
import tempfile
import unittest
from pathlib import Path
from judges.meta_judge import assess, validate_alignment, audit_file, build_messages
from src.validate import ROOT, read_jsonl

class MetaJudgeTests(unittest.TestCase):
    def setUp(self):
        self.case=next(c for c in read_jsonl(ROOT/'data/seed_cases.jsonl') if c['id']=='INC-003')
        self.cand=next(c['candidate'] for c in read_jsonl(ROOT/'data/candidate_labels.jsonl') if c['case_id']=='INC-003')
        self.fake=lambda messages,model: {'reasoning_aligned':False,'human_failure_mode':'promo vs installment','judge_failure_mode':'length','explanation':'Different defects'}
    def test_fail_fail_calls_meta_model(self):
        result=assess(self.case,self.cand,'FAIL','This is promo','FAIL','Too short',client=self.fake)
        self.assertEqual(result['status'],'ASSESSED')
        self.assertFalse(result['reasoning_aligned'])
    def test_label_mismatch_skips_model(self):
        result=assess(self.case,self.cand,'FAIL','This is promo','PASS','Seems fine',client=lambda **kwargs:1/0)
        self.assertEqual(result['status'],'LABEL_MISMATCH')
    def test_pass_pass_skips_model(self):
        result=assess(self.case,self.cand,'PASS','Good','PASS','Good',client=lambda **kwargs:1/0)
        self.assertEqual(result['status'],'NOT_APPLICABLE')
    def test_reject_malformed_json(self):
        with self.assertRaises(ValueError): validate_alignment({'reasoning_aligned':'false'})
    def test_no_reference_verdict_in_meta_payload(self):
        messages=build_messages(self.case,self.cand,'wrong category','too short')
        self.assertIn('human_rationale',messages[1]['content'])
        self.assertNotIn('human_verdict',messages[1]['content'])
    def test_batch_focus_set(self):
        records={'results':[{'case_id':'INC-003','verdict':'FAIL','reason':'Too short'},
                            {'case_id':'INC-002','verdict':'PASS','reason':'fine'},
                            {'case_id':'INC-001','verdict':'PASS','reason':'fine'}]}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'scores.json';p.write_text(json.dumps(records))
            result=audit_file(p,client=self.fake)
        self.assertEqual(result['metrics']['agreed_fail_pairs'],1)
        self.assertEqual(len(result['reflector_focus_set']),2)
        self.assertEqual(result['metrics']['reasoning_agreement'],0)

if __name__=='__main__':unittest.main()
