---
name: agent-validation-eval
description: Design and run focused evaluations of AI agents against realistic tasks, with explicit criteria, controlled inputs, and evidence-backed results.
---

# Agent Validation Eval

Use this skill when the user wants to validate, benchmark, regression-test, or assess an AI agent, agent workflow, prompt, tool policy, or multi-agent system. Produce an evaluation plan and results; do not silently modify the agent under test unless the user also requests remediation.

## Evaluation workflow

1. Define the claim being tested and the agent boundary: model/prompt version, tools, data sources, permissions, and expected side effects.
2. Convert the claim into observable success criteria. Include correctness, instruction-following, safety/authorization, tool use, robustness, and user-facing quality only when relevant.
3. Build a small representative test set. Include normal cases, edge cases, ambiguous inputs, and at least one adversarial or out-of-scope case when the claim involves safety or boundaries. Keep test inputs independent and do not leak the expected answer into the prompt.
4. Establish an oracle for each case: exact answer, structured constraints, a reference rubric, or a human-review decision. Separate objective checks from subjective scoring.
5. Run the cases in an isolated workspace or dry-run mode when possible. Record the exact input, agent output, tool calls, errors, latency/cost if available, and side effects. Never use live production mutations merely to obtain a score without explicit authorization.
6. Score each case against the predeclared criteria. Mark outcomes as `pass`, `fail`, `partial`, or `blocked`; distinguish an agent failure from an unavailable dependency or inadequate test oracle.
7. Report aggregate results and concrete failures. Include per-case evidence, severity, reproducibility, likely cause, and the smallest useful next step. State test coverage and residual risks.

## Test design guidance

- Prefer a few high-signal cases over a large synthetic suite with duplicated wording.
- Test both successful completion and correct refusal or clarification where the task is unsafe, unauthorized, underspecified, or outside scope.
- For tool-using agents, verify tool selection, argument correctness, ordering, error handling, and whether actions stayed within authorization.
- For structured outputs, validate the schema and semantics independently of prose formatting.
- Treat a single successful run as insufficient evidence for nondeterministic behavior; repeat cases when variance matters and report the number of trials.
- Do not change prompts, tools, or test data mid-run. If a fix is evaluated, label it as a separate version and compare like-for-like.

## Result format

Lead with the verdict and the most important evidence. Include:

- scope and versions tested;
- test matrix with case, expected behavior, observed behavior, status, and evidence;
- summary metrics, including the denominator and any blocked cases;
- high-severity failures and reproducibility;
- limitations, untested paths, and recommended next action.

Do not claim an agent is safe, reliable, or production-ready from a narrow pass rate alone. Qualify conclusions by the tested scope and confidence.
