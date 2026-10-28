import unittest, json
from src.validate import ROOT, read_jsonl
from judges.taxonomy_judge import build_messages, validate_judgment, judge_one, evaluate

class JudgeTests(unittest.TestCase):
 def setUp(self):
  self.tax=json.loads((ROOT/'rubrics/taxonomy.json').read_text())
  self.case=read_jsonl(ROOT/'data/seed_cases.jsonl')[0]
  self.cand=read_jsonl(ROOT/'data/candidate_labels.jsonl')[0]['candidate']
 def test_no_label_leakage(self):
  s=json.dumps(build_messages(self.case,self.cand,self.tax))
  self.assertNotIn('human_rationale',s)
  self.assertNotIn('human_verdict',s)
  self.assertNotIn('reference',json.loads(build_messages(self.case,self.cand,self.tax)[1]['content']))
 def test_valid_judgment(self):
  j={"verdict":"PASS","reason":"Activation failure","evidence":"ACT-500","suggested_primary":None}
  self.assertEqual(validate_judgment(j,self.tax)['verdict'],'PASS')
 def test_invalid_judgment(self):
  with self.assertRaises(ValueError):validate_judgment({"verdict":"MAYBE"},self.tax)
 def test_mock_model(self):
  def fake(messages,model):return {"verdict":"PASS","reason":"Explicit activation","evidence":"ACT-500","suggested_primary":None}
  out=judge_one(self.case,self.cand,self.tax,client=fake)
  self.assertEqual(out['criterion'],'taxonomy_correctness')
 def test_eval_errors_not_counted_as_agreement(self):
  def down(messages,model):raise RuntimeError('offline')
  outs,metrics=evaluate(client=down)
  self.assertEqual(metrics['decided'],0)
  self.assertIsNone(metrics['label_agreement'])
  self.assertEqual(metrics['errors'],len(outs))
if __name__=='__main__':unittest.main()
