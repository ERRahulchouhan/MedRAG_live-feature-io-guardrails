from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class AppSettings:
    active_project: str
    qdrant_host: str
    qdrant_port: int
    openai_model: str
    embedding_model: str
    embedding_output_dimensionality: int
    embedding_batch_size: int
    chunk_size: int
    chunk_overlap: int
    query_mode: str
    similarity_top_k: int
    sparse_top_k: int
    hybrid_alpha: float
    groq_api_key: str | None
    groq_prompt_guard_model: str
    groq_safeguard_model: str
    guardrail_timeout_seconds: float
    prompt_guard_threshold: float

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            active_project=os.getenv("ACTIVE_PROJECT", "medrag"),
            qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            embedding_output_dimensionality=int(
                os.getenv("EMBEDDING_OUTPUT_DIMENSIONALITY", "384")
            ),
            embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "16")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1024")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "100")),
            query_mode=os.getenv("VECTOR_STORE_QUERY_MODE", "default"),
            similarity_top_k=int(os.getenv("SIMILARITY_TOP_K", "8")),
            sparse_top_k=int(os.getenv("SPARSE_TOP_K", "8")),
            hybrid_alpha=float(os.getenv("HYBRID_ALPHA", "0.5")),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_prompt_guard_model=os.getenv(
                "GROQ_PROMPT_GUARD_MODEL", "meta-llama/llama-prompt-guard-2-86m"
            ),
            groq_safeguard_model=os.getenv(
                "GROQ_SAFEGUARD_MODEL", "openai/gpt-oss-safeguard-20b"
            ),
            guardrail_timeout_seconds=float(os.getenv("GUARDRAIL_TIMEOUT_SECONDS", "2.0")),
            prompt_guard_threshold=float(os.getenv("PROMPT_GUARD_THRESHOLD", "0.5")),
        )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings.from_env()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]