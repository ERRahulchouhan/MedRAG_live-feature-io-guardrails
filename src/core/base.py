from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from llama_index.core.schema import Document


@dataclass(frozen=True)
class MetadataField:
    name: str
    type: str
    description: str


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    collection_name: str
    system_prompt: str
    disclaimer: str
    data_dir: Path
    metadata_fields: list[MetadataField]
    golden_dataset_path: Path
    safeguard_policy: str


class DocumentIngestor(ABC):
    """Project-specific parsing contract."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    @abstractmethod
    def load_and_parse(self) -> list["Document"]:
        """Load raw data, parse it, and return LlamaIndex documents."""

    @abstractmethod
    def enrich_metadata(self, docs: list["Document"]) -> list["Document"]:
        """Attach domain-specific metadata needed by the shared pipeline."""

    def ingest(self) -> list["Document"]:
        return self.enrich_metadata(self.load_and_parse())
