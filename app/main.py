"""Application entry point: `uvicorn app.main:app`."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.errors import register_error_handlers
from app.routes import router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Mini Expense Tracker")
register_error_handlers(app)
app.include_router(router)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


# Mounted last so API routes take precedence; serves index.html at "/".
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True, check_dir=False), name="static")
