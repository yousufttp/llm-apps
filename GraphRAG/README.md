# GraphRAG Mini - Learning Project

A lightweight GraphRAG implementation built from scratch to understand how Graph-based Retrieval Augmented Generation works.

## What is GraphRAG?

Traditional RAG chunks documents and retrieves similar chunks. GraphRAG goes further:
1. **Extracts entities & relationships** from documents using an LLM
2. **Builds a knowledge graph** connecting all entities
3. **Detects communities** (clusters of related entities)
4. **Generates summaries** for each community
5. **Supports two search modes**:
   - **Local Search**: Finds relevant entity → explores its neighborhood
   - **Global Search**: Uses community summaries for big-picture questions

## Project Structure

```
graphrag-mini/
├── data/                          # Sample IT playbook documents
│   ├── playbook_payment_service.md
│   ├── playbook_user_service.md
│   ├── playbook_order_service.md
│   └── playbook_platform_infra.md
├── src/
│   └── graphrag_pipeline.py       # Complete pipeline implementation
├── output/
│   └── graph_data.json            # Exported graph (after running)
└── README.md
```

## How to Run

### Demo Mode (No API Key Needed)
```bash
cd graphrag-mini/src
python graphrag_pipeline.py
```
This runs with mock LLM responses to demonstrate the full pipeline.

### With Real LLM
Replace `mock_llm_call` with a real API call function (e.g., Claude API or OpenAI).

## Pipeline Steps (What the Code Does)

| Step | Function | LLM? | What it does |
|------|----------|-------|-------------|
| 1 | `load_documents()` | No | Reads markdown files |
| 2 | `extract_entities_and_relationships()` | **Yes** | LLM extracts entities & relationships |
| 3 | `build_graph()` | No | Creates NetworkX graph, merges entities |
| 4 | `detect_communities()` | No | Groups related entities into clusters |
| 5 | `generate_community_summaries()` | **Yes** | LLM summarizes each community |
| 6a | `local_search()` | **Yes** | Entity-focused search |
| 6b | `global_search()` | **Yes** | Community-summary-based search |

## Key Concepts

- **Entity Extraction**: LLM reads each document and identifies services, teams, people, tools
- **Relationship Extraction**: LLM identifies how entities connect (depends_on, owns, manages)
- **Community Detection**: Algorithm groups tightly-connected entities into clusters
- **Community Summaries**: Pre-generated summaries enable fast global search
- **Local vs Global**: Local = specific entity questions, Global = broad/summary questions
