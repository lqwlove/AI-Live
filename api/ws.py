import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.events import EventBus

logger = logging.getLogger(__name__)

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
            await websocket.send_json(event.to_dict())
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        event_bus.unsubscribe(queue)
        logger.info("WebSocket client disconnected")
