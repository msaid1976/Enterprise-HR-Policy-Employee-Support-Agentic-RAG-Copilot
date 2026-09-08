import logging
import time
from pinecone import Pinecone , ServerlessSpec
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from app.core.config import get_settings
from langchain_huggingface import HuggingFaceEmbeddings


logger = logging.getLogger(__name__)

settings = get_settings()


_embeddings = None
_vectorstore = None


EMBEDDING_DIMENSIONS = {
    "sentence-transformers/all-MiniLM-L6-v2": 384,  # for Hugging Face Embedding Model
    "text-embedding-3-small": 1536,  # for OpenAI Embedding Model
    "text-embedding-3-large": 3072,  # for OpenAI Embedding Model
    "text-embedding-ada-002": 1536,  # for OpenAI Embedding Model
    "all-minilm-l6-v2": 384,         # for OpenAI Embedding Model
}


def get_active_embedding_model_name() -> str:
    provider = (settings.embedding_provider or "openai").strip().lower()
    if provider == "huggingface":
        return settings.huggingface_embedding_model
    return settings.embedding_model


def get_embedding_dimension(model_name: str | None = None) -> int:
    name = (model_name or get_active_embedding_model_name() or "").strip()
    if not name:
        raise RuntimeError("Embedding model is not configured")
    normalized = name.lower()
    if normalized in EMBEDDING_DIMENSIONS:
        return EMBEDDING_DIMENSIONS[normalized]
    
    if "sentence-transformers/all-MiniLM-L6-v2" in normalized:
        return 384
    if "text-embedding-3-small" in normalized:
        return 1536
    if "text-embedding-3-large" in normalized:
        return 3072
    if "text-embedding-ada-002" in normalized:
        return 1536
    if "all-minilm" in normalized:
        return 384
    
    raise ValueError(
        f"Unsupported embedding model '{model_name or settings.embedding_model}' for Pinecone. "
        "Add the matching dimension to EMBEDDING_DIMENSIONS."
    )



def _build_openai_embeddings():
    if not settings.openai_api_key:
        raise RuntimeError(
            "EMBEDDING_PROVIDER is 'openai' but OPENAI_API_KEY is missing. "
            "Set OPENAI_API_KEY in your .env, or set EMBEDDING_PROVIDER=huggingface."
        )
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )


def _build_huggingface_embeddings():
    return HuggingFaceEmbeddings(
        model_name=settings.huggingface_embedding_model,
        encode_kwargs={"normalize_embeddings": True},
    )


# Registry of embedding providers. Add new entries here to support more
# embedding libraries without touching get_embeddings() itself.
EMBEDDING_PROVIDER_BUILDERS = {
    "openai": _build_openai_embeddings,
    "huggingface": _build_huggingface_embeddings,
}


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        provider = (settings.embedding_provider or "").strip().lower()
        builder = EMBEDDING_PROVIDER_BUILDERS.get(provider)
        if builder is None:
            raise ValueError(
                f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'. "
                f"Choose one of: {', '.join(EMBEDDING_PROVIDER_BUILDERS)}"
            )
        logger.info("Using '%s' embedding provider.", provider)
        _embeddings = builder()
    return _embeddings



def ensure_index():
    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is missing")
    desired_dimension = get_embedding_dimension()
    pc = Pinecone(api_key=settings.pinecone_api_key)
    names = [x["name"] for x in pc.list_indexes()]

    if settings.pinecone_index_name in names:
        index_info = pc.describe_index(settings.pinecone_index_name)
        current_dimension = getattr(index_info, "dimension", None)
        if current_dimension is None and isinstance(index_info, dict):
            current_dimension = index_info.get("dimension")
        if current_dimension is not None and current_dimension != desired_dimension:
            pc.delete_index(name=settings.pinecone_index_name)
            while settings.pinecone_index_name in [x["name"] for x in pc.list_indexes()]:
                time.sleep(1)
    if settings.pinecone_index_name not in [x["name"] for x in pc.list_indexes()]:
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=desired_dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(settings.pinecone_index_name).status["ready"]:
            time.sleep(1)

    return pc.Index(settings.pinecone_index_name)



def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        index = ensure_index()
        _vectorstore = PineconeVectorStore(
            index=index,
            embedding=get_embeddings(),
            namespace=settings.pinecone_namespace,
        )
    return _vectorstore



def get_retriever():
    return get_vectorstore().as_retriever(search_kwargs={"k": settings.top_k})




def add_documents(chunks):
    store = get_vectorstore()
    return store.add_documents(chunks)



def has_indexed_vectors() -> bool:
    """True if the Pinecone index already has vectors in our namespace."""
    index = ensure_index()
    stats = index.describe_index_stats()
    namespaces = stats.get("namespaces") if isinstance(stats, dict) else getattr(stats, "namespaces", {})
    ns = (namespaces or {}).get(settings.pinecone_namespace)
    if ns is None:
        return False
    count = ns.get("vector_count") if isinstance(ns, dict) else getattr(ns, "vector_count", 0)
    return bool(count)
