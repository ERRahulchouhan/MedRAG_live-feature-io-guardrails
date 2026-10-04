from __future__ import annotations


def _named(metric: object, name: str) -> object:
    setattr(metric, "name", name)
    return metric


def build_rag_metrics():
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
    )

    return [
        _named(AnswerRelevancyMetric(threshold=0.7), "Answer Relevance"),
        _named(ContextualRelevancyMetric(threshold=0.7), "Context Relevance"),
        _named(FaithfulnessMetric(threshold=0.7), "Groundedness"),
    ]