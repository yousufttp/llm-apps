# TIRA — Telecom Incident Resolution Agent

Production-structured local LangGraph learning project with SQLite persistence, dummy telecom services, human approval, idempotent remediation, a golden dataset, local evaluation, and optional LangSmith tracing/evaluation.

## Run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Evaluate locally
```bash
python -m evaluation.run_local_evaluation
```

## LangSmith
Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` in `.env`, then:
```bash
python -m evaluation.langsmith_eval
```

### Evaluation results

![LangSmith evaluator results](Langsmith-evaluator1.png)

### Trace

![LangSmith trace](Langsmith-Trace.png)

## TIRA tables
- tira_incident_runs
- tira_remediation_operations
- tira_evaluation_results

LangGraph creates its own framework checkpoint tables in the same SQLite DB; those are library-owned and are not prefixed with `tira_`.
