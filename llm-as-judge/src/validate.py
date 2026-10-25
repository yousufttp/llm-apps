"""Phase I benchmark checks. These are structural checks, NOT an LLM judge."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_jsonl(path: Path):
    result = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if line.strip():
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path.name}:{number}: invalid JSON: {exc}') from exc
    return result

def check_label(label, taxonomy, context):
    problems = []
    if label.get('primary') not in taxonomy['primary_domains']:
        problems.append(f'{context}: unknown primary: {label.get("primary")}')
    attrs = label.get('attributes', {})
    if set(attrs) != set(taxonomy['attributes']):
        problems.append(f'{context}: missing/extra attributes')
    for name, value in attrs.items():
        if value not in taxonomy['attribute_values']:
            problems.append(f'{context}: invalid {name}={value}')
    return problems

def validate(root=ROOT):
    taxonomy = json.loads((root/'rubrics'/'taxonomy.json').read_text(encoding='utf-8'))
    cases = read_jsonl(root/'data'/'seed_cases.jsonl')
    candidates = read_jsonl(root/'data'/'candidate_labels.jsonl')
    errors, ids, candidate_ids = [], set(), set()
    for case in cases:
        cid = case.get('id')
        if cid in ids: errors.append(f'duplicate case ID: {cid}')
        ids.add(cid)
        for field in ('id','source','text','reference','human_rationale','failure_mode','split','needs_review'):
            if field not in case: errors.append(f'{cid}: missing {field}')
        if case.get('split') not in ('train','validation','test'):
            errors.append(f'{cid}: invalid split')
        if not case.get('human_rationale','').strip(): errors.append(f'{cid}: missing rationale')
        errors.extend(check_label(case.get('reference', {}),taxonomy,cid))
    for cand in candidates:
        cid = cand.get('case_id')
        if cid not in ids: errors.append(f'{cid}: candidate has no reference case')
        if cid in candidate_ids: errors.append(f'{cid}: duplicate candidate')
        candidate_ids.add(cid)
        errors.extend(check_label(cand.get('candidate',{}), taxonomy, f'{cid} candidate'))
        if cand.get('human_verdict') not in ('PASS','FAIL'):
            errors.append(f'{cid}: verdict must be PASS/FAIL')
        if not cand.get('human_rationale','').strip():
            errors.append(f'{cid}: missing verdict rationale')
    return cases, candidates, errors

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--strict',action='store_true',help='Exit nonzero on errors')
    args=parser.parse_args()
    cases,candidates,errors=validate()
    from collections import Counter
    print(f'Cases: {len(cases)} | Candidate assessments: {len(candidates)}')
    print('Primary:',dict(sorted(Counter(x['reference']['primary'] for x in cases).items())))
    print('Splits:',dict(sorted(Counter(x['split'] for x in cases).items())))
    print('Human-review flags:',sum(x['needs_review'] for x in cases))
    if errors:
        for error in errors: print('ERROR:',error)
    else: print('Structural validation PASSED')
    if errors and args.strict: raise SystemExit(1)
if __name__=='__main__': main()
