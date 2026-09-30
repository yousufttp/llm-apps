# LLM Portfolio

![LLM](https://img.shields.io/badge/Focus-LLM%20Applications-6f42c1)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![Status](https://img.shields.io/badge/Status-Active%20Development-2ea44f)

A collection of practical LLM, agent, NLP, and AI application projects built as a hands-on portfolio for future interviews.

The projects in this repository focus on useful AI systems—not just model calls. They explore classification, RAG, semantic search, multi-agent orchestration, human approval, evaluation, observability, and production-style application design.

## Project showcase

### [CareAgent](https://github.com/yousufttp/CareAgent)

Production-structured telecom customer-care application with a FastAPI backend, LangGraph supervisor, specialist workers, CopilotKit frontend, Oracle persistence, approval workflows, and OpenTelemetry observability.

**Highlights:** multi-agent workflows · policy-controlled tools · human approval · customer/operator workspaces · tracing

### [TIRA — Telecom Incident Resolution Agent](https://github.com/yousufttp/TIRA-LangGraph-Workflow)

Local LangGraph incident-resolution agent with SQLite persistence, deterministic remediation tools, human approval, idempotent operations, a golden dataset, and local/LangSmith evaluation.

**Highlights:** agent state · evaluation · persistence · safe remediation · LangSmith tracing

<p align="center">
  <img src="./TIRA/Langsmith-evaluator1.png" width="48%" alt="TIRA LangSmith evaluator results" />
  <img src="./TIRA/Langsmith-Trace.png" width="48%" alt="TIRA LangSmith trace" />
</p>

### [Laya Reopen Analyser](https://github.com/yousufttp/Laya-Reopen-Analyser)

Streamlit application that processes incident workbooks, uses a local Laya model to determine whether a customer issue remains unresolved, and exports row-level verdicts with probabilities and error handling.

**Highlights:** local model inference · batch processing · Excel workflow · Streamlit UI · downloadable results

<p align="center">
  <img src="./Laya-Reopen-Analyser/GUI.png" width="80%" alt="Laya Reopen Analyser interface" />
</p>

### [GraphRAG Mini](https://github.com/yousufttp/llm-apps/tree/main/GraphRAG)

Learning implementation of Graph-based Retrieval-Augmented Generation. It extracts entities and relationships, builds a knowledge graph, detects communities, generates summaries, and supports local and global search.

**Highlights:** entity extraction · NetworkX graph · community detection · local search · global search

### [BERT Incident Classifier](https://github.com/yousufttp/BERT_Incident_classifier)

Local incident-ticket classifier that uses a frozen BERT text encoder and scikit-learn logistic regression to predict support group and category, with confidence-based manual review.

**Highlights:** BERT embeddings · supervised classification · Excel input · repeatable inference · confidence thresholds

### [Incident AI](https://github.com/yousufttp/llm-apps/tree/main/incident-ai)

Incident-focused AI experimentation project exploring automated understanding and resolution workflows.

### [IT Playbook OKF Bundle](https://github.com/yousufttp/llm-apps/tree/main/it-playbook-okf-bundle)

Structured IT operations and playbook resources for grounding incident-analysis and retrieval workflows.

### [Gemini Experiments](https://github.com/yousufttp/llm-apps/tree/main/gemini)

Experiments with Google Gemini capabilities and multimodal/model-assisted application patterns.

### [First ML Project](https://github.com/yousufttp/my-first-ml)

Early machine-learning project demonstrating the foundations behind the later NLP and LLM systems in this portfolio.

## Skills demonstrated

| Area | Examples in this portfolio |
| --- | --- |
| LLM applications | Gemini experiments, CareAgent, TIRA |
| RAG and search | GraphRAG Mini, IT playbook bundle |
| NLP and classification | BERT Incident Classifier, Laya Reopen Analyser |
| Agents | LangGraph supervisors, specialist workers, remediation agents |
| Reliability | Human approval, confidence thresholds, idempotency, readback verification |
| Evaluation | Golden datasets, local evaluation, LangSmith evaluators and traces |
| Product engineering | FastAPI, Streamlit, Next.js, Docker, Oracle, SQLite |

## Portfolio roadmap

- Add project-specific architecture diagrams and demo videos
- Expand automated tests and evaluation datasets
- Add deployment examples for selected applications
- Document model, latency, cost, and accuracy trade-offs
- Continue exploring multimodal, RAG, and tool-using agent systems

## Getting started

Each project is independently documented and may use a different environment. Start with the project README, then run its setup instructions.

```bash
git clone <repository-url>
cd ai-portfolio
```

For example:

```bash
cd TIRA
python main.py
```

## About this portfolio

I am building this repository as a record of continuous learning and as a practical demonstration of LLM application development. Projects will continue to be improved with stronger evaluations, clearer documentation, tests, and deployment examples.

## License

Add a license here before distributing the repository publicly.
