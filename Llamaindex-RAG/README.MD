# Telecom Incident RAG Assistant

A local Retrieval-Augmented Generation (RAG) application built with **LlamaIndex, Ollama, and ChromaDB**.

The application uses historical telecom incidents as a knowledge base. When a new customer issue is entered, the system retrieves semantically similar historical incidents and uses a local LLM to suggest likely root causes and resolutions.

This project was built to explore the complete RAG lifecycle:

**Load → Chunk → Embed → Persist → Retrieve → Augment → Generate → Evaluate**

The current implementation is a local, terminal-based assistant. It keeps the
vector index on disk, supports repeatable incremental ingestion, and exposes
the retrieved incident IDs, categories, and similarity scores alongside each
answer for traceability.

---

## Architecture

### RAG Query Pipeline

```text
                         USER QUERY
                            │
                            ▼
                  "Activation is blocked
                   by another open order"
                            │
                            ▼
                 ┌─────────────────────┐
                 │  nomic-embed-text   │
                 │      Ollama         │
                 └──────────┬──────────┘
                            │
                      Query Embedding
                            │
                            ▼
                 ┌─────────────────────┐
                 │      ChromaDB       │
                 │                     │
                 │ Persistent vectors  │
                 │ + metadata          │
                 └──────────┬──────────┘
                            │
                    Similarity Search
                            │
                            ▼
                    Top-K Incidents
                            │
               ┌────────────┼────────────┐
               ▼            ▼            ▼
            INC1001      INC1004      INC1010
               │            │            │
               └────────────┼────────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │     LlamaIndex      │
                 │    Query Engine     │
                 │                     │
                 │ Query + Retrieved   │
                 │      Context        │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │      llama3.2       │
                 │       Ollama        │
                 └──────────┬──────────┘
                            │
                            ▼
                    Generated Answer
                            │
                  ┌─────────┴─────────┐
                  ▼                   ▼
            Likely Root Cause    Recommended
                                  Resolution
```

---

## Technology Stack

| Component | Technology | Responsibility |
|---|---|---|
| RAG framework | LlamaIndex | Document processing, retrieval and query orchestration |
| Embedding model | nomic-embed-text | Converts incident text and queries into vectors |
| Model runtime | Ollama | Runs embedding and generative models locally |
| Vector database | ChromaDB | Persists and searches vector embeddings |
| Generative LLM | llama3.2 | Generates answers from retrieved evidence |
| Evaluation | Python | Measures retrieval quality using a golden dataset |

### Current query behavior

`main.py` loads the existing ChromaDB index, asks for a customer issue, and
optionally accepts an exact incident category filter. The query engine retrieves
the top three matching incidents and sends only that retrieved context to the
local `llama3.2` model. Answers are constrained to this format:

```text
Likely Root Cause:
<root cause>

Recommended Resolution:
<resolution>
```

The application also prints the retrieved incident ID, category, and similarity
score so the generated answer can be checked against its evidence.

---

## Project Structure

```text
Llamaindex-RAG/
│
├── data/
│   ├── incidents.json
│   └── evaluation_dataset.json
│
├── src/
│   ├── __init__.py
│   ├── loader.py
│   ├── indexer.py
│   ├── retriever.py
│   ├── query_engine.py
│   ├── filtered_retriever.py
│   └── reranker.py
│
├── chroma_db/
│
├── build_index.py
├── ingest_incidents.py
├── check_db.py
├── evaluation.py
├── inspect_nodes.py
├── main.py
├── requirements.txt
└── README.md
```

---

# How the RAG Pipeline Works

## 1. Load Historical Incidents

Historical telecom incidents are stored in:

```text
data/incidents.json
```

Example:

```json
{
  "incident_id": "INC1001",
  "category": "Activation",
  "error_code": "ACT-500",
  "description": "Customer activation failed due to pending order.",
  "root_cause": "Existing pending order blocked activation.",
  "resolution": "Clear pending order and retry activation."
}
```

`loader.py` converts each source record into a LlamaIndex `Document`.

Metadata such as the incident ID, category and error code is retained for filtering and traceability.

---

## 2. Documents → Nodes

LlamaIndex converts Documents into Nodes.

```text
Document
   │
   ▼
Node / Chunk
```

For the current synthetic dataset, each incident is small enough to remain a single node.

With larger documents, LlamaIndex can split a document into multiple chunks before embedding.

---

## 3. Generate Embeddings

The project uses the local Ollama model:

```text
nomic-embed-text
```

Conceptually:

```text
Incident text
      │
      ▼
nomic-embed-text
      │
      ▼
[0.12, -0.34, 0.82, ...]
```

The resulting vector represents the semantic meaning of the incident.

---

## 4. Persist Embeddings in ChromaDB

Instead of regenerating document embeddings every time the application starts, vectors are persisted in ChromaDB.

```text
Historical Incidents
        │
        ▼
   LlamaIndex
        │
        ▼
nomic-embed-text
        │
        ▼
     Vectors
        │
        ▼
┌──────────────────┐
│     ChromaDB     │
│                  │
│ Vector           │
│ Document/Node    │
│ Metadata         │
│ Incident ID      │
└──────────────────┘
```

The application can therefore restart and reuse previously generated vectors.

Only the incoming user query needs to be embedded during retrieval.

---

# Retrieval

Suppose the user asks:

```text
Customer activation is blocked because another order is already open.
```

The query is converted into an embedding using the same embedding model.

```text
User Query
    │
    ▼
nomic-embed-text
    │
    ▼
Query Vector
    │
    ▼
ChromaDB
    │
    ▼
Vector Similarity Search
```

ChromaDB returns the most semantically similar historical incidents.

Example:

```text
1. INC1001 - Activation
2. INC1004 - Pending Order
3. INC1010 - Activation
```

This is the **Retrieval** part of RAG.

---

# Augmentation

The retrieved incidents are added to the LLM prompt as context.

Conceptually:

```text
SYSTEM INSTRUCTION

Use only the supplied historical incidents.

CONTEXT

INC1001
Root Cause:
Existing pending order blocked activation.

Resolution:
Clear pending order and retry activation.

INC1004
Root Cause:
Conflicting open order.

Resolution:
Resolve conflicting order before resubmission.

USER QUERY

Customer activation is blocked because
another order is already open.
```

This is the **Augmented** part of Retrieval-Augmented Generation.

---

# Generation

The augmented prompt is sent to the local `llama3.2` model through Ollama.

```text
Retrieved Evidence
        +
     User Query
        ↓
    llama3.2
        ↓
Likely Root Cause
        +
Recommended Resolution
```

The LLM therefore generates an answer grounded in historical incident evidence rather than relying only on its pretrained knowledge.

---

# Persistent vs In-Memory Indexing

Initial implementation:

```text
Application starts
      ↓
Load all incidents
      ↓
Embed every incident
      ↓
Create index in memory
      ↓
Query
      ↓
Application stops
      ↓
Index disappears
```

Current implementation:

```text
              FIRST INGESTION

incidents.json
      ↓
Generate embeddings
      ↓
   ChromaDB
      ↓
Persist vectors


              QUERY TIME

User Query
    ↓
Generate query embedding
    ↓
Load/search existing ChromaDB vectors
    ↓
Top-K incidents
    ↓
LLM
```

Existing document embeddings therefore do not need to be regenerated for every application run.

---

# Incremental Ingestion

A production knowledge base should not re-embed every historical incident whenever new data arrives.

Instead, the ingestion pipeline determines whether a record is:

```text
                    SOURCE INCIDENT
                           │
                           ▼
                    Incident ID exists?
                           │
                  ┌────────┴────────┐
                  │                 │
                 NO                YES
                  │                 │
                  ▼                 ▼
               INSERT         Compare content
                                      │
                              ┌───────┴───────┐
                              │               │
                            SAME           CHANGED
                              │               │
                              ▼               ▼
                            SKIP           RE-EMBED
                                              │
                                              ▼
                                            UPDATE
```

---

## Content Hashing

Each incident can contain a SHA-256 hash representing the retrieval-relevant content.

For example:

```text
Description
+
Root Cause
+
Resolution
+
Category
+
Error Code
+
Keywords
        ↓
      SHA-256
        ↓
content_hash
```

During synchronization:

```text
Same incident ID
+
Same content hash
        ↓
SKIP
```

while:

```text
Same incident ID
+
Different content hash
        ↓
Content changed
        ↓
Generate new embedding
        ↓
Update vector database
```

This provides idempotent ingestion while avoiding unnecessary embedding operations.

---

# Production-Scale Incremental Sync

The current project uses a small JSON dataset.

For a production system containing millions of incidents, reading every record during every synchronization would be inefficient.

A source system would normally expose a modification timestamp such as:

```text
updated_at
```

The ingestion service can request only records changed since its last successful synchronization.

```text
Source System
1,000,000 incidents
       │
       │ updated_at > last_sync
       ▼
2,000 changed/new records
       │
       ▼
Content Hash Check
       │
       ├── unchanged → SKIP
       │
       ├── new → EMBED + INSERT
       │
       └── changed → RE-EMBED + UPDATE
       │
       ▼
Vector Database
```

At larger scale, the same pipeline can also become event-driven:

```text
ServiceNow / Source System
          │
          │ Incident Updated Event
          ▼
      Message Queue
          │
          ▼
    Ingestion Worker
          │
          ▼
   Change Detection
          │
          ▼
     Embedding Model
          │
          ▼
      Vector DB
```

---

# Retrieval Evaluation

The project includes a golden dataset:

```text
data/evaluation_dataset.json
```

Each test contains:

```json
{
  "query": "customer tried to activate but another transaction is still hanging",
  "expected_incidents": [
    "INC1001",
    "INC1004"
  ]
}
```

Retrieval quality is evaluated independently from LLM generation.

The project currently measures:

### Recall@K

Measures how many expected relevant incidents were retrieved within the top K results.

Example:

```text
Expected:

INC1001
INC1004

Top 3:

INC1001
INC1002
INC1010

Recall@3 = 1 / 2 = 0.50
```

### Hit Rate@K

Measures whether at least one relevant incident appears within the top K results.

For the example above:

```text
Hit@3 = 1
```

### Mean Reciprocal Rank (MRR)

Measures how highly the first relevant result appears.

If the first relevant incident is ranked first:

```text
Reciprocal Rank = 1 / 1 = 1.0
```

---

# Current Evaluation Results

Using the current synthetic golden dataset:

| Metric | Result |
|---|---:|
| Recall@3 | 0.90 |
| Hit Rate@3 | 1.00 |
| MRR | 1.00 |

The evaluation also revealed a useful semantic retrieval gap: one query expects both `INC1001` and `INC1004`, but only `INC1001` currently appears in the top three.

This demonstrates why retrieval quality should be measured independently rather than assuming a RAG system works because the generated answer looks reasonable.

---

# Experiments

## Metadata Filtering

Metadata filtering was tested using incident categories.

Example:

```text
category = Activation
```

This successfully restricts retrieval to Activation incidents.

However, hard filtering can also remove useful cross-category evidence. For example, an Activation problem may actually be caused by a Pending Order incident.

Metadata filtering should therefore be used when the constraint is genuinely required.

---

## Metadata Enrichment

Category, error code and domain terminology were added to the text used for embeddings.

This improved ranking behavior on parts of the golden dataset.

It demonstrated that embedding quality depends not only on the embedding model, but also on the information supplied to that model.

---

## LLM Reranking

An experiment was performed using LlamaIndex `LLMRerank` with the local `llama3.2` model.

The reranking experiment degraded retrieval quality and was therefore not integrated into the main pipeline.

This reinforced an important engineering principle:

> Additional architecture does not automatically improve a RAG system. Changes should be evaluated against a stable benchmark.

A dedicated reranker or cross-encoder would be a better future experiment.

---

# Running the Project

## Install Dependencies

```bash
pip install -r requirements.txt
```

Install and start [Ollama](https://ollama.com), then pull the two models used by
the pipeline:

```bash
ollama serve
ollama pull nomic-embed-text
ollama pull llama3.2
```

The project requires:

```text
nomic-embed-text
llama3.2
```

---

## Build the Initial Vector Index

```bash
python build_index.py
```

This loads the source incidents, generates embeddings and persists them in ChromaDB.

Run this once for a new or empty `chroma_db/` directory. The command refuses to
insert into a non-empty collection, which prevents accidental duplicate vectors.

---

## Inspect ChromaDB

```bash
python check_db.py
```

This displays the number of stored vectors and incident metadata.

---

## Run Incremental Ingestion

```bash
python ingest_incidents.py
```

The initial index must already exist before synchronization. Each incident is
identified by `incident_id` and compared using a SHA-256 hash of its indexed
content. Removed source incidents are not automatically deleted; delete or
rebuild the local index if removals must be reflected.

The synchronization process can:

```text
NEW       → INSERT
CHANGED   → RE-EMBED + UPDATE
UNCHANGED → SKIP
```

---

## Run the RAG Application

```bash
python main.py
```

When prompted, press Enter at the category prompt to search all incidents, or
enter an exact category such as `Activation`.

Example query:

```text
customer activation is blocked because another order is already open
```

---

## Run Retrieval Evaluation

```bash
python evaluation.py
```

This executes the golden dataset against the persisted ChromaDB index and reports Recall@K, Hit Rate@K and MRR.

---

# Key Engineering Lessons

This project demonstrates that a production RAG system is more than:

```text
Documents → Embeddings → LLM
```

A more complete architecture is:

```text
                    DATA / INGESTION

Source Data
    ↓
Documents
    ↓
Chunking
    ↓
Change Detection
    ↓
Embedding Model
    ↓
Vector Database


                    QUERY / RAG

User Query
    ↓
Query Embedding
    ↓
Vector Retrieval
    ↓
Top-K Evidence
    ↓
Prompt Augmentation
    ↓
LLM Generation
    ↓
Grounded Response


                    QUALITY

Golden Dataset
    ↓
Retrieval Evaluation
    ↓
Recall@K / Hit Rate / MRR
    ↓
Identify Retrieval Gaps
    ↓
Improve → Measure → Keep/Reject
```

The project also demonstrates several production-oriented principles:

- Persist embeddings instead of rebuilding them for every application run.
- Separate retrieval quality from generation quality.
- Treat similarity scores as ranking signals rather than probabilities.
- Preserve source metadata for filtering and traceability.
- Use idempotent ingestion.
- Re-embed records only when retrieval-relevant content changes.
- Use incremental synchronization for large datasets.
- Evaluate architectural changes against a stable golden dataset.
- Avoid overfitting retrieval behavior to a tiny synthetic dataset.

---

# Future Improvements

Potential extensions include:

- Larger real-world telecom incident datasets
- Hybrid semantic + keyword/BM25 search
- Dedicated cross-encoder reranking
- ServiceNow/API-based ingestion
- `updated_at` incremental synchronization
- Event-driven ingestion
- Retrieval and generation observability
- Automated RAG regression testing
- Production vector database deployment
- API layer using FastAPI
- Containerized deployment

---

## Purpose

This repository is a learning and portfolio project demonstrating the design, implementation, persistence, evaluation and incremental ingestion patterns behind a Retrieval-Augmented Generation system using **LlamaIndex + Ollama + ChromaDB**.
