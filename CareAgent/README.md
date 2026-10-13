# CareAgent

Local telecom customer care with Oracle Database **21c XE**, FastAPI, LangGraph, LiteLLM, CopilotKit, and OpenTelemetry.

Customers sign in, select a mobile or broadband service, and describe their issue. A supervisor plans the work and routes tasks to specialist nodes. Account changes require explicit confirmation and a successful readback. Operators receive exceptions, billing disputes, and permanent disconnection requests.

**This is a synthetic-data demo.** It does not connect to a real carrier, process payments, activate physical equipment, or submit real trade-ins. `MODEL_MODE=demo` uses deterministic intent routing; `MODEL_MODE=live` uses your chosen model through LiteLLM. Specialist tools and execution policy remain deterministic in both modes.

## Architecture

```mermaid
flowchart LR
  Customer[Customer / operator] --> Web[Next.js + CopilotKit]
  Web -->|HttpOnly session / AG-UI| API[FastAPI]
  API --> Supervisor[LangGraph supervisor]
  Supervisor --> Workers[Account + domain specialists]
  Workers --> Approval[Durable customer approval]
  Approval --> Tools[Policy-controlled simulated tools]
  Tools --> Verify[Readback verification]
  Workers --> Queue[Operator cases]
  Verify --> Queue
  API --> Oracle[(Oracle 21c XE)]
  Supervisor --> Oracle
  API --> OTEL[OpenTelemetry Collector]
  OTEL --> Jaeger
  OTEL --> Prometheus
  Supervisor --> LLM[LiteLLM: hosted provider or Ollama]
```

- `backend/careagent`: API, authentication, agent graph, policy tools, and Oracle checkpoint saver.
- `frontend`: customer and operator workspaces, CopilotKit runtime, same-origin API proxy.
- `deploy`: observability configuration.
- `backend/migrations`: frozen Alembic schema migrations.

## Start locally

Prerequisites: your **existing Oracle Database 21c**, Python 3.13, UV, Node.js 22, npm, and Git. The application runs directly on Windows or Linux; it does not require Docker or an additional Oracle installation.

### 1. Configure your existing Oracle connection

Use a dedicated CareAgent application schema in your existing database. It needs `CREATE SESSION`, `CREATE TABLE`, `CREATE SEQUENCE`, and a tablespace quota. Do not use SYS, SYSTEM, or a schema containing unrelated application data. Your DBA can provide the schema; CareAgent does not create database users.

```powershell
Copy-Item .env.example .env
```

The configured connection is **user `careagent`, service `xepdb1`, host `localhost`, port `1521`**. Fill `ORACLE_PASSWORD` in the ignored local `.env` file. The service name and schema username are separate values.

### 2. Install and start the API

From CareAgent in PowerShell:

```powershell
uv sync --frozen
uv run python scripts/check_oracle.py
uv run python -m careagent.bootstrap
uv run uvicorn careagent.api:app --reload --no-access-log
```

The bootstrap command waits for your existing Oracle connection, applies migrations, and seeds demo data once. Keep this terminal running.

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

| Address | Purpose |
| --- | --- |
| http://localhost:8000/docs | FastAPI API reference |
| http://localhost:8000/health/ready | Database readiness and model mode |
| http://localhost:3000 | Customer and operator GUI |
| http://localhost:8000/docs | FastAPI API reference |

Account and workflow data remain in your existing Oracle schema. Changing `.env` credentials does not change database passwords.

### Demo sign-ins

All three users have password **`CareDemo123!`**.

| User | Access |
| --- | --- |
| `alex@example.test` | Mobile and broadband services in active, pending, and suspended states |
| `jordan@example.test` | Restricted account for eligibility exception scenarios |
| `operator@example.test` | Escalation queue, evidence, credits, and disconnection |

Sessions expire after eight hours. Cookies are HttpOnly and SameSite=Strict. Use `COOKIE_SECURE=true` and a matching `ALLOWED_ORIGIN` when running behind HTTPS. Credentials and sessions are enforced by the backend; the selected account is never taken from model output.

## Connect a model

Set `MODEL_MODE=live`, then configure the model, key, and optional endpoint in `.env`. Restart the local Uvicorn process. No provider fallback is enabled. Model output is schema-validated; malformed output, timeouts, and unavailable providers result in human handoff.

| Provider | Example `LLM_MODEL` | `LLM_API_BASE` |
| --- | --- | --- |
| OpenAI | `openai/gpt-4.1-mini` | Empty; use provider default |
| Anthropic | `anthropic/claude-sonnet-4-5` | Empty; use provider default |
| Google | `gemini/gemini-2.5-flash` | Empty; use provider default |
| OpenAI-compatible server | `openai/your-served-model` | Your server's `/v1` endpoint |
| Local Ollama | `ollama_chat/qwen2.5:7b` | `http://localhost:11434` |

Use a model available to your provider account; the names above are configuration examples. Set `LLM_API_KEY` for hosted providers. **Clear the default Ollama base URL when switching to a hosted provider.** Keys stay in backend configuration and are never sent to the browser.

Install and start Ollama separately if you want local inference, then pull the model with `ollama pull qwen2.5:7b`. No externally hosted fonts or CopilotKit cloud key are required.

Live mode sends the current customer message and up to ten saved messages to the configured model. Raw messages, account records, credentials, and model responses are excluded from application telemetry. Do not enable provider debug logging when using real data.

## Demo walkthroughs and policy

Choose the named service, select **Start a conversation**, then send the prompt. Each conversation is bound to one service; open another conversation for a different service. The **Saved conversation** section shows durable history after a reload.

| Scenario | Service / prompt | Expected result |
| --- | --- | --- |
| Activation | New mobile or New broadband: `activate my service` | Approve → active, then verified |
| Discount | Personal mobile or Home broadband: `apply a discount` | Approve → MOBILE10 / FIBER15 |
| Billing explanation | Any Alex service: `explain my bill` | Account-level bill breakdown; no mutation |
| Billing dispute | `my bill is incorrect; refund the duplicate charge` | Operator case; operator can credit up to $100 and no more than remaining invoice balance |
| Trade-in | Personal mobile: `start a trade in` | Approve → one submission for the eligible device |
| Disconnect | `disconnect my service` | Operator reviews and confirms permanent disconnection |
| Reconnect | Travel mobile or Seasonal broadband: `reconnect my service` | Approve → active |
| Suspension | Personal mobile or Home broadband: `suspend my service` | Approve → suspended |
| Multiple issues | New mobile: `activate then apply a discount` | Two sequential, independent approvals |
| Decline | Any eligible proposal → Decline | No change; next task proceeds |
| Exception | Jordan: `reconnect`; broadband: `trade in` | Human case with eligibility evidence |
| Explicit handoff | `I want a human` | Immediate escalation |

Demo rules: activation requires `pending`; reconnect requires `suspended`; suspension requires `active`. Restricted accounts require an operator. Discounts require active service and no current promotion. Trade-ins require an eligible mobile device and no previous submission. Promotions annotate the account for future simulated cycles; they do not rewrite the seeded invoice. Reconnection does not restore permanently disconnected service. Invalid transitions become operator cases.

The deterministic router recognizes the phrases above; it is not a general natural-language model. Negated requests ask for clarification. In live mode the supervisor can request missing intent details. Service selection provides the target; models never choose another customer's account.

Approvals capture exact parameters and a service version. Execution locks the approval and service, rechecks eligibility, performs the simulated mutation and audit insertion in one transaction, and verifies the result before committing. A failed readback rolls the mutation back and creates a case. Concurrent or repeated approvals cannot repeat a committed action. Pending graph interrupts survive API restarts. Conversation leases prevent concurrent runs and expire after five minutes following a crash.

Operators can inspect the entire conversation, account evidence, and attempted actions. Billing credits require a billing case; permanent disconnection requires a disconnect case. Other exceptions can be resolved with an explanatory note; this does not silently bypass account restrictions or perform an unsupported service change.

## Local development / existing Oracle 21c

Create a dedicated application schema with `CREATE SESSION`, `CREATE TABLE`, `CREATE SEQUENCE`, and a tablespace quota. Configure `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE`, `ORACLE_USER`, and `ORACLE_PASSWORD` in `.env`. An explicit SQLAlchemy `DATABASE_URL` can override these, for example `oracle+oracledb://user:password@host:1521/?service_name=XEPDB1` (URL-encode special password characters).

```powershell
uv sync --frozen
uv run python scripts/check_oracle.py
uv run alembic upgrade head
uv run python -m careagent.seed
uv run uvicorn careagent.api:app --reload --no-access-log
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

The frontend defaults to `http://127.0.0.1:8000`; set server-side `BACKEND_URL` for another API location. `python-oracledb` uses Thin mode, so no Oracle Instant Client installation is needed. The API never uses SYS/SYSTEM credentials. Oracle DDL auto-commits: review migrations before applying them to a persistent database.

## Tests and verification

```powershell
uv run ruff check backend scripts
uv run python -m pytest -q
cd frontend
npm run typecheck
npm run build
```

Default tests use disposable SQLite databases to quickly exercise policy, authentication, AG-UI events, approval idempotency, checkpoint serialization, and restart recovery. **SQLite tests are not proof of Oracle locking or dialect behavior.**

To test real Oracle, supply an **empty disposable 21c schema**, separate from the demo application schema:

```powershell
$env:TEST_ORACLE_URL='oracle+oracledb://careagent_test:TestPassword21@localhost:1521/?service_name=XEPDB1'
uv run python -m pytest -m oracle -v
```

The test refuses schemas with existing tables, applies migrations, checks repeatable seeds, BLOB checkpoint round trips, intermediate writes, approval recovery, and transaction rollback, then downgrades. The Alembic version table remains; use a fresh empty schema for the next run. A failed run can leave test tables for diagnosis.

Browser tests require a running stack in demo mode and **fresh seed data** (they change service state):

```powershell
cd frontend
npx playwright install chromium
npm run test:e2e
```

To verify observability, perform a chat and an approved service action. In Jaeger, locate supervisor, specialist, execution, and readback spans. In Prometheus, query `careagent_runs_total`, `careagent_escalations_total`, and the `careagent_run_duration_seconds` histogram. Token metrics are populated only by live providers that return usage. Logs are structured JSON with trace IDs and omit raw request content.

For live-provider smoke testing, use the same activation or billing walkthrough with `MODEL_MODE=live`. Validate the routing and handoff behavior; CI never makes paid model calls.

## API overview

- `/api/v1/auth/login`, `/auth/logout`, `/me`: session lifecycle.
- `/api/v1/account`: only the authenticated customer's account.
- `/api/v1/conversations`: create/list service-bound conversations; `/{id}` returns durable history and approvals.
- `/api/v1/conversations/{id}/messages`: REST agent run; reuse `run_id` when retrying a failed request. `/recover` resumes interrupted work; the GUI provides a matching recovery button.
- `/api/v1/agent`: authenticated AG-UI event stream used by CopilotKit. Client-supplied agent state is not trusted.
- `/api/v1/approvals/{id}`: explicit approval/decline.
- `/api/v1/cases`: customer-owned cases or the operator queue.
- `/api/v1/operator/cases/{id}` and `/resolve`: evidence and audited operator actions.

The local demo uses one API process and one supervisor graph per application. Production SSO, external carrier adapters, payment/refund processing, distributed job scheduling, and retention controls are future integration work. No Oracle installation or extra Oracle container is required.
