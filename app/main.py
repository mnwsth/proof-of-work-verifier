"""FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import ROOT, load_app_config
from app.dashboard import router
from app.storage import Storage
from app.utils import setup_logging


def create_app(config=None) -> FastAPI:
    config = config or load_app_config()
    log_path = ROOT / "logs" / "verifier.log"
    logger = setup_logging(log_path)
    logger.info("Starting proof-of-work verifier")
    app = FastAPI(title="YouTube Proof-of-Work Integrity Verifier")
    app.state.config = config
    app.state.storage = Storage(config.data_root_path)
    app.state.youtube = None
    app.state.classroom = None
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
