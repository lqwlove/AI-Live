import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    CHAT_RECEIVED = "chat_received"
    CHAT_FILTERED = "chat_filtered"
    AI_REPLY_START = "ai_reply_start"
    AI_REPLY_DONE = "ai_reply_done"
    TTS_START = "tts_start"
    TTS_DONE = "tts_done"
    AUDIO_PLAYING = "audio_playing"
    AUDIO_DONE = "audio_done"
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    SESSION_ERROR = "session_error"
    STATS_UPDATE = "stats_update"
    LIKE = "like"
    GIFT = "gift"
    MEMBER_JOIN = "member_join"
    CONNECTED = "connected"


@dataclass
class Event:
    type: EventType
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class EventBus:
    """Pub/sub event bus backed by asyncio.Queue per subscriber."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=500)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    async def emit(self, event: Event):
        for q in self._subscribers:
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def emit_sync(self, event: Event, loop: asyncio.AbstractEventLoop | None = None):
        """Thread-safe emit for callbacks running outside the event loop."""
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
        loop.call_soon_threadsafe(asyncio.ensure_future, self.emit(event))
