from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.engine import ConfigError

router = APIRouter(prefix="/api/session")


class StartRequest(BaseModel):
    platform: str
    mock_mode: bool = False
    video_id: str = ""
    channel_id: str = ""
    unique_id: str = ""
    room_id: str = ""
    live_url: str = ""


@router.post("/start")
async def start_session(req: StartRequest, request: Request):
    mgr = request.app.state.session_manager
    try:
        status = await mgr.start(req.platform, **req.model_dump(exclude={"platform"}))
        return status
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/stop")
async def stop_session(request: Request):
    mgr = request.app.state.session_manager
    return await mgr.stop()


@router.get("/status")
async def get_status(request: Request):
    mgr = request.app.state.session_manager
    return mgr.get_status()
