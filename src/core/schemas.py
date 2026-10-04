from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(min_length=5, description="User question for the active project")


class RAGResponse(BaseModel):
    answer: str = Field(description="Direct answer in 2-4 sentences")
    evidence: str = Field(description="Supporting evidence summary")
    sources: list[str] = Field(description="Source documents cited")
    confidence: str = Field(description="high, moderate, or low")
    disclaimer: str = Field(description="Domain-specific disclaimer")

class HealthResponse(BaseModel):
    project: str
    collection_name: str
    collection_ready: bool


class SourceFileResponse(BaseModel):
    name: str
    size_bytes: int
    modified_at: datetime



class PubMedQuerySummaryResponse(BaseModel):
    query: str
    document_count: int
    chunk_count: int

class PubMedStatusResponse(BaseModel):
    enabled: bool
    configured_queries: list[str]
    configured_query_limit: int
    configured_max_results: int
    indexed_query_summaries: list[PubMedQuerySummaryResponse]
    indexed_document_count: int
    indexed_chunk_count: int

class SourceListResponse(BaseModel):
    sources: list[SourceFileResponse]
    pubmed: PubMedStatusResponse

class SourceMutationResponse(BaseModel):
    message: str
    source: SourceFileResponse | None = None


class ReindexResponse(BaseModel):
    message: str
    indexed_documents: int
    source_count: int
    collection_name: str



class EvalMetricResultResponse(BaseModel):
    name: str
    score: float | None
    threshold: float | None
    success: bool
    reason: str | None = None
    error: str | None = None


class EvalCaseResultResponse(BaseModel):
    id: str
    query: str
    expected_answer: str
    actual_answer: str
    sources: list[str]
    retrieval_context: list[str]
    metrics: list[EvalMetricResultResponse]
    success: bool

class EvalSummaryResponse(BaseModel):
    project: str
    collection_name: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    dataset_size: int
    passed_cases: int
    failed_cases: int
    success_rate: float
    success: bool


class EvalRunResponse(BaseModel):
    summary: EvalSummaryResponse
    cases: list[EvalCaseResultResponse]


class GuardrailStatusResponse(BaseModel):
    enabled: bool
    prompt_guard_model: str
    safeguard_model: str
    prompt_guard_threshold: float


class GuardrailInputTestRequest(BaseModel):
    question: str = Field(min_length=1, description="Question to run through the input guardrail")


class GuardrailOutputTestRequest(BaseModel):
    question: str = Field(min_length=1, description="Question paired with the answer being tested")
    answer: str = Field(min_length=1, description="Candidate answer to run through the output guardrail")


class GuardrailTestResponse(BaseModel):
    allowed: bool
    reason: str | None = None



@dataclass(frozen=True)
class QueryArtifacts:
    response: RAGResponse
    retrieval_context: list[str]

