import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import Config
from core.events import EventBus
from core.session import SessionManager
from utils.paths import get_bundle_dir, get_data_path

from api.routes.health import router as health_router
from api.routes.config_routes import router as config_router
from api.routes.session import router as session_router
from api.routes.products import router as products_router
from api.ws import router as ws_router


def create_app(config_path: str | None = None) -> FastAPI:
    if config_path is None:
        config_path = get_data_path("config.yaml")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = FastAPI(title="AI Live", version="0.3.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    config = Config(config_path)
    event_bus = EventBus()
    session_manager = SessionManager(config, event_bus)

    from knowledge.product_store import ProductStore

    knowledge_cfg = config.get("knowledge")
    products_file = knowledge_cfg.get("products_file", "products.json")
    if not os.path.isabs(products_file):
        products_file = get_data_path(products_file)
    product_store = ProductStore(
        file_path=products_file,
        max_match=knowledge_cfg.get("max_match_products", 3),
    )

    app.state.config = config
    app.state.event_bus = event_bus
    app.state.session_manager = session_manager
    app.state.product_store = product_store

    app.include_router(health_router)
    app.include_router(config_router)
    app.include_router(session_router)
    app.include_router(products_router)
    app.include_router(ws_router)

    # Serve TTS audio files for browser playback
    audio_dir = get_data_path("audio_cache")
    os.makedirs(audio_dir, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=audio_dir), name="audio")

    # Serve pre-built frontend (web/dist)
    dist_dir = os.path.join(get_bundle_dir(), "web", "dist")
    if os.path.isdir(dist_dir):
        app.mount(
            "/assets",
            StaticFiles(directory=os.path.join(dist_dir, "assets")),
            name="assets",
        )

        index_html = os.path.join(dist_dir, "index.html")

        @app.get("/{full_path:path}")
        async def spa_fallback(request: Request, full_path: str):
            file_path = os.path.join(dist_dir, full_path)
            if full_path and os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(index_html)

    return app
