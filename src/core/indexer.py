from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from src.core.base import ProjectConfig
from src.core.settings import AppSettings

if TYPE_CHECKING:
    from llama_index.core import VectorStoreIndex
    from llama_index.core.schema import Document


class QdrantClientCompat:
    def __init__(self, client: QdrantClient):
        self._client = client

    def search(
        self,
        collection_name: str,
        query_vector: Any,
        limit: int,
        query_filter: Any = None,
        **kwargs: Any,
    ):
        using = kwargs.pop("using", None)
        if using is None and isinstance(query_vector, list):
            using = self._default_vector_name(collection_name)
        response = self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using=using,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
            **kwargs,
        )
        return response.points

    def __getattr__(self, name: str):
        return getattr(self._client, name)

    def _default_vector_name(self, collection_name: str) -> str | None:
        vectors = self._client.get_collection(collection_name).config.params.vectors
        if isinstance(vectors, dict) and vectors:
            return next(iter(vectors))
        return None

    def search_batch(self, collection_name: str, requests: list[Any], **kwargs: Any):
        responses = []
        for request in requests:
            vector = getattr(request, "vector", None)
            query: Any = vector
            using: str | None = None

            if isinstance(vector, rest.NamedVector):
                query = vector.vector
                using = vector.name
            elif isinstance(vector, rest.NamedSparseVector):
                query = vector.vector
                using = vector.name

            response = self._client.query_points(
                collection_name=collection_name,
                query=query,
                using=using,
                limit=getattr(request, "limit", 10),
                query_filter=getattr(request, "filter", None),
                with_payload=getattr(request, "with_payload", True),
                **kwargs,
            )
            responses.append(response.points)
        return responses


def build_index(
    documents: list["Document"], config: ProjectConfig, settings: AppSettings
) -> "VectorStoreIndex":
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.core.node_parser import SentenceSplitter

    client = build_qdrant_client(settings)
    try:
        client.delete_collection(collection_name=config.collection_name)
    except Exception:
        pass

    vector_store = _build_vector_store(config, settings)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    splitter = SentenceSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    embed_model = _build_embed_model(settings)
    return VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        transformations=[splitter],
        show_progress=True,
    )


def load_index(config: ProjectConfig, settings: AppSettings) -> "VectorStoreIndex":
    from llama_index.core import VectorStoreIndex

    vector_store = _build_vector_store(config, settings)
    embed_model = _build_embed_model(settings)
    _warm_embed_model(embed_model)
    return VectorStoreIndex.from_vector_store(vector_store=vector_store, embed_model=embed_model)


def collection_exists(config: ProjectConfig, settings: AppSettings) -> bool:
    client = build_qdrant_client(settings)
    try:
        client.get_collection(config.collection_name)
        return True
    except Exception:
        return False


def build_qdrant_client(settings: AppSettings) -> QdrantClientCompat:
    return QdrantClientCompat(
        QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    )


def _build_embed_model(settings: AppSettings):
    from llama_index.embeddings.fastembed import FastEmbedEmbedding

    return FastEmbedEmbedding(
        model_name=settings.embedding_model,
        embed_batch_size=settings.embedding_batch_size,
    )


def _warm_embed_model(embed_model: Any) -> None:
    """Trigger lazy model initialization so the first user query is not cold."""
    warm_method = getattr(embed_model, "get_text_embedding", None)
    if callable(warm_method):
        warm_method("medrag warmup")


def _build_vector_store(config: ProjectConfig, settings: AppSettings):
    from llama_index.vector_stores.qdrant import QdrantVectorStore

    client = build_qdrant_client(settings)
    return QdrantVectorStore(
        client=client,
        collection_name=config.collection_name,
    )
