import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from utils.zh_text import is_primarily_chinese
from utils.paths import get_data_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/announce")


def _make_tts(config):
    """从配置创建独立 TTS 实例（用于预生成，不依赖运行中的会话）。"""
    tts_cfg = config.get("tts")
    engine = tts_cfg.get("engine", "edge-tts")
    output_dir = tts_cfg.get("output_dir", "audio_cache")
    if not os.path.isabs(output_dir):
        output_dir = get_data_path(output_dir)

    if engine == "volcengine":
        from tts.volcengine_speaker import VolcengineSpeaker
        from tts.volcengine_voices import get_voice_by_id

        vc_cfg = config.get("volcengine")
        # tts.speaker_id 非空时优先（UI 可配置），否则回退到 internal_credentials
        speaker_id = tts_cfg.get("speaker_id") or vc_cfg["speaker_id"]
        voice_cfg = get_voice_by_id(speaker_id)
        resource_id = (
            voice_cfg.resource_id
            if voice_cfg is not None
            else vc_cfg.get("resource_id", "seed-tts-2.0")
        )
        return VolcengineSpeaker(
            api_key=vc_cfg.get("api_key", ""),
            app_id=vc_cfg.get("app_id", ""),
            access_token=vc_cfg.get("access_token", ""),
            speaker_id=speaker_id,
            resource_id=resource_id,
            output_dir=output_dir,
        )
    else:
        from tts.speaker import TTSSpeaker
        return TTSSpeaker(
            voice=tts_cfg.get("voice", "zh-CN-XiaoxiaoNeural"),
            rate=tts_cfg.get("rate", "+0%"),
            volume=tts_cfg.get("volume", "+0%"),
            output_dir=output_dir,
        )


async def _pregen_items(store, config):
    """后台预生成所有启用文案的语音缓存。"""
    try:
        tts = _make_tts(config)
    except Exception as e:
        logger.error(f"[Announce] 预生成：初始化 TTS 失败: {e}")
        return

    is_volcengine = config.get("tts").get("engine", "edge-tts") == "volcengine"
    items = store.get_all()
    for item in items:
        if not item.get("enabled"):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        try:
            if is_volcengine:
                lang = "zh" if is_primarily_chinese(text) else "en"
                path = await tts.synthesize(text, lang=lang)
            else:
                path = await tts.synthesize(text)
            if path:
                logger.info(f"[Announce] 预生成完成: {item.get('title') or item['id']} → {path}")
            else:
                logger.warning(f"[Announce] 预生成失败: {item.get('title') or item['id']}")
        except Exception as e:
            logger.error(f"[Announce] 预生成出错 id={item['id']}: {e}")


@router.get("/items")
async def list_items(request: Request):
    store = request.app.state.announcement_store
    return store.get_all()


class ItemsPutBody(BaseModel):
    items: list[dict] = Field(default_factory=list)


@router.put("/items")
async def put_items(body: ItemsPutBody, request: Request, background_tasks: BackgroundTasks):
    store = request.app.state.announcement_store
    config = request.app.state.config
    result = store.replace_all(body.items)
    # 保存后立即在后台预生成所有启用文案的语音，直播时直接命中缓存
    background_tasks.add_task(_pregen_items, store, config)
    return result


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
        "current": getattr(engine, "announce_current", None),
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
        if not body.enabled:
            await engine.stop_announcement()

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


class PlayBody(BaseModel):
    id: str


@router.post("/play")
async def play_announcement(body: PlayBody, request: Request):
    engine = request.app.state.session_manager.engine

    if not engine.running:
        raise HTTPException(status_code=400, detail="请先开播后再手动播报")

    try:
        await engine.play_announcement_item(body.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return _runtime_dict(engine, request.app.state.config)


@router.post("/stop")
async def stop_announcement(request: Request):
    engine = request.app.state.session_manager.engine

    if not engine.running:
        raise HTTPException(status_code=400, detail="当前未开播")

    await engine.stop_announcement()
    return _runtime_dict(engine, request.app.state.config)
