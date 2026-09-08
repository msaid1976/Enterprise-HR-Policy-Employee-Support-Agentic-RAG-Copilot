from pathlib import Path
from app.core.config import get_settings
from app.services.ingestion import load_file, chunk_documents
from app.rag.vectorstore import add_documents


def ingest_sample_kb() -> tuple[int, int, int]:
    """Load every file in the sample KB folder, chunk it, and index it in Pinecone.

    Returns (num_files, num_chunks, num_vectors).
    """
    settings = get_settings()
    folder = Path(settings.sample_kb_dir)
    files = [p for p in folder.iterdir() if p.is_file()]

    all_docs = []
    for path in files:
        all_docs.extend(load_file(path))
    chunks = chunk_documents(all_docs)
    ids = add_documents(chunks)
    return len(files), len(chunks), len(ids)


if __name__ == "__main__":
    num_files, num_chunks, num_vectors = ingest_sample_kb()
    print(f"Indexed {num_files} files -> {num_chunks} chunks -> {num_vectors} Pinecone vectors")
