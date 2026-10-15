# OpsCLI

OpsCLI is a small Python telecom-operations demo with two interfaces:

- a local command-line interface that reads and writes JSON records;
- an OpenAI-powered agent that answers operational questions through one restricted, read-only CLI tool.

The project also includes an MCP implementation for comparing a multi-tool MCP interface with the single-tool CLI approach.

![OpsCLI workflow](MCP%20VS%20CLI%20workflow.png)

## Project layout

```text
OpsCLI/
├── opscli/                 # CLI package
├── data/                   # Local incident and defect JSON records
├── agent.py                # OpenAI Responses API agent
├── mcp/                    # MCP server and MCP comparison agent
├── .env-example            # Environment variable template
└── README.md
```

## Requirements

- Python 3.10 or newer
- No third-party packages are required for the local CLI
- `openai` and `python-dotenv` are required for `agent.py`
- `mcp`, `openai`, and `python-dotenv` are required for the MCP example

## Run the local CLI

From the project directory:

```powershell
python -m opscli --help
python -m opscli health
python -m opscli get-incident INC1001
python -m opscli search-defects ACT-401
python -m opscli incident-stats
```

All commands emit compact JSON. The CLI uses `data/incidents.json` and `data/defects.json` by default. Set `OPSCLI_DATA_DIR` to use another data directory.

## Commands

| Command | Purpose | Example |
|---|---|---|
| `health` | Check CLI health and tool count | `python -m opscli health` |
| `get-incident` | Read one incident | `python -m opscli get-incident INC1001` |
| `list-incidents` | List or filter incidents | `python -m opscli list-incidents --status Open` |
| `search-incidents` | Search incident fields | `python -m opscli search-incidents activation` |
| `create-incident` | Create an incident | `python -m opscli create-incident --category Activation --description "Activation failure"` |
| `update-status` | Change status | `python -m opscli update-status INC1001 --status Resolved` |
| `assign-incident` | Assign an owner | `python -m opscli assign-incident INC1001 --owner Alex` |
| `add-note` | Add a work note | `python -m opscli add-note INC1001 --text "Verified order"` |
| `search-defects` | Search mock Jira defects | `python -m opscli search-defects ACT-401` |
| `incident-stats` | Summarize incident counts | `python -m opscli incident-stats` |

The mutating commands update `data/incidents.json`: `create-incident`, `update-status`, `assign-incident`, and `add-note`.

## Run the OpenAI agent

Install the agent dependencies:

```powershell
python -m pip install --upgrade openai python-dotenv
```

Create `.env` from `.env-example` and set `OPENAI_API_KEY`. You can optionally set `OPENAI_MODEL`; the default is `gpt-4.1-mini`.

```powershell
python agent.py "Which incidents are currently open?"
python agent.py "Get incident INC1001 and find related Jira defects"
```

The agent exposes exactly one function tool, `run_opscli`, and permits only these read-only commands: `health`, `get-incident`, `list-incidents`, `search-incidents`, `search-defects`, and `incident-stats`. Each run prints the CLI calls and token-usage summary.

## MCP comparison

The `mcp/` folder contains a real stdio MCP server and an MCP client that discovers and calls its tools:

```powershell
python -m pip install --upgrade mcp openai python-dotenv
python mcp/mcp_agent.py "Get incident INC1001 and find related Jira defects"
```

Use the same model and prompt for both approaches, then compare input, output, cached, total tokens, and model-request counts.

![MCP versus CLI token comparison](MCP%20VS%20CLI%20Token%20Comparison.png)

## Safety notes

This is a local mock application, not a production ServiceNow or Jira integration. Do not expose arbitrary shell execution to untrusted users. A real integration should add authentication, authorization, strict validation, audit logging, and confirmation for high-impact updates.
