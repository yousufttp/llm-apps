# Lesson 4 — Actual MCP comparison

Copy `mcp_server.py` and `mcp_agent.py` into the **root** of your existing OpsCLI project, beside `agent.py`.

In PowerShell:

```powershell
python -m pip install --upgrade mcp openai python-dotenv
python mcp_agent.py "Get incident INC1001 and find related Jira defects"
```

Your existing `.env` must contain `OPENAI_API_KEY=...`; optionally set `OPENAI_MODEL=gpt-4.1-mini`.

Keep MCP and CLI on the same model and use the exact same test prompt. Compare `total_tokens`, `input_tokens`, `output_tokens`, `cached_input_tokens` and the number of model requests. An MCP client can also filter/select schemas; this example intentionally exposes all six read-only MCP tools.

`mcp_server.py` is a real MCP stdio server. `mcp_agent.py` creates a stdio connection, discovers tool schemas via `list_tools`, maps them to OpenAI functions, and executes selected tools using `call_tool`. The OpenAI API does not directly speak stdio MCP here—the local Python client bridges the two.
