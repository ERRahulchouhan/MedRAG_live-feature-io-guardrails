from __future__ import annotations

from dataclasses import dataclass

from src.core.base import DocumentIngestor, ProjectConfig
from src.projects.medrag.config import MEDRAG_CONFIG
from src.projects.medrag.ingestor import MedRAGIngestor

@dataclass(frozen=True)
class ProjectDefinition:
    config: ProjectConfig
    ingestor_cls: type[DocumentIngestor]


PROJECTS: dict[str, ProjectDefinition] = {
    "medrag": ProjectDefinition(config=MEDRAG_CONFIG, ingestor_cls=MedRAGIngestor),
}

def get_project_definition(name: str) -> ProjectDefinition:
    try:
        return PROJECTS[name]
    except KeyError as exc:
        supported = ", ".join(sorted(PROJECTS))
        raise ValueError(f"Unknown project '{name}'. Supported projects: {supported}") from exc
