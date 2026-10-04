# MedRAG

Clinical guideline Q&A powered by a shared, plugin-based RAG toolkit. One domain-agnostic core (`src/core/`) drives retrieval, generation, evaluation, and safety guardrails; a project plugin (`src/projects/medrag/`) supplies the domain-specific ingestion and policy. Three thin interfaces — CLI, FastAPI, and a Streamlit UI — all sit on top of the same `RAGService`.

> **Branch scope:** `feature/io-guardrails` adds API-boundary input and output safety checks, diagnostic endpoints, and a Guardrails UI tab. These controls fail open and do not run for CLI or evaluation calls; review [Guardrails](#guardrails) before production use.

The illustrated [MedRAG project report](output/pdf/MedRAG_Project_Report.pdf) gives a concise problem statement, operating model, architecture, implementation map, safety posture, product walkthrough, and recommended next steps.

MedRAG is an educational evidence assistant. It does not diagnose, prescribe, replace a clinician, or establish that its indexed guidance is complete or current.

## Stack

- **Vector store**: Qdrant
- **Embeddings**: FastEmbed (`BAAI/bge-small-en-v1.5`, local, no API key needed)
- **Generation**: OpenAI (`gpt-4o-mini` by default)
- **Document parsing**: LlamaParse (guideline PDFs) + PubMed (`PubmedReader`)
- **Guardrails**: Groq-hosted Prompt Guard (input) and a policy-driven safeguard model (output)
- **Eval**: DeepEval (faithfulness, answer relevancy, contextual relevancy) against a golden dataset

## Architecture

```mermaid
flowchart TB
  subgraph IF["Interfaces"]
    CLI["CLI<br/>src/cli.py"]
    API["FastAPI<br/>src/api/main.py"]
    UI["Streamlit UI<br/>src/ui/app.py"]
  end

  SVC["RAGService<br/>src/core/service.py"]

  subgraph CORE["Core pipeline — domain-agnostic"]
    IDXR["indexer.py"]
    RET["retriever.py"]
    GEN["generator.py"]
  end

  PROJ["projects.py<br/>PROJECTS registry"]

  subgraph PLUG["medrag plugin — domain-specific"]
    CFG["config.py<br/>MEDRAG_CONFIG"]
    ING["ingestor.py<br/>MedRAGIngestor"]
  end

  subgraph INFRA["Infrastructure"]
    QD[(Qdrant)]
    OAI["OpenAI API"]
    FE["fastembed"]
    GRQ["Groq (guardrails)"]
  end

  UI -->|HTTP JSON| API
  CLI --> SVC
  API --> SVC
  SVC --> IDXR
  SVC --> RET
  RET --> GEN
  SVC -->|resolves project by name| PROJ
  PROJ --> CFG
  PROJ --> ING
  IDXR -->|writes vectors| QD
  RET -->|reads vectors| QD
  RET -->|drafts answer| OAI
  IDXR -->|embeds chunks| FE
  API -->|input/output checks| GRQ
```

## Guardrails

Guardrails live **only** at the API boundary (`src/api/main.py`'s `/query` handler) — they wrap `RAGService.query()` rather than living inside it, so the CLI and the eval harness bypass both checks and are never affected by a guardrail false positive. Both guards are Groq-hosted models called via `src/core/guardrails.py` and **fail open**: a Groq timeout, auth error, or malformed response is logged and the request is allowed through rather than blocked, so a Groq outage degrades the app to unguarded behavior instead of taking query-answering down entirely.

```mermaid
flowchart TD
    A["User question"] --> L1

    subgraph L1["① Input Guardrail"]
        direction TB
        L1a["check_prompt_injection()"]
        L1b["Groq: meta-llama/llama-prompt-guard-2-86m"]
        L1c{"malicious score ≥ threshold?<br/>(default 0.5)"}
        L1a --> L1b --> L1c
    end

    L1c -->|"yes → block"| L1x["HTTP 422<br/>Blocked by guardrail (input)"]
    L1c -->|"no → allow"| L2

    subgraph L2["② Our Project — RAG Pipeline"]
        direction TB
        L2a["RAGService.query()"]
        L2b["Retrieve top-k chunks<br/>Qdrant vector store"]
        L2c["Generate answer<br/>OpenAI gpt-4o-mini"]
        L2a --> L2b --> L2c
    end

    L2 --> L3

    subgraph L3["③ Output Guardrail"]
        direction TB
        L3a["check_safeguard_policy()"]
        L3b["Groq: openai/gpt-oss-safeguard-20b<br/>policy = MEDRAG_CONFIG.safeguard_policy"]
        L3c{"violation == 1?"}
        L3a --> L3b --> L3c
    end

    L3c -->|"yes → block"| L3x["HTTP 422<br/>Blocked by guardrail (output)"]
    L3c -->|"no → allow"| R["HTTP 200<br/>RAGResponse returned to UI"]
```

The Streamlit **Guardrails** tab hits two dedicated diagnostic endpoints — `POST /guardrails/test-input` and `POST /guardrails/test-output` — that call each layer directly, skipping retrieval/generation entirely, so you can sanity-check guard behavior without burning an OpenAI call.

## Query flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit UI
    participant API as FastAPI /query
    participant GR as guardrails.py
    participant SVC as RAGService
    participant QD as Qdrant
    participant LLM as OpenAI

    User->>UI: asks a clinical question
    UI->>API: POST /query {question}
    API->>GR: check_prompt_injection()
    GR-->>API: allowed / blocked
    alt blocked
        API-->>UI: 422 Blocked by guardrail (input)
    else allowed
        API->>SVC: query(question)
        SVC->>QD: vector search, top_k
        QD-->>SVC: source nodes + metadata
        SVC->>LLM: system_prompt + context + question
        LLM-->>SVC: drafted answer
        SVC-->>API: RAGResponse
        API->>GR: check_safeguard_policy()
        GR-->>API: allowed / blocked
        alt blocked
            API-->>UI: 422 Blocked by guardrail (output)
        else allowed
            API-->>UI: 200 {answer, evidence, sources, confidence}
        end
    end
```

## Index build flow

Triggered by `rag-toolkit index --project medrag` (the Docker `indexer` service runs this once on startup, then exits).

```mermaid
flowchart TD
  A["CLI: index --project medrag"] --> B["RAGService.build_index()"]
  B --> C["MedRAGIngestor.ingest()"]

  subgraph LOAD["load_and_parse()"]
    C1["LlamaParse<br/>guideline PDFs"]
    C2["PubmedReader<br/>PubMed abstracts"]
    C3["bootstrap seed docs"]
  end
  C --> C1
  C --> C2
  C --> C3

  C1 --> D["enrich_metadata()<br/>tags source_org / specialty / evidence_type"]
  C2 --> D
  C3 --> D

  D --> E["core.indexer.build_index()"]
  E --> F["SentenceSplitter<br/>chunk_size / chunk_overlap"]
  F --> G["FastEmbed<br/>BAAI/bge-small-en-v1.5"]
  G --> H[(Qdrant collection<br/>medrag_collection_bge_small)]
```

`--skip-if-exists` short-circuits if the collection already exists.

## Deployment topology

```mermaid
flowchart LR
  subgraph COMPOSE["docker compose"]
    direction TB
    QD[("qdrant<br/>:6333")]
    IDX["indexer<br/>runs once, exits 0"]
    API["api<br/>:8000 uvicorn"]
    UI["ui<br/>:8501 streamlit"]
  end

  Browser(("browser")) -->|":8501"| UI
  Client(("API client")) -->|":8000"| API

  IDX -->|"waits for, then writes vectors"| QD
  API -->|"depends_on: indexer"| IDX
  API -->|"reads vectors"| QD
  UI -->|"API_BASE_URL=http://api:8000"| API
```

`ui` never touches Qdrant or `RAGService` directly — it's a pure HTTP client of `api`.

## Quick start

```bash
cp .env.example .env
# fill in OPENAI_API_KEY, LLAMA_CLOUD_API_KEY, and (optionally) GROQ_API_KEY
docker compose up -d
```

- UI: http://localhost:8501
- API docs: http://localhost:8000/docs

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ACTIVE_PROJECT` | `medrag` | Which registered project to serve |
| `OPENAI_API_KEY` | — | Required for generation |
| `LLAMA_CLOUD_API_KEY` | — | Required for LlamaParse (guideline PDFs) |
| `GROQ_API_KEY` | — | Optional; guardrails no-op and allow everything through if unset |
| `QDRANT_HOST` / `QDRANT_PORT` | `localhost` / `6333` | Vector store connection |
| `OPENAI_MODEL` | `gpt-4o-mini` | Generation model |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Local embedding model |
| `MAX_GUIDELINE_FILES` | `3` | Cap on guideline PDFs parsed per index build |
| `PUBMED_ENABLED` | `true` | Toggle PubMed ingestion |
| `PUBMED_QUERY_LIMIT` | `1` | How many of `MedRAGIngestor.pubmed_queries` actually run |
| `PUBMED_MAX_RESULTS` | `5` | Abstracts fetched per PubMed query |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1024` / `100` | Sentence splitter settings |
| `VECTOR_STORE_QUERY_MODE` | `default` | `default` or `hybrid` (dense+sparse) |
| `GROQ_PROMPT_GUARD_MODEL` | `meta-llama/llama-prompt-guard-2-86m` | Input guardrail model |
| `GROQ_SAFEGUARD_MODEL` | `openai/gpt-oss-safeguard-20b` | Output guardrail model |
| `PROMPT_GUARD_THRESHOLD` | `0.5` | Malicious-score cutoff for the input guardrail |
| `GUARDRAIL_TIMEOUT_SECONDS` | `2.0` | Per-guard-call timeout before failing open |

> ⚠️ `docker-compose.yml`'s `api` service does **not** pass through `PUBMED_ENABLED` / `PUBMED_QUERY_LIMIT` / `PUBMED_MAX_RESULTS` / `MAX_GUIDELINE_FILES` — only the one-shot `indexer` service does. Changing those in `.env` and reindexing via the UI's "Reindex" button (which hits the `api` container) will silently use the code defaults instead. Rerun the `indexer` service to pick up changes.

## API reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Project/collection readiness |
| `GET` | `/sources` | Uploaded PDFs + PubMed ingestion status |
| `POST` | `/sources/upload` | Upload a guideline PDF |
| `DELETE` | `/sources/{filename}` | Remove a guideline PDF |
| `POST` | `/sources/reindex` | Rebuild the Qdrant collection |
| `POST` | `/query` | Ask a question (runs both guardrails) |
| `GET` | `/guardrails/status` | Whether guardrails are enabled + configured models/threshold |
| `POST` | `/guardrails/test-input` | Run only the input guardrail on a question |
| `POST` | `/guardrails/test-output` | Run only the output guardrail on a question/answer pair |
| `POST` | `/evals/medrag/run` | Run the DeepEval golden-dataset suite |
| `GET` | `/evals/medrag/latest` | Latest local eval results |

## Development

```bash
uv run --extra dev pytest tests/
uv run --extra dev ruff check src/ tests/
```

CLI usage (bypasses guardrails — dev/debug tool):

```bash
uv run python -m src.cli index --project medrag --skip-if-exists
uv run python -m src.cli query "What is first-line therapy for hypertension?" --project medrag
```
