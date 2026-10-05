# MedRAG Run Guide

This guide covers starting the app, adding guideline PDFs, asking a question, and running the golden evaluation. Run commands from the repository root.

## 1. Start the application

Make sure Docker Desktop is running and the required environment values are configured in `.env`. PDF parsing requires `LLAMA_CLOUD_API_KEY`; answer generation requires `OPENAI_API_KEY`.

```powershell
docker compose up --build
```

Compose starts Qdrant, runs the one-time indexer, then starts the API and Streamlit UI. Check service status with:

```powershell
docker compose ps
```

Open the UI at <http://localhost:8501>. The API health endpoint is <http://localhost:8000/health>.

## 2. Upload guideline PDFs

1. In the UI, open **Uploaded Sources**.
2. Choose one or more PDF files under **Add guideline PDFs**.
3. Click **Upload and reindex** and wait for the success message.

The UI sends each file to `POST /sources/upload`. The API saves it under `src/projects/medrag/data/guidelines/`. After all files upload, the UI calls `POST /sources/reindex` to rebuild the index. This directory is shared with the API and indexer containers through a Docker bind mount.

Reindexing replaces the Qdrant collection with a rebuilt collection containing the configured PDF, PubMed, and bootstrap sources. If reindexing fails after upload, the PDF remains saved; fix the error and use **Rebuild index from current sources** in the UI.

PDF parsing uses LlamaParse and requires `LLAMA_CLOUD_API_KEY` whenever guideline PDFs are present. PubMed ingestion is controlled by `PUBMED_ENABLED`, `PUBMED_QUERY_LIMIT`, and `PUBMED_MAX_RESULTS`.

## 3. Ask a question

Open **Ask Questions**, enter a clinical question, and click **Ask**. The API validates the request, runs the configured input guardrail, retrieves relevant chunks from Qdrant, generates an answer with the configured OpenAI model, and runs the output safeguard. A successful response includes the answer, evidence, sources, confidence, and disclaimer.

The workflow diagram is in [docs/application_workflow.md](docs/application_workflow.md).

## 4. Run the golden evaluation

The golden evaluation uses the indexed collection and questions in `eval/medrag/golden_dataset.json`.

In the UI, open **Eval Results** and click **Run MedRAG eval**. Alternatively, call the API from PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/evals/medrag/run
Invoke-RestMethod -Method Get -Uri http://localhost:8000/evals/medrag/latest
```

The latest result is saved under `src/projects/medrag/data/evals/`.

## 5. Run automated tests

Automated tests are separate from the live golden evaluation. From the repository root:

```powershell
uv run --extra dev pytest tests/
```

To run only the evaluator unit tests:

```powershell
uv run --extra dev pytest tests/core/test_evals.py
```

## Troubleshooting

- **UI cannot connect:** confirm `docker compose ps` shows the API and UI running; inspect logs with `docker compose logs -f api ui`.
- **Upload works but reindex fails:** inspect `docker compose logs api`. If guideline PDFs are present, verify `LLAMA_CLOUD_API_KEY` is configured for the API container.
- **No collection or query reports that indexing is needed:** use **Rebuild index from current sources** in **Uploaded Sources** and wait for success.
- **Evaluation fails because the collection is missing:** rebuild the index before running the evaluation.
- **Latest evaluation is absent:** run the evaluation once; the latest-results endpoint returns 404 until a result has been saved.

docker compose up -d qdrant

uv run uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000

uv run streamlit run src/ui/app.py --server.port 8501

uv run python -m src.cli index --project medrag

sbse pahle ye call hoga data load krne ke liye
uv run python -m src.cli index --project medrag


evalution ke liye
______________________

uv run --extra dev pytest eval/medrag/test_medrag.py -m integration