import json
import tempfile
import unittest
from pathlib import Path
from alignment.reflector import apply_proposal, build_messages, prepare_examples, propose
from src.validate import ROOT

TAX=json.loads((ROOT/'rubrics/taxonomy.json').read_text())
GOOD={'revised_definitions':{'payment_plan':'Device installment or financing agreement complaint; missing promotional credit alone does not qualify.'},'rules_to_add':['Missing promo credit does not by itself establish a payment plan issue.'],'rules_to_remove':[],'change_rationale':'Distinguish promotion from installment repayment.','risks':['May under-label mixed cases.']}

class ReflectorTests(unittest.TestCase):
 def test_valid_draft(self):
  changed=apply_proposal(TAX,GOOD)
  self.assertEqual(changed['status'],'PROPOSAL_ONLY_NOT_APPROVED')
  self.assertEqual(TAX['definitions']['payment_plan'],'Device installment/financing payment plan issue, not merely any billing complaint.')
 def test_cannot_remove_protected_rule(self):
  x=dict(GOOD,rules_to_remove=["Do not infer 'no' from missing mention; use unknown."])
  with self.assertRaises(ValueError):apply_proposal(TAX,x)
 def test_cannot_redefine_da(self):
  x=dict(GOOD,revised_definitions={'da':'Something invented'})
  with self.assertRaises(ValueError):apply_proposal(TAX,x)
 def test_prompt_has_benchmark_not_secrets(self):
  messages=build_messages(TAX,[{'error_type':'LABEL_MISMATCH'}],[{'case_id':'a'}])
  self.assertIn('anchor_examples',messages[1]['content'])
 def test_proposal_written_but_active_untouched(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp); meta=base/'meta.json';judge=base/'judge.json';out=base/'proposal.json'
   candidate=json.loads((ROOT/'data/candidate_labels.jsonl').read_text().splitlines()[0])
   cid=candidate['case_id']
   meta.write_text(json.dumps({'results':[{'case_id':cid,'status':'LABEL_MISMATCH'}], 'reflector_focus_set':[{'case_id':cid,'error_type':'LABEL_MISMATCH'}]}))
   judge.write_text(json.dumps({'results':[{'case_id':cid,'verdict':'PASS' if candidate['human_verdict']=='FAIL' else 'FAIL','reason':'Wrong boundary'}]}))
   original=(ROOT/'rubrics/taxonomy.json').read_bytes()
   report=propose(ROOT,meta,judge,out,client=lambda messages,model:GOOD)
   self.assertEqual(report['status'],'PENDING_HUMAN_REVIEW')
   self.assertTrue(out.with_suffix('.diff').exists())
   self.assertEqual((ROOT/'rubrics/taxonomy.json').read_bytes(),original)
if __name__=='__main__': unittest.main()
