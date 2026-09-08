import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Sample-KB auto-ingestion runs from app.main's lifespan startup hook, so it
# happens the same way here as it does under `uvicorn` directly (Docker/Render).

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
