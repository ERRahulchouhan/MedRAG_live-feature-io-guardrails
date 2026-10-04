from __future__ import annotations

from pathlib import Path

import pytest

from src.core.base import MetadataField, ProjectConfig
from src.core.source_manager import SourceManager, summarize_pubmed_payloads


def _config(tmp_path: Path) -> ProjectConfig:
    return ProjectConfig(
        name="medrag",
        collection_name="test_collection",
        system_prompt="prompt",
        disclaimer="disclaimer",
        data_dir=tmp_path,
        metadata_fields=[MetadataField(name="source_org", type="str", description="org")],
        golden_dataset_path=tmp_path / "golden.json",
        safeguard_policy="policy",
    )


def test_source_manager_saves_lists_and_deletes_pdfs(tmp_path: Path) -> None:
    manager = SourceManager(_config(tmp_path))

    record = manager.save_source("guideline.pdf", b"%PDF-1.4 test")

    assert record.name == "guideline.pdf"
    assert record.size_bytes > 0
    assert [source.name for source in manager.list_sources()] == ["guideline.pdf"]

    manager.delete_source("guideline.pdf")

    assert manager.list_sources() == []


@pytest.mark.parametrize("filename", ["../escape.pdf", "notes.txt", ""])
def test_source_manager_rejects_invalid_filenames(tmp_path: Path, filename: str) -> None:
    manager = SourceManager(_config(tmp_path))

    with pytest.raises(ValueError):
        manager.save_source(filename, b"content")


def test_summarize_pubmed_payloads_groups_by_query_and_distinct_document() -> None:
    summaries = summarize_pubmed_payloads(
        [
            {"source": "pubmed", "query": "hypertension", "doc_id": "doc-1"},
            {"source": "pubmed", "query": "hypertension", "doc_id": "doc-1"},
            {"source": "pubmed", "query": "hypertension", "doc_id": "doc-2"},
            {"source": "pubmed", "query": "diabetes", "doc_id": "doc-3"},
            {"source": "guideline_pdf", "query": "ignore-me", "doc_id": "doc-4"},
        ]
    )

    assert [(summary.query, summary.document_count, summary.chunk_count) for summary in summaries] == [
        ("diabetes", 1, 1),
        ("hypertension", 2, 3),
    ]
