# LLM Gateway

A small OpenAI-compatible streaming gateway for a local Ollama `llama3.2` model.

## Setup

```bash
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
ollama pull llama3.2
```

Start Ollama, then run the API from the `LLM-Gateway` directory:

```bash
uvicorn app.main:app --reload
```

The health endpoint is available at `GET /health`. Chat requests are sent to
`POST /v1/chat/completions` with a model alias of `local` (or `llama3.2`) and a
non-empty `messages` array. The response is Server-Sent Events containing
streamed content, usage data, and a final `[DONE]` event.
