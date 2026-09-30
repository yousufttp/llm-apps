---
type: Runbook
title: DPP Timeout
description: Steps for when the DPP swimlane times out processing pending orders.
resource: https://internal.example.com/servicenow/DPP-runbook
tags: [dpp, timeout, pending-order]
timestamp: 2026-07-21T00:00:00Z
---

# Symptoms
- Pending Order queue depth rising
- Often correlated with [AYS Service Down](/incidents/ays-service-down.md)

# Diagnosis Steps
1. Query Oracle for stuck order records
2. Check ServiceNow for related open incidents

# Resolution
- Requeue stuck orders via admin tool
- If root cause is AYS, follow [AYS Service Down](/incidents/ays-service-down.md) runbook first
