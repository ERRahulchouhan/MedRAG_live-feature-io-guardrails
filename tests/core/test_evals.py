from __future__ import annotations

import json
from pathlib import Path

import deepeval.metrics as deepeval_metrics

from eval.shared.metrics import build_rag_metrics
from src.core.base import MetadataField, ProjectConfig
from src.core.evals import load_latest_eval_result, run_medrag_eval
from src.core.schemas import QueryArtifacts, RAGResponse


class _FakeMetric:
    def __init__(
        self,
        name: str,
        score: float | None = 1.0,
        threshold: float = 0.7,
        reason: str = "Looks good.",
        should_raise: bool = False,
    ) -> None:
        self.name = name
        self._score = score
        self.threshold = threshold
        self._reason = reason
        self._should_raise = should_raise

    def measure(self, test_case, _show_indicator: bool = False):  # noqa: ANN001
        if self._should_raise:
            raise RuntimeError("metric exploded")
        self.score = self._score
        self.success = bool(self._score is not None and self._score >= self.threshold)
        self.reason = self._reason
        self.error = None
        return self.score


class _FakeService:
    def __init__(self, config: ProjectConfig) -> None:
        self.config = config

    def collection_ready(self) -> bool:
        return True

    def query(self, question: str) -> QueryArtifacts:
        return QueryArtifacts(
            response=RAGResponse(
                answer=f"Answer for: {question}",
                evidence="Evidence summary",
                sources=["Bootstrap: bootstrap_seed"],
                confidence="moderate",
                disclaimer="For educational purposes only.",
            ),
            retrieval_context=["Context snippet"],
        )


def _config(tmp_path: Path) -> ProjectConfig:
    return ProjectConfig(
        name="medrag",
        collection_name="medrag_collection_bge_small",
        system_prompt="prompt",
        disclaimer="disclaimer",
        data_dir=tmp_path / "data",
        metadata_fields=[MetadataField(name="source_org", type="str", description="org")],
        golden_dataset_path=tmp_path / "golden.json",
        safeguard_policy="policy",
    )


def test_run_medrag_eval_persists_latest_results(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.golden_dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "med_001",
                    "query": "What is the first-line treatment?",
                    "expected_answer": "Expected answer",
                }
            ]
        )
    )
    service = _FakeService(config)
    monkeypatch.setattr(
        "src.core.evals.build_rag_metrics",
        lambda: [_FakeMetric("Faithfulness"), _FakeMetric("Answer Relevancy", score=0.8)],
    )

    result = run_medrag_eval(service)
    latest = load_latest_eval_result(service)

    assert result.summary.success is True
    assert result.summary.dataset_size == 1
    assert result.summary.passed_cases == 1
    assert result.cases[0].success is True
    assert [metric.name for metric in result.cases[0].metrics] == [
        "Faithfulness",
        "Answer Relevancy",
    ]
    assert latest == result


def test_run_medrag_eval_marks_metric_errors_as_failed(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.golden_dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "med_002",
                    "query": "Why include a disclaimer?",
                    "expected_answer": "Expected answer",
                }
            ]
        )
    )
    service = _FakeService(config)
    monkeypatch.setattr(
        "src.core.evals.build_rag_metrics",
        lambda: [_FakeMetric("Faithfulness", should_raise=True)],
    )

    result = run_medrag_eval(service)

    assert result.summary.success is False
    assert result.summary.failed_cases == 1
    assert result.cases[0].success is False
    assert result.cases[0].metrics[0].error == "metric exploded"


def test_build_rag_metrics_uses_requested_labels(monkeypatch) -> None:
    monkeypatch.setattr(
        deepeval_metrics,
        "AnswerRelevancyMetric",
        lambda threshold=0.7: _FakeMetric("internal", threshold=threshold),
    )
    monkeypatch.setattr(
        deepeval_metrics,
        "ContextualRelevancyMetric",
        lambda threshold=0.7: _FakeMetric("internal", threshold=threshold),
    )
    monkeypatch.setattr(
        deepeval_metrics,
        "FaithfulnessMetric",
        lambda threshold=0.7: _FakeMetric("internal", threshold=threshold),
    )

    metrics = build_rag_metrics()

    assert [metric.name for metric in metrics] == [
        "Answer Relevance",
        "Context Relevance",
        "Groundedness",
    ]
    assert [metric.threshold for metric in metrics] == [0.7, 0.7, 0.7]
