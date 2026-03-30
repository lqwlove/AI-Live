import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from utils.paths import get_data_path

router = APIRouter(prefix="/api/bgm")


@router.get("")
async def get_bgm_status(request: Request):
    engine = request.app.state.session_manager.engine
    if engine.bgm:
        return engine.bgm.get_status()
    return {"playing": False, "file": None, "volume": 0, "duck_volume": 0}


@router.get("/files")
async def list_bgm_files(request: Request):
    bgm_dir = request.app.state.config.get("bgm").get("dir", "bgm")
    if not os.path.isabs(bgm_dir):
        bgm_dir = get_data_path(bgm_dir)
    if not os.path.isdir(bgm_dir):
        return {"files": [], "dir": bgm_dir}
    extensions = (".mp3", ".wav", ".ogg", ".flac")
    files = [
        f for f in sorted(os.listdir(bgm_dir))
        if os.path.isfile(os.path.join(bgm_dir, f)) and f.lower().endswith(extensions)
    ]
    return {"files": files, "dir": bgm_dir}


class BgmPlayRequest(BaseModel):
    file: str = ""


@router.post("/play")
async def play_bgm(req: BgmPlayRequest, request: Request):
    engine = request.app.state.session_manager.engine
    if not engine.running:
        raise HTTPException(status_code=400, detail="请先开播后再切换背景音乐")
    player = engine.ensure_bgm_player()
    if not player:
        raise HTTPException(status_code=400, detail="当前无法播放背景音乐")

    file_path = None
    if req.file:
        safe_name = os.path.basename(req.file.strip())
        if not safe_name:
            raise HTTPException(status_code=400, detail="无效的文件名")
        bgm_dir = player.bgm_dir
        file_path = os.path.join(bgm_dir, safe_name)
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail=f"文件不存在: {safe_name}")

    player.play(file_path)
    return player.get_status()


@router.post("/stop")
async def stop_bgm(request: Request):
    engine = request.app.state.session_manager.engine
    if engine.bgm:
        engine.bgm.stop()
    return {"playing": False}


class BgmVolumeRequest(BaseModel):
    volume: float


@router.put("/volume")
async def set_bgm_volume(req: BgmVolumeRequest, request: Request):
    engine = request.app.state.session_manager.engine
    if not engine.running:
        raise HTTPException(status_code=400, detail="请先开播")
    player = engine.ensure_bgm_player()
    if not player:
        raise HTTPException(status_code=400, detail="无法调整背景音乐")
    player.set_volume(req.volume)
    return player.get_status()
