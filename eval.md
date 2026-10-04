# MedRAG Eval and Runbook

This guide explains how the project runs, how evaluation works, and which commands to use in order.

## 1) What this project does

This app is a RAG (Retrieval-Augmented Generation) system for medical guideline Q&A.

Main parts:
- `ui` → Streamlit web app
- `api` → FastAPI backend
- `qdrant` → vector database for search
- `indexer` → one-time setup job that loads and indexes documents

The Docker Compose stack wires them together.

---

## 2) Prerequisites

Before starting, make sure:
- Docker Desktop is installed and running
- Python 3.11+ is available
- `uv` is installed
- project root is the current directory

Check the repo root:

```powershell
cd F:\AI_Project\MedRAG_live-feature-io-guardrails
```

---

## 3) Start the application

From the repo root, run:

```powershell
docker compose up --build
```

This starts:
- Qdrant
- API
- UI
- indexer

What happens:
- `qdrant` starts first
- `indexer` waits for Qdrant
- `indexer` runs the MedRAG indexing step
- `api` starts after indexing setup
- `ui` starts and exposes the browser app

After startup, open:

- UI: http://localhost:8501
- API docs: http://localhost:8000/docs
- Qdrant dashboard: http://localhost:6333/dashboard

### If a container naming conflict happens

Sometimes old containers stay behind and Docker refuses to reuse names.

Run:

```powershell
docker ps -aq --filter "name=medrag_live-feature-io-guardrails" | ForEach-Object { docker rm -f $_ }
docker compose down --remove-orphans
docker compose up --build
```

This clears the stale project containers and restarts cleanly.

---

## 4) Understand the container roles

### `medrag_live-feature-io-guardrails-qdrant-1`
This is the vector database. It stores chunks and embeddings used for retrieval.

### `medrag_live-feature-io-guardrails-indexer-1`
This is a setup job. It loads project data and builds the vector collection.

It is expected to run once and then exit successfully.

Example log message:

```text
Collection 'medrag_collection_bge_small' already exists for project 'medrag'. Skipping reindex.
```

If exit code is `0`, that means it finished successfully.

### `medrag_live-feature-io-guardrails-api-1`
This is the main backend. It serves query, upload, reindex, and eval APIs.

### `medrag_live-feature-io-guardrails-ui-1`
This is the Streamlit frontend. It talks to the API over HTTP.

---

## 5) How to know the app is running

Run:

```powershell
docker compose ps
```

You want to see services in `Up` state.

Also check the terminal logs during startup:

```powershell
docker compose logs -f
```

Look for:
- Qdrant listening on port 6333
- API showing `Uvicorn running on http://0.0.0.0:8000`
- UI showing `Local URL: http://localhost:8501`

---

## 6) Run the test suite

This project uses `uv` and the dev dependencies.

From the project root:

```powershell
uv run --extra dev pytest tests/
```

This runs all tests under the `tests/` folder.

For a single test file:

```powershell
uv run --extra dev pytest tests/core/test_evals.py
```

For a specific test:

```powershell
uv run --extra dev pytest tests/core/test_evals.py -k run_medrag_eval
```

### What the tests do

The test file `tests/core/test_evals.py` checks:
- eval run result is created correctly
- evaluation saves the latest result
- failed metrics are marked as failed
- metric names and thresholds are generated correctly

---

## 7) Run the MedRAG evaluation

The README explains that this is a DeepEval gold-dataset evaluation, not a normal pytest test.

### Option A: use the UI
1. Open http://localhost:8501
2. Open the `Eval Results` tab
3. Click `Run MedRAG eval`

### Option B: call the API manually

```powershell
curl -X POST http://localhost:8000/evals/medrag/run
```

Then read the saved result:

```powershell
curl http://localhost:8000/evals/medrag/latest
```

### Option C: use Python directly

```powershell
uv run python -c "from src.core.service import RAGService; print('ready')"
```

This is not the main evaluation path, but it shows the project can be imported in the project environment.

---

## 8) Understand the evaluation flow

The eval process works like this:

1. Check whether the vector collection exists
2. Load the dataset from the golden JSON file
3. Query the system for each dataset question
4. Compare answer + retrieved context against expected output
5. Run DeepEval metrics
6. Save results to the latest JSON file
7. Return summary and case-level results

The code for this lives in:
- `src/core/evals.py`
- `src/api/main.py`

The result is saved to a project data directory, typically under:
- `src/projects/medrag/data/evals/`

---

## 9) Example run sequence

Use this sequence when starting fresh:

```powershell
cd F:\AI_Project\MedRAG_live-feature-io-guardrails

docker compose up --build

# wait until ui and api show started

uv run --extra dev pytest tests/

# open browser to UI
# click Eval Results -> Run MedRAG eval
```

This is the full flow:
- start services
- verify app is up
- run tests
- run evaluation from UI or API
- inspect result

---

## 10) Common status checks

### Check whether container is running

```powershell
docker compose ps
```

### Check logs

```powershell
docker compose logs -f
```

### Check if API responds

```powershell
curl http://localhost:8000/health
```

### Check if UI responds

Open in browser:

```text
http://localhost:8501
```

### Check if tests passed

```powershell
uv run --extra dev pytest tests/
```

Success means exit code `0` and all tests passed.

---

## 11) Summary

The order to remember is:

1. Start Docker stack
2. Wait for app services to be ready
3. Run tests with `uv run --extra dev pytest tests/`
4. Run MedRAG eval through UI or API
5. Check latest results in the Eval Results tab or `/evals/medrag/latest`

If the app is running, the important endpoints are:
- `http://localhost:8501`
- `http://localhost:8000/docs`
- `http://localhost:6333/dashboard`

This is the basic lifecycle of the project.
