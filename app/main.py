from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.routes import router
from app.core.config import get_settings, BASE_DIR
from app.core.logging import configure_logging
from app.services.audit import init_db


configure_logging()
settings = get_settings()
init_db()


def ensure_kb_indexed() -> None:
    """Auto-ingest the sample KB into Pinecone on first boot, so a fresh
    deploy (Docker/Render, or `python run.py` locally) never starts against
    an empty index. Runs on every process start; a no-op once vectors exist."""
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_kb_indexed()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})
