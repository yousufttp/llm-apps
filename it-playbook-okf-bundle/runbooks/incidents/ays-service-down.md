---
type: Runbook
title: AYS Service Down
description: Steps to diagnose and recover when the AYS service stops responding.
resource: https://internal.example.com/servicenow/AYS-runbook
tags: [ays, outage, kubernetes]
timestamp: 2026-07-21T00:00:00Z
---

# Symptoms
- Health-check endpoint returns 5xx
- Pending Order queue backs up (see [DPP Timeout](/incidents/dpp-timeout.md) for related symptom)

# Diagnosis Steps
1. Check pod status: `kubectl get pods -n ays`
2. Check ELK logs for `OutOfMemoryError` or `ConnectionTimeout`
3. Check related metric: [Incident Count](/metrics/incident-count.md)

# Resolution
- Restart pod: `kubectl rollout restart deployment/ays -n ays`
- If DB2 connection pool exhausted, scale connection pool config

# Escalation
Escalate to AYS swimlane on-call if not resolved in 30 minutes.
