from fastapi import APIRouter, Request
from pydantic import BaseModel

from tts.volcengine_voices import get_voices_dict

router = APIRouter(prefix="/api/config")


@router.get("")
async def get_config(request: Request):
    config = request.app.state.config
    return config.get_sanitized()


@router.put("")
async def update_config(request: Request):
    config = request.app.state.config
    body = await request.json()
    config.update(body)
    session_mgr = request.app.state.session_manager
    session_mgr.reload_config(config)
    return {"ok": True}


class ValidateRequest(BaseModel):
    platform: str


@router.post("/validate")
async def validate_platform(req: ValidateRequest, request: Request):
    config = request.app.state.config
    return config.validate_platform(req.platform)


@router.get("/volcengine-voices")
async def get_volcengine_voices():
    """返回预设的火山引擎音色列表。"""
    return get_voices_dict()
