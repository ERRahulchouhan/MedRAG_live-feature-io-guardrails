from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.generator import answer_question
from src.core.indexer import build_index, collection_exists, load_index
from src.core.projects import ProjectDefinition, get_project_definition
from src.core.schemas import QueryArtifacts
from src.core.settings import AppSettings, get_settings

@dataclass
class RAGService:
    definition: ProjectDefinition
    settings: AppSettings
    index: Any | None = None

    @classmethod
    def from_project_name(
        cls, project_name: str | None = None, settings: AppSettings | None = None
    ) -> "RAGService":
        current_settings = settings or get_settings()
        resolved_name = project_name or current_settings.active_project
        definition = get_project_definition(resolved_name)
        return cls(definition=definition, settings=current_settings)

    @property
    def config(self):
        return self.definition.config

    def collection_ready(self) -> bool:
        return collection_exists(self.config, self.settings)

    def build_index(self) -> int:
        ingestor = self.definition.ingestor_cls(self.config)
        documents = ingestor.ingest()
        if not documents:
            raise RuntimeError(
                "No documents were loaded. Add guideline PDFs or adjust PubMed ingestion first."
            )
        self.index = build_index(documents=documents, config=self.config, settings=self.settings)
        return len(documents)

    def ensure_index_loaded(self) -> Any:
        if self.index is not None:
            return self.index
        if not self.collection_ready():
            raise FileNotFoundError(
                f"Qdrant collection '{self.config.collection_name}' is missing. "
                "Run the indexing command first."
            )
        self.index = load_index(config=self.config, settings=self.settings)
        return self.index

    def query(self, question: str) -> QueryArtifacts:
        index = self.ensure_index_loaded()
        return answer_question(
            index=index,
            question=question,
            config=self.config,
            settings=self.settings,
        )
