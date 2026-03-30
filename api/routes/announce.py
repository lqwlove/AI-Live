from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/announce")


@router.get("/items")
async def list_items(request: Request):
    store = request.app.state.announcement_store
    return store.get_all()


class ItemsPutBody(BaseModel):
    items: list[dict] = Field(default_factory=list)


@router.put("/items")
async def put_items(body: ItemsPutBody, request: Request):
    store = request.app.state.announcement_store
    return store.replace_all(body.items)


class RuntimeBody(BaseModel):
    enabled: bool | None = None
    active_ids: list[str] | None = None
    interval_seconds: float | None = Field(default=None, ge=1.0, le=3600.0)
    voice_volume: float | None = Field(default=None, ge=0.0, le=1.0)


def _runtime_dict(engine, config) -> dict:
    audio_cfg = config.get("audio")
    ann_cfg = config.get("announce")
    return {
        "enabled": getattr(engine, "announce_enabled", False),
        "active_ids": list(getattr(engine, "announce_active_ids", [])),
        "interval_seconds": getattr(
            engine,
            "_announce_interval",
            float(ann_cfg.get("interval_seconds", 30)),
        ),
        "voice_volume": getattr(
            engine,
            "voice_volume",
            float(audio_cfg.get("voice_volume", 1.0)),
        ),
    }


@router.get("/runtime")
async def get_runtime(request: Request):
    engine = request.app.state.session_manager.engine
    config = request.app.state.config
    return _runtime_dict(engine, config)


@router.put("/runtime")
async def put_runtime(body: RuntimeBody, request: Request):
    engine = request.app.state.session_manager.engine
    config = request.app.state.config
    store = request.app.state.announcement_store

    if not engine.running:
        raise HTTPException(status_code=400, detail="请先开播后再调节自动播报")

    if body.enabled is not None:
        engine.announce_enabled = body.enabled

    if body.active_ids is not None:
        ok, msg = store.validate_active_ids(body.active_ids)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        engine.announce_active_ids = list(body.active_ids)

    if body.interval_seconds is not None:
        engine._announce_interval = body.interval_seconds

    if body.voice_volume is not None:
        engine.voice_volume = body.voice_volume
        audio = config.get_all().get("audio", {})
        audio = {**audio, "voice_volume": body.voice_volume}
        config.update({"audio": audio})

    return _runtime_dict(engine, config)
