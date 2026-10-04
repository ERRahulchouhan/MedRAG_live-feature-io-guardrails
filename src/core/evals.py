from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from deepeval.test_case import LLMTestCase

from eval.shared.metrics import build_rag_metrics
from src.core.schemas import (
    EvalCaseResultResponse,
    EvalMetricResultResponse,
    EvalRunResponse,
    EvalSummaryResponse,
)
from src.core.service import RAGService

def _display_metric_name(metric: object) -> str:
    raw_name = getattr(metric, "name", None) or type(metric).__name__.removesuffix("Metric")
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", str(raw_name)).strip()
    return " ".join(spaced.split())

def _results_dir(service: RAGService) -> Path:
    return service.config.data_dir / "evals"

def _latest_results_path(service: RAGService) -> Path:
    return _results_dir(service) / f"{service.config.name}_latest.json"

def load_eval_dataset(service: RAGService) -> list[dict]:
    return json.loads(service.config.golden_dataset_path.read_text())

def load_latest_eval_result(service: RAGService) -> EvalRunResponse | None:
    path = _latest_results_path(service)
    if not path.exists():
        return None
    return EvalRunResponse.model_validate_json(path.read_text())

def save_latest_eval_result(service: RAGService, result: EvalRunResponse) -> Path:
    path = _latest_results_path(service)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2))
    return path

def run_medrag_eval(service: RAGService) -> EvalRunResponse:
    if not service.collection_ready():
        raise FileNotFoundError(
            f"Qdrant collection '{service.config.collection_name}' is missing. "
            "Run the indexing command first."
        )

    dataset = load_eval_dataset(service)
    started_at = datetime.now(UTC)
    case_results: list[EvalCaseResultResponse] = []

    for item in dataset:
        query_result = service.query(item["query"])
        test_case = LLMTestCase(
            input=item["query"],
            actual_output=query_result.response.answer,
            expected_output=item["expected_answer"],
            retrieval_context=query_result.retrieval_context,
        )

        metric_results: list[EvalMetricResultResponse] = []
        case_success = True
        for metric in build_rag_metrics():
            try:
                metric.measure(test_case, _show_indicator=False)
                metric_success = bool(getattr(metric, "success", False))
                metric_results.append(
                    EvalMetricResultResponse(
                        name=_display_metric_name(metric),
                        score=(
                            float(metric.score) if getattr(metric, "score", None) is not None else None
                        ),
                        threshold=(
                            float(metric.threshold)
                            if getattr(metric, "threshold", None) is not None
                            else None
                        ),
                        success=metric_success,
                        reason=getattr(metric, "reason", None),
                        error=getattr(metric, "error", None),
                    )
                )
                case_success = case_success and metric_success
            except Exception as exc:
                metric_results.append(
                    EvalMetricResultResponse(
                        name=_display_metric_name(metric),
                        score=None,
                        threshold=(
                            float(metric.threshold)
                            if getattr(metric, "threshold", None) is not None
                            else None
                        ),
                        success=False,
                        reason=None,
                        error=str(exc),
                    )
                )
                case_success = False

        case_results.append(
            EvalCaseResultResponse(
                id=item["id"],
                query=item["query"],
                expected_answer=item["expected_answer"],
                actual_answer=query_result.response.answer,
                sources=query_result.response.sources,
                retrieval_context=query_result.retrieval_context,
                metrics=metric_results,
                success=case_success,
            )
        )
    completed_at = datetime.now(UTC)
    passed_cases = sum(1 for case in case_results if case.success)
    failed_cases = len(case_results) - passed_cases

    summary = EvalSummaryResponse(
        project=service.config.name,
        collection_name=service.config.collection_name,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=round((completed_at - started_at).total_seconds(), 2),
        dataset_size=len(case_results),
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        success_rate=round(passed_cases / len(case_results), 4) if case_results else 0.0,
        success=failed_cases == 0,
    )
    result = EvalRunResponse(summary=summary, cases=case_results)
    save_latest_eval_result(service, result)
    return result

    
