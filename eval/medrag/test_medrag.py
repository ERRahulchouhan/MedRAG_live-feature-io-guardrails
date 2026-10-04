from __future__ import annotations

import pytest

from eval.shared.metrics import build_rag_metrics
from src.core.service import RAGService

deepeval = pytest.importorskip("deepeval")
deepeval_test_case = pytest.importorskip("deepeval.test_case")
assert_test = deepeval.assert_test
LLMTestCase = deepeval_test_case.LLMTestCase



@pytest.mark.integration
def test_medrag_golden_dataset(medrag_dataset):
    service = RAGService.from_project_name("medrag")
    if not service.collection_ready():
        pytest.skip("MedRAG collection is not indexed yet.")

    metrics = build_rag_metrics()

    for item in medrag_dataset:
        result = service.query(item["query"])
        test_case = LLMTestCase(
            input=item["query"],
            actual_output=result.response.answer,
            expected_output=item["expected_answer"],
            retrieval_context=result.retrieval_context,
        )
        assert_test(test_case, metrics)