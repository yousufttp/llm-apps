# LLM as Judge

**Netflix-inspired, human-aligned LLM evaluation architecture — Phase I: Birth**

This project builds a **hierarchical telecom incident segmentation system** and a separate **LLM-as-a-Judge evaluation lifecycle**. The project's name is **LLM as Judge**; Netflix is acknowledged as the inspiration, not as the owner or source of this implementation.

> Status: Phase I benchmark scaffolding is implemented. All examples are synthetic, draft annotations; they have **not** been validated by independent subject matter experts. An LLM judge, rubric tuning, production gating, and monitoring are **not yet implemented**.

## Architecture inspiration and boundaries

Source: [Netflix Technology Blog, *The Lifecycle of LLM-as-a-Judge: Building, Aligning, and Monitoring at Scale* (September 4, 2026)](https://netflixtechblog.com/the-lifecycle-of-llm-as-a-judge-building-aligning-and-monitoring-at-scale-c95bd8283508).

Netflix describes a four-stage lifecycle for evaluating **LLM-generated recommendation explanations**, not telecom incidents. We reproduce the **published component responsibilities and lifecycle**, but our incident domain, label taxonomy, schemas, file structure, prompts, and proposed human-review policy are our own adaptations. This project is not Netflix source code and does not claim to reproduce undisclosed infrastructure.

## End-to-end system overview

```text
                OFFLINE: human-anchored evaluator development
  Domain experts -> labeling guidelines + per-criterion rubrics
               -> adversarial / borderline / sampled examples
               -> human labels + rationale -> benchmark
                         |                ^
                         v                | new audited cases
                [criterion-specific Judge(s)]
                         | labels + rationales
                         v
       compare verdicts to humans and compare FAIL reasons
                [Meta-Judge: reasoning agreement]
                         |
                         v
        focus set: label errors + same-FAIL/wrong-reason
                         |
                         v
            [Reflector: propose rubric revision]
                         |
                         v
       validation thresholds + human approval + versioning
                         |
                         v
                APPROVED JUDGE RUBRICS
                         |
                         v
                  ONLINE: classification
   Incoming incident -> Generator: hierarchical segmentation
                         |
                         v
               Judges: taxonomy / evidence / completeness
                    /                     \
          all PASS                        any FAIL
             |                               |
     store classification             return critique
                                      to Generator
                                    (bounded retries)
                                          |
                                  review if still FAIL
                         |
                         v
       Monitor sampled PASS / FAIL / revised decisions
       -> human raters -> alignment metrics -> drift alerts
       -> augment benchmark + human-approved retuning
```

**Four automated components from Netflix's article:**

| Component | Netflix responsibility | Our corresponding component (planned unless noted) |
|---|---|---|
| Generator | Creates recommendation explanations; revises from judge feedback | Creates primary incident domain + secondary attributes + cited evidence |
| Judge | For each criterion, returns PASS/FAIL and short rationale; serves as gate and critic | Independent judges for taxonomy compliance, grounding, and completeness |
| Meta-Judge | Compares Judge's FAIL rationale against human FAIL rationale | Checks whether a rejection is for the expert's reason |
| Reflector | Proposes rubric-text edits using failure cases and human reasons | Proposes versioned rubric changes, subject to validation and approval |
| Human experts and raters | Establish standards, label examples, monitor and approve changes | SME ground truth, disagreement adjudication, controlled rubric promotion |

### Phase I — Birth: benchmark and ground truth (implemented starter)

1. **Define the decision**: the Generator will assign one `primary_domain` and independent `attributes` with values `yes`, `no`, or `unknown`; it must not hallucinate negative evidence from silence.
2. **Write guidelines** for annotators that define each domain, priority rule and explicit evidence requirements. The same guidelines seed judge rubrics in Phase II.
3. **Create benchmark samples** from expert-authored adversarial cases, human-reviewed LLM-generated boundary cases and sampled real generator outputs (after privacy screening). Netflix describes all three categories; our current starter contains only synthetic illustrative cases.
4. **Annotate the reference** independently by domain experts, store rationale and quoted evidence, resolve disagreement; tag ambiguous cases for human review.
5. **Annotate candidate outputs separately**: PASS/FAIL per criterion with a written reason for failure. An incident's correct label and a candidate classification's quality rating are different records.
6. **Split carefully** into development/validation/held-out test by incident family to avoid leaking paraphrases. Preserve immutable benchmark versions.

**Current files:** `rubrics/taxonomy.json` (draft), `data/seed_cases.jsonl` (12 draft synthetic incidents), `data/candidate_labels.jsonl` (6 illustrative candidate assessments), `src/validate.py` (structural validator), `tests/test_benchmark.py` (unit tests).

#### Hierarchical segmentation example

Incident: "Customer traded in an old phone; promotional monthly credit is missing."

```json
{
  "primary_domain": "promotion",
  "attributes": {
    "trade": "yes",
    "promo": "yes",
    "device_involved": "unknown",
    "payment_plan_involved": "unknown"
  }
}
```

The primary domain identifies the **reported failing process**, not every mentioned business process. `no` should be reserved for explicit negative information. `unknown` means insufficient evidence. Domain meanings for `DA` and `Switch` are still provisional and must be confirmed with an SME; the dataset is not production-approved.

### Phase II — Training / alignment (not implemented)

Netflix's **Reasoning-Aligned Rubric Tuning (RART)** changes **rubric/prompt text**, not LLM weights. Its loop is:

1. Score benchmark training examples with the current criterion-specific Judge rubric. Keep Judge `verdict` and `rationale`.
2. Evaluate **held-out validation** alignment separately for each criterion; stop when agreed thresholds are reached.
3. Build a **focus set** from both (a) Judge–human label disagreement and (b) Judge FAIL / human FAIL where the **Meta-Judge** finds mismatched explanations.
4. Give these cases, expert rationales, anchor examples and current rubric to the **Reflector** to propose a new rubric.
5. Re-score and compare metrics. Promote only revisions that clear validation and explicit human approval; version and retain previous rubrics.

Metrics per criterion: **fail-recall / specificity** (reject bad outputs), **pass-recall** (accept good outputs), and **reasoning agreement** (same reason when both fail). Reasoning agreement must not be calculated from label agreement alone. Calibrate the Meta-Judge against independent human assessments of rationale pairs.

### Phase III — Deployment (not implemented)

```text
Incident -> Generator -> all mandatory Judges
                           | PASS -> approved classification
                           | FAIL -> critique to Generator -> retry
                                                      | still FAIL -> review queue
```

Netflix reused the Judge as both a **gate** and a **critic**, with a three-retry budget in its described experiment and a final drop of failed *recommendation explanations*. For an operational incident, **hold for human review instead of discarding the incident**. Retain the original text, candidate labels, rubric versions, decisions, model versions and retry trace. Do not execute telecom remediation actions as part of this classification workflow.

### Phase IV — Human-in-the-loop monitoring (not implemented)

Netflix sampled roughly **300 explanations per week** during its tests, stratified across passed/revised/dropped decisions and weighted toward newer catalog items. At least **three raters** reviewed each; the majority provided the ground-truth label. The Judge was evaluated against the same majority label and compared with the human rater distribution, using a floor at **two standard deviations below mean rater performance** per metric/criterion. Drift triggered benchmark enrichment and re-tuning; rubrics were human-approved before deployment and kept for rollback.

For our project, start with a configurable periodic stratified review of incidents (including new incident types, disagreements and held classifications). Store rater labels and reasons, measure per-segment confusion and per-criterion agreement, monitor distribution shifts, and route drift to Phase I/II. The precise sampling size and thresholds are **design choices**, not mandatory Netflix values for telecom.

## Run Phase I locally

Requirements: Python 3.10+; no external API keys or LLMs for the current phase.

```powershell
cd llm-as-judge
python -m src.validate --strict
python -m unittest discover -s tests -v
```

Validation checks schema and consistency, **not** semantic accuracy or actual human consensus.

## Human labeling / release checklist

- [ ] Confirm the `DA` and `Switch` definitions, whether Trade is an attribute, and the treatment of Non-Trade/Non-Promo.
- [ ] Define domain precedence and minimum evidence requirements; assign rubric owner.
- [ ] Obtain independent expert annotations and reasons; adjudicate conflicts and version them.
- [ ] Add hard negative, near-boundary and real anonymized incident samples.
- [ ] Freeze held-out cases separately from calibration cases.
- [ ] Only then implement baseline Judges, Meta-Judge, Reflector and human-reviewed RART.
- [ ] Later implement bounded generate–judge–revise, operational monitoring and rollback.

## Privacy and operational safety

Use synthetic or anonymized incidents for development. Exclude customer personal information, account numbers, credentials, and production secrets. Incident descriptions are untrusted **data**, not instructions to the LLM. No automatic production action is part of this phase.


## Phase II-A — Taxonomy Judge (implemented)

The `judges/taxonomy_judge.py` module implements a Netflix-inspired **per-criterion Judge**. It runs a local Ollama model via the HTTP API with a fixed system prompt, the versioned taxonomy rubric, the incident description, and the candidate segmentation. The response is validated as JSON. **The Judge never sees the reference classification or human rationale.** The evaluator adds draft human labels afterward to measure agreement. A failed model call is recorded as ERROR, not PASS or FAIL.

### Getting started (PowerShell)

```powershell
ollama pull llama3.2
python -m src.validate --strict
python -m unittest discover -s tests -v
python -m judges.taxonomy_judge --id INC-002
python -m judges.taxonomy_judge --all
```

`--all` writes `evaluation_phase2a.json`, containing decisions and observed label agreement. Ollama must be running locally; no API key is required. Real model accuracy has **not** been measured in this package. The draft synthetic labels are **not expert-validated ground truth**, so evaluation figures are engineering smoke-test metrics only. A schema-valid JSON response is not proof of correct judgment.

### Next: Phase II-B

Build a Meta-Judge that compares human and Judge rationales for examples where both said FAIL, then use these disagreements alongside label errors as the RART Reflector focus set. Do not automatically modify approved rubrics.
