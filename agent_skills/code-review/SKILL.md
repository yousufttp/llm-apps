---
name: code-review
description: Review application code for actionable correctness, security, reliability, and maintainability issues with evidence and precise file references.
---

# Code Review

Use this skill when the user asks to review, audit, inspect, or assess code. Produce a review, not an unsolicited implementation, unless the user also requests fixes.

## Review workflow

1. Establish scope from the request, repository state, and relevant tests/configuration. Preserve unrelated working-tree changes.
2. Read the changed code in context, including callers, error paths, data validation, authentication/authorization, persistence, concurrency, and configuration boundaries where relevant.
3. Run focused, safe checks when available: syntax/type checks, targeted tests, linters, or a minimal reproduction. Do not hide failures or mutate external systems.
4. Report only actionable findings supported by code evidence. Prefer a small number of high-confidence findings over speculative concerns.

## Finding standards

For each finding, include:

- severity: `critical`, `high`, `medium`, or `low`;
- exact file and line reference;
- the concrete behavior or failure mode;
- why it matters and, when useful, a focused remediation.

Prioritize exploitable security issues, data loss/corruption, broken runtime behavior, and regressions before style or maintainability suggestions. Distinguish verified issues from assumptions and state what was not tested.

Do not treat missing tests as a defect unless the untested behavior creates a meaningful regression risk. Avoid recommending broad rewrites when a focused change addresses the issue.

## Final response

Lead with findings, ordered by severity. If no actionable issues are found, say so clearly and summarize the checks performed. Include a brief note on residual risks or untested paths, then optionally mention strengths or follow-up suggestions.
