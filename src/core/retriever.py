from __future__ import annotations

from src.core.base import ProjectConfig
from src.core.settings import AppSettings

def _build_llm(config: ProjectConfig, settings: AppSettings):
    from llama_index.llms.openai import OpenAI

    try:
        return OpenAI(
            model=settings.openai_model,
            temperature=0.1,
            system_prompt=config.system_prompt,
        )
    except TypeError:
        return OpenAI(model=settings.openai_model, temperature=0.1)


def build_query_engine(index, config: ProjectConfig, settings: AppSettings):
    llm = _build_llm(config, settings)
    query_kwargs = {
        "llm": llm,
        "similarity_top_k": settings.similarity_top_k,
        "response_mode": "compact",
    }
    if settings.query_mode == "hybrid":
        query_kwargs.update(
            {
                "vector_store_query_mode": "hybrid",
                "sparse_top_k": settings.sparse_top_k,
                "alpha": settings.hybrid_alpha,
            }
        )
    return index.as_query_engine(**query_kwargs)