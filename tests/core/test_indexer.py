import sys
import types

from src.core.indexer import _build_embed_model
from src.core.settings import AppSettings


class DummyFastEmbedEmbedding:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_build_embed_model_uses_fastembed(monkeypatch):
    fake_module = types.ModuleType("llama_index.embeddings.fastembed")
    fake_module.FastEmbedEmbedding = DummyFastEmbedEmbedding
    monkeypatch.setitem(sys.modules, "llama_index.embeddings.fastembed", fake_module)

    settings = AppSettings(
        active_project="medrag",
        qdrant_host="localhost",
        qdrant_port=6333,
        openai_model="gpt-4o-mini",
        embedding_model="BAAI/bge-small-en-v1.5",
        embedding_output_dimensionality=384,
        embedding_batch_size=16,
        chunk_size=1024,
        chunk_overlap=100,
        query_mode="default",
        similarity_top_k=8,
        sparse_top_k=8,
        hybrid_alpha=0.5,
        groq_api_key=None,
        groq_prompt_guard_model="meta-llama/llama-prompt-guard-2-86m",
        groq_safeguard_model="openai/gpt-oss-safeguard-20b",
        guardrail_timeout_seconds=2.0,
        prompt_guard_threshold=0.5,
    )

    embed_model = _build_embed_model(settings)

    assert isinstance(embed_model, DummyFastEmbedEmbedding)
    assert embed_model.kwargs["model_name"] == "BAAI/bge-small-en-v1.5"
