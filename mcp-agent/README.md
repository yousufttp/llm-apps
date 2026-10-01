# Customer Lookup MCP Demo

A small demo where Streamlit sends a mobile-number request to a LangGraph agent. The agent calls a local HTTP MCP server containing three synthetic customers.

## Setup

```powershell
uv sync
Copy-Item .env.example .env
```

Add your `OPENAI_API_KEY` to `.env`. `OPENAI_MODEL` defaults to `gpt-4o-mini`; `MCP_SERVER_URL` defaults to `http://localhost:8000/mcp`.

## Run

Use two terminals from the project directory:

```powershell
uv run python mcp_server.py
```

```powershell
uv run streamlit run app.py
```

Try these demo numbers:

- `212-555-0101` — Ava Patel
- `312-555-0102` — Marcus Johnson
- `415-555-0103` — Sofia Garcia

## Tests

```powershell
uv run pytest
```

The MCP server uses Streamable HTTP at `/mcp`. If the app cannot connect, confirm the server is running and that `MCP_SERVER_URL` matches its address. The app validates numbers before calling the agent and reports missing customers without inventing details.
