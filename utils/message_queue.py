import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ChatTask:
    user: str
    content: str
    timestamp: float = field(default_factory=time.time)
    reply_text: str = ""
    audio_path: str = ""


class MessageFilter:
    """弹幕过滤器：判断是否需要 AI 回复"""

    def __init__(self, keywords: list[str], min_length: int = 2,
                 max_length: int = 100, cooldown: float = 3.0):
        self.keywords = keywords
        self.min_length = min_length
        self.max_length = max_length
        self.cooldown = cooldown
        self._last_reply_time: dict[str, float] = {}

    def should_reply(self, user_id: str, content: str) -> bool:
        if len(content) < self.min_length or len(content) > self.max_length:
            return False

        now = time.time()
        last_time = self._last_reply_time.get(user_id, 0)
        if now - last_time < self.cooldown:
            return False

        has_keyword = any(kw in content for kw in self.keywords)
        if has_keyword:
            self._last_reply_time[user_id] = now
            return True

        return False


class TaskQueue:
    """异步任务队列，管理弹幕 → AI回复 → TTS → 播放的流水线"""

    def __init__(self, max_size: int = 50):
        self._queue: asyncio.Queue[ChatTask] = asyncio.Queue(maxsize=max_size)
        self._running = False

    async def put(self, task: ChatTask):
        if self._queue.full():
            try:
                self._queue.get_nowait()
                logger.warning("队列已满，丢弃最早的任务")
            except asyncio.QueueEmpty:
                pass
        await self._queue.put(task)

    async def get(self) -> ChatTask:
        return await self._queue.get()

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def empty(self) -> bool:
        return self._queue.empty()
