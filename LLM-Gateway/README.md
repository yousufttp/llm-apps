# LLM Gateway

A small OpenAI-compatible streaming gateway that routes requests to local
Ollama models and optionally to OpenAI. The gateway now includes API-key
authentication, Redis-backed rate limiting, explicit cloud-fallback approval,
SQLite usage records, latency tracking, and estimated token cost reporting.

## Setup

```bash
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull llama3.2
```

Start Ollama and Redis, then run the API from the `LLM-Gateway` directory:

```bash
uvicorn app.main:app --reload
```

Redis is required when serving chat requests because it stores the per-key
rate-limit counter. Set `REDIS_URL` when Redis is not using its local default.
Set `GATEWAY_API_KEY` before calling protected endpoints. Add `OPENAI_API_KEY`
only if the OpenAI provider or cloud fallback is needed. See `.env.example` for
all supported variables.

## API

`GET /health` is public and reports service health. The following endpoints
require the `X-API-Key` header:

- `GET /v1/models` lists configured model aliases.
- `POST /v1/chat/completions` streams a chat completion as Server-Sent Events.
- `GET /v1/usage?limit=20` returns recent SQLite usage records.

Example request:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $GATEWAY_API_KEY" \
  -d '{"model":"local","messages":[{"role":"user","content":"Hello"}]}'
```

Supported aliases include `local`, `local-small`, and `llama3.2`. The gateway
emits route metadata, content chunks, usage data when the provider supplies it,
and a final `[DONE]` event. Cloud fallback is disabled by default and must be
requested explicitly with `"allow_cloud_fallback": true`.

Each request is recorded in `data/gateway.db`, which is ignored by Git. The
estimated cost is a learning aid based on the model-price table in
`app/services/usage.py`, not a live billing statement.
