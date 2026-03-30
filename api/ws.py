import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.events import EventBus, EventType

logger = logging.getLogger(__name__)

_WS_DEBUG_TYPES = frozenset({EventType.CHAT_RECEIVED, EventType.AI_REPLY_DONE})

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    event_bus: EventBus = websocket.app.state.event_bus
    queue = event_bus.subscribe()
    logger.info("WebSocket client connected")
    try:
        while True:
            event = await queue.get()
            payload = event.to_dict()
            if event.type in _WS_DEBUG_TYPES:
                data = payload.get("data") or {}
                extra = ""
                if event.type == EventType.CHAT_RECEIVED:
                    c = str(data.get("content", "") or "")
                    extra = (
                        f" msg_uid={str(data.get('msg_uid', ''))[:12]}"
                        f" content_len={len(c)} merged_paren={('(' in c and ')' in c)}"
                    )
                elif event.type == EventType.AI_REPLY_DONE:
                    r = str(data.get("reply", "") or "")
                    extra = f" reply_len={len(r)} merged_paren={('(' in r and ')' in r)}"
                logger.info(
                    "WS→浏览器 type=%s ts=%s%s keys=%s",
                    payload.get("type"),
                    payload.get("timestamp"),
                    extra,
                    list(data.keys()),
                )
            await websocket.send_json(payload)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        event_bus.unsubscribe(queue)
        logger.info("WebSocket client disconnected")
