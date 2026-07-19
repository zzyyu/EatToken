from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from eattoken.web.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="EatToken Dashboard")
    app.include_router(router)
    base = Path(__file__).resolve().parent
    app.mount("/static", StaticFiles(directory=str(base / "static")), name="static")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
