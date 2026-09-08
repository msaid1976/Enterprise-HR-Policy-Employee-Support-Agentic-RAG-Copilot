import uvicorn
from dotenv import load_dotenv

load_dotenv()


def ensure_kb_indexed() -> None:
    """Auto-ingest the sample KB into Pinecone on first run, so the app
    never starts against an empty index (which previously required
    manually running `python ingest_sample_kb.py` before the server
    would actually work)."""
    from app.rag.vectorstore import has_indexed_vectors
    from ingest_sample_kb import ingest_sample_kb

    try:
        if has_indexed_vectors():
            return
        print("Pinecone index is empty - running one-time sample KB ingestion...")
        num_files, num_chunks, num_vectors = ingest_sample_kb()
        print(f"Indexed {num_files} files -> {num_chunks} chunks -> {num_vectors} Pinecone vectors")
    except Exception as exc:
        print(f"Warning: skipped auto-ingestion ({exc}). Run `python ingest_sample_kb.py` manually if needed.")


if __name__ == "__main__":
    ensure_kb_indexed()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=True)
