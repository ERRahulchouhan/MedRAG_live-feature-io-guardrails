from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.base import ProjectConfig
from src.core.indexer import build_qdrant_client
from src.core.settings import AppSettings


@dataclass(frozen=True)
class SourceFileRecord:
    name: str
    size_bytes: int
    modified_at: datetime


@dataclass(frozen=True)
class PubMedQueryRecord:
    query: str
    document_count: int
    chunk_count: int


@dataclass(frozen=True)
class PubMedStatus:
    enabled: bool
    configured_queries: list[str]
    configured_query_limit: int
    configured_max_results: int
    indexed_query_summaries: list[PubMedQueryRecord]
    indexed_document_count: int
    indexed_chunk_count: int


class SourceManager:
    def __init__(self, config: ProjectConfig):
        self.guideline_dir = config.data_dir / "guidelines"
        self.guideline_dir.mkdir(parents=True, exist_ok=True)

    def list_sources(self) -> list[SourceFileRecord]:
        records: list[SourceFileRecord] = []
        for path in sorted(self.guideline_dir.glob("*.pdf")):
            stat = path.stat()
            records.append(
                SourceFileRecord(
                    name=path.name,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )
        return records

    def save_source(self, filename: str, content: bytes) -> SourceFileRecord:
        path = self._resolve_source_path(filename)
        path.write_bytes(content)
        stat = path.stat()
        return SourceFileRecord(
            name=path.name,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        )

    def delete_source(self, filename: str) -> None:
        path = self._resolve_source_path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Source '{path.name}' does not exist.")
        path.unlink()

    def pubmed_status(
        self,
        *,
        settings: AppSettings,
        collection_name: str,
        configured_queries: list[str],
        configured_query_limit: int,
        configured_max_results: int,
    ) -> PubMedStatus:
        enabled = configured_query_limit > 0 and configured_max_results > 0
        client = build_qdrant_client(settings)
        try:
            client.get_collection(collection_name)
        except Exception:
            return PubMedStatus(
                enabled=enabled,
                configured_queries=configured_queries,
                configured_query_limit=configured_query_limit,
                configured_max_results=configured_max_results,
                indexed_query_summaries=[],
                indexed_document_count=0,
                indexed_chunk_count=0,
            )

        payloads: list[dict[str, Any]] = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=collection_name,
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            payloads.extend((point.payload or {}) for point in points)
            if offset is None:
                break

        summaries = summarize_pubmed_payloads(payloads)
        return PubMedStatus(
            enabled=enabled,
            configured_queries=configured_queries,
            configured_query_limit=configured_query_limit,
            configured_max_results=configured_max_results,
            indexed_query_summaries=summaries,
            indexed_document_count=sum(summary.document_count for summary in summaries),
            indexed_chunk_count=sum(summary.chunk_count for summary in summaries),
        )

    def _resolve_source_path(self, filename: str) -> Path:
        safe_name = Path(filename).name
        if not safe_name or safe_name != filename:
            raise ValueError("Invalid source filename.")
        if Path(safe_name).suffix.lower() != ".pdf":
            raise ValueError("Only PDF sources are supported.")
        return self.guideline_dir / safe_name


def summarize_pubmed_payloads(payloads: list[dict[str, Any]]) -> list[PubMedQueryRecord]:
    grouped: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        if payload.get("source") != "pubmed":
            continue
        query = str(payload.get("query") or "Unspecified query")
        query_summary = grouped.setdefault(
            query,
            {
                "document_keys": set(),
                "chunk_count": 0,
            },
        )
        query_summary["chunk_count"] += 1
        query_summary["document_keys"].add(_pubmed_document_key(payload))

    summaries = [
        PubMedQueryRecord(
            query=query,
            document_count=len(summary["document_keys"]),
            chunk_count=summary["chunk_count"],
        )
        for query, summary in grouped.items()
    ]
    return sorted(summaries, key=lambda item: item.query)


def _pubmed_document_key(payload: dict[str, Any]) -> str:
    for key in ("ref_doc_id", "doc_id", "document_id", "URL", "Title of this paper", "title"):
        value = payload.get(key)
        if value:
            return str(value)
    return "unknown-pubmed-document"
