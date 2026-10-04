from __future__ import annotations

import logging
import os
from threading import RLock

from fastapi import FastAPI, File, HTTPException, UploadFile

from src.core.schemas import (
    EvalRunResponse,
    GuardrailInputTestRequest,
    GuardrailOutputTestRequest,
    GuardrailStatusResponse,
    GuardrailTestResponse,
    HealthResponse,
    PubMedQuerySummaryResponse,
    PubMedStatusResponse,
    QueryRequest,
    RAGResponse,
    ReindexResponse,
    SourceFileResponse,
    SourceListResponse,
    SourceMutationResponse,
)
from src.core.evals import load_latest_eval_result, run_medrag_eval
from src.core.guardrails import check_prompt_injection, check_safeguard_policy
from src.core.service import RAGService
from src.core.settings import get_settings
from src.core.source_manager import SourceManager


logger = logging.getLogger(__name__)
settings = get_settings()
service = RAGService.from_project_name(settings.active_project, settings=settings)
source_manager = SourceManager(service.config)
service_lock = RLock()

app = FastAPI(title="RAG Toolkit API")


@app.on_event("startup")
def warm_query_stack() -> None:
    if not service.collection_ready():
        return
    try:
        service.ensure_index_loaded()
        logger.info("MedRAG query stack warmed for collection '%s'.", service.config.collection_name)
    except Exception:
        logger.exception("Failed to warm MedRAG query stack during startup.")



@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        project=service.config.name,
        collection_name=service.config.collection_name,
        collection_ready=service.collection_ready(),
    )




def _pubmed_status_payload() -> PubMedStatusResponse:
    ingestor = service.definition.ingestor_cls(service.config)
    configured_queries = list(getattr(ingestor, "pubmed_queries", ()))
    configured_query_limit = int(os.getenv("PUBMED_QUERY_LIMIT", "1"))
    default_max_results = int(getattr(ingestor, "pubmed_max_results", 5))
    configured_max_results = int(os.getenv("PUBMED_MAX_RESULTS", str(default_max_results)))
    status = source_manager.pubmed_status(
        settings=service.settings,
        collection_name=service.config.collection_name,
        configured_queries=configured_queries,
        configured_query_limit=configured_query_limit,
        configured_max_results=configured_max_results,
    )
    return PubMedStatusResponse(
        enabled=status.enabled,
        configured_queries=status.configured_queries,
        configured_query_limit=status.configured_query_limit,
        configured_max_results=status.configured_max_results,
        indexed_query_summaries=[
            PubMedQuerySummaryResponse.model_validate(summary.__dict__)
            for summary in status.indexed_query_summaries
        ],
        indexed_document_count=status.indexed_document_count,
        indexed_chunk_count=status.indexed_chunk_count,
    )


@app.get("/sources", response_model=SourceListResponse)
def list_sources() -> SourceListResponse:
    return SourceListResponse(
        sources=[SourceFileResponse.model_validate(record.__dict__) for record in source_manager.list_sources()],
        pubmed=_pubmed_status_payload(),
    )

@app.post("/sources/upload", response_model=SourceMutationResponse)
async def upload_source(file: UploadFile = File(...)) -> SourceMutationResponse:
    try:
        content = await file.read()
        record = source_manager.save_source(file.filename or "", content)
        return SourceMutationResponse(
            message=f"Uploaded '{record.name}'. Rebuild the index to make it queryable.",
            source=SourceFileResponse.model_validate(record.__dict__),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/sources/{filename}", response_model=SourceMutationResponse)
def delete_source(filename: str) -> SourceMutationResponse:
    try:
        source_manager.delete_source(filename)
        return SourceMutationResponse(
            message=f"Deleted '{filename}'. Rebuild the index to remove it from retrieval."
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/sources/reindex", response_model=ReindexResponse)
def reindex_sources() -> ReindexResponse:
    try:
        with service_lock:
            service.index = None
            indexed_documents = service.build_index()
        return ReindexResponse(
            message=f"Rebuilt collection '{service.config.collection_name}'.",
            indexed_documents=indexed_documents,
            source_count=len(source_manager.list_sources()),
            collection_name=service.config.collection_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc



@app.post("/query", response_model=RAGResponse)
def query(payload: QueryRequest) -> RAGResponse:
    input_check = check_prompt_injection(payload.question, service.settings)
    if not input_check.allowed:
        raise HTTPException(
            status_code=422, detail=f"Blocked by guardrail (input): {input_check.reason}"
        )

    try:
        with service_lock:
            result = service.query(payload.question)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    output_check = check_safeguard_policy(
        payload.question, result.response.answer, service.config.safeguard_policy, service.settings
    )
    if not output_check.allowed:
        raise HTTPException(
            status_code=422, detail=f"Blocked by guardrail (output): {output_check.reason}"
        )

    return result.response


@app.get("/guardrails/status", response_model=GuardrailStatusResponse)
def guardrail_status() -> GuardrailStatusResponse:
    return GuardrailStatusResponse(
        enabled=bool(service.settings.groq_api_key),
        prompt_guard_model=service.settings.groq_prompt_guard_model,
        safeguard_model=service.settings.groq_safeguard_model,
        prompt_guard_threshold=service.settings.prompt_guard_threshold,
    )


@app.post("/guardrails/test-input", response_model=GuardrailTestResponse)
def test_input_guardrail(payload: GuardrailInputTestRequest) -> GuardrailTestResponse:
    result = check_prompt_injection(payload.question, service.settings)
    return GuardrailTestResponse(allowed=result.allowed, reason=result.reason)


@app.post("/guardrails/test-output", response_model=GuardrailTestResponse)
def test_output_guardrail(payload: GuardrailOutputTestRequest) -> GuardrailTestResponse:
    result = check_safeguard_policy(
        payload.question, payload.answer, service.config.safeguard_policy, service.settings
    )
    return GuardrailTestResponse(allowed=result.allowed, reason=result.reason)


@app.post("/evals/medrag/run", response_model=EvalRunResponse)
def run_medrag_eval_endpoint() -> EvalRunResponse:
    try:
        with service_lock:
            return run_medrag_eval(service)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc



@app.get("/evals/medrag/latest", response_model=EvalRunResponse)
def latest_medrag_eval() -> EvalRunResponse:
    result = load_latest_eval_result(service)
    if result is None:
        raise HTTPException(status_code=404, detail="No local MedRAG eval results are available yet.")
    return result
