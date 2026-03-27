import asyncio
import logging
import threading
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

    def __init__(
        self,
        keywords: list[str],
        min_length: int = 2,
        max_length: int = 100,
        cooldown: float = 3.0,
    ):
        self.keywords = keywords
        self.min_length = min_length
        self.max_length = max_length
        self.cooldown = cooldown
        self._last_reply_time: dict[str, float] = {}

    def should_reply(self, user_id: str, content: str) -> bool:
        if len(content) < self.min_length or len(content) > self.max_length:
            logger.debug(
                f"[Filter] 长度不符: len={len(content)}, 范围=[{self.min_length}, {self.max_length}]"
            )
            return False

        now = time.time()
        last_time = self._last_reply_time.get(user_id, 0)
        if now - last_time < self.cooldown:
            logger.debug(
                f"[Filter] 冷却中: user={user_id}, 距上次={now - last_time:.1f}s < {self.cooldown}s"
            )
            return False

        matched = [kw for kw in self.keywords if kw in content]
        if matched:
            self._last_reply_time[user_id] = now
            logger.info(f"[Filter] 命中关键词 {matched} → 通过")
            return True

        logger.info(f'[Filter] 未命中关键词, 内容="{content}", 关键词={self.keywords}')
        return False


class CommentBuffer:
    """Thread-safe buffer that accumulates comments for batch processing."""

    def __init__(self, max_size: int = 100):
        self._buffer: list[ChatTask] = []
        self._lock = threading.Lock()
        self.max_size = max_size

    def append(self, task: ChatTask):
        with self._lock:
            if len(self._buffer) >= self.max_size:
                self._buffer.pop(0)
            self._buffer.append(task)

    def drain(self) -> list[ChatTask]:
        """Atomically take all buffered comments and clear the buffer."""
        with self._lock:
            items = self._buffer[:]
            self._buffer.clear()
            return items

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._buffer)


class TaskQueue:
    """异步任务队列（保留用于 CLI 兼容）"""

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
