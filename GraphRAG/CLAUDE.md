# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

A single-file, pedagogical GraphRAG implementation. The whole pipeline lives in [graphrag_pipeline.py](graphrag_pipeline.py) and is meant to be read top-to-bottom — each step is delineated by a banner comment (`STEP 1` … `STEP 7`).

## Running

```bash
# Demo mode (mock LLM, no API key)
python graphrag_pipeline.py
```

Dependencies (imported lazily inside functions, no `requirements.txt`): `networkx`. The mock LLM has no other deps.

### Path layout caveat
The `__main__` block at [graphrag_pipeline.py:636-647](graphrag_pipeline.py#L636-L647) resolves `data_dir` and `output_dir` as `../data` and `../output` relative to the script — i.e., it assumes the script lives in a `src/` subdirectory (as drawn in [README.md](README.md)). The actual repo is flat: the script sits at the GraphRAG/ root with no `src/`, `data/`, or `output/` directories present. Running as-is will load zero documents. To exercise the pipeline you must either create `../data` with markdown files, or change the paths in `__main__`.

The mock LLM at [graphrag_pipeline.py:461](graphrag_pipeline.py#L461) only matches prompts containing specific document titles (`"Payment Service Playbook"`, `"User Service Playbook"`, `"Order Service Playbook"`, `"Platform Infrastructure"`) — so demo data must use those exact filenames/headers, otherwise extraction returns the generic fallback.

## Architecture

The pipeline is a linear function chain orchestrated by `run_pipeline()` at [graphrag_pipeline.py:403](graphrag_pipeline.py#L403):

1. `load_documents` — read `*.md` from a directory.
2. `extract_entities_and_relationships` — **LLM call per doc**. Uses `EXTRACTION_PROMPT` ([line 42](graphrag_pipeline.py#L42)). Strips markdown fences from response, parses JSON, falls back to empty dicts on parse failure.
3. `build_graph` — merges extractions across docs into one undirected `nx.Graph`. Entities with the same `name` across documents are merged into a single node (descriptions concatenated). Edges accumulate `types` and `descriptions` as parallel lists when the same pair appears multiple times.
4. `detect_communities` — `greedy_modularity_communities` (NetworkX). The README claims Leiden but the code uses greedy modularity for simplicity. Tags each node with a `community` attribute.
5. `generate_community_summaries` — **LLM call per community**. Feeds entity + intra-community-edge details into `SUMMARY_PROMPT` ([line 206](graphrag_pipeline.py#L206)).
6. Two query modes:
   - `local_search` ([line 281](graphrag_pipeline.py#L281)) — **two LLM calls**: one to pick the most relevant entity from the full node list, one to answer using that entity's 1-hop neighborhood. Falls back to `_string_distance` fuzzy match if the LLM returns a name that isn't in the graph.
   - `global_search` ([line 339](graphrag_pipeline.py#L339)) — **one LLM call** over the concatenated community summaries.

### LLM injection contract
Every LLM-using function takes an `llm_call_fn: (prompt: str) -> str` argument. Swapping `mock_llm_call` for a real provider (Claude/OpenAI/etc.) is the only integration point — there is no client abstraction or config layer. The mock at [graphrag_pipeline.py:461](graphrag_pipeline.py#L461) routes by string-matching the prompt; real LLMs are expected to obey the JSON-only output rule baked into `EXTRACTION_PROMPT`.

### Graph data model
- Nodes: `name` (id), `type` (service/database/team/person/tool/infrastructure/unknown), `description` (merged), `community` (int).
- Edges: `types` (list of relationship strings), `descriptions` (list, parallel to types). Undirected — direction information from extraction is lost at graph build time.

`export_graph_data` ([line 367](graphrag_pipeline.py#L367)) serializes the graph + communities + summaries to a single JSON file for downstream visualization.
