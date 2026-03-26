import asyncio
import collections
import logging
import time
from typing import Callable

from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    ConnectEvent,
    CommentEvent,
    GiftEvent,
    LikeEvent,
    JoinEvent,
    FollowEvent,
    DisconnectEvent,
    RoomUserSeqEvent,
)

logger = logging.getLogger(__name__)


def _safe_user(event) -> dict:
    """Safely extract user info, bypassing broken ExtendedUser.from_user() conversion."""
    try:
        u = event.user
        return {
            "id": str(getattr(u, "id", "") or ""),
            "nickname": getattr(u, "nickname", "") or getattr(u, "unique_id", "") or "",
            "unique_id": getattr(u, "unique_id", "") or "",
        }
    except (TypeError, AttributeError):
        raw = getattr(event, "user_info", None)
        if raw is None:
            return {"id": "", "nickname": "", "unique_id": ""}
        return {
            "id": str(getattr(raw, "id", "") or ""),
            "nickname": (
                getattr(raw, "nickname", "")
                or getattr(raw, "nickName", "")
                or getattr(raw, "unique_id", "")
                or getattr(raw, "uniqueId", "")
                or ""
            ),
            "unique_id": getattr(raw, "unique_id", "") or getattr(raw, "uniqueId", "") or "",
        }


class _Deduplicator:
    """基于消息指纹的去重器，自动过期旧条目"""

    def __init__(self, capacity: int = 500, ttl: float = 120.0):
        self._seen: collections.OrderedDict[str, float] = collections.OrderedDict()
        self._capacity = capacity
        self._ttl = ttl

    def is_dup(self, key: str) -> bool:
        now = time.time()
        while self._seen:
            oldest_key, ts = next(iter(self._seen.items()))
            if now - ts > self._ttl:
                self._seen.pop(oldest_key)
            else:
                break
        if key in self._seen:
            return True
        self._seen[key] = now
        if len(self._seen) > self._capacity:
            self._seen.popitem(last=False)
        return False


class TikTokDanmakuClient:
    """TikTok 直播弹幕客户端，使用 TikTokLive 库"""

    def __init__(self, unique_id: str, proxy: str = ""):
        if unique_id.startswith("@"):
            unique_id = unique_id[1:]
        self.unique_id = unique_id
        self.proxy = proxy
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False
        self._client: TikTokLiveClient | None = None
        self._dedup = _Deduplicator(capacity=500, ttl=120.0)
        self._room_id: int | None = None
        self._ever_connected = False

    def on(self, event: str, callback: Callable):
        self._callbacks.setdefault(event, []).append(callback)

    def _emit(self, event: str, data: dict):
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"回调处理出错 [{event}]: {e}")

    async def start(self):
        self._running = True
        logger.info(f"正在连接 TikTok 直播间 @{self.unique_id} ...")

        kwargs = {"unique_id": f"@{self.unique_id}"}
        if self.proxy:
            kwargs["web_proxy"] = self.proxy
            kwargs["ws_proxy"] = self.proxy

        error_count = 0
        max_errors = 10

        while self._running and error_count < max_errors:
            self._client = TikTokLiveClient(**kwargs)
            self._register_events()

            try:
                connect_kwargs = {}
                if self._ever_connected and self._room_id:
                    connect_kwargs["room_id"] = self._room_id
                    connect_kwargs["process_connect_events"] = False

                await self._client.connect(**connect_kwargs)

                # connect() returned normally → WebSocket closed gracefully
                # This is expected (signed URLs expire), just reconnect quietly
                error_count = 0
                if self._running:
                    logger.debug("WebSocket 连接周期结束，正在静默重连...")
                    await asyncio.sleep(1)

            except Exception as e:
                err_msg = str(e)
                if "not found" in err_msg.lower() or "offline" in err_msg.lower():
                    logger.error(f"直播间 @{self.unique_id} 未开播或不存在: {e}")
                    break
                if "blocked" in err_msg.lower() or "200" in err_msg:
                    logger.warning(f"被 TikTok 暂时限制: {e}")
                    error_count += 1
                    wait = min(error_count * 10, 60)
                    logger.info(
                        f"等待 {wait} 秒后重试 (第 {error_count}/{max_errors} 次)..."
                    )
                    await asyncio.sleep(wait)
                    continue

                error_count += 1
                wait = min(error_count * 3, 30)
                logger.warning(
                    f"连接出错: {e}，{wait}s 后重连 (第 {error_count}/{max_errors} 次)"
                )
                await asyncio.sleep(wait)

    def _make_key(self, event_type: str, event) -> str:
        uid = _safe_user(event)["id"] if hasattr(event, "user") or hasattr(event, "user_info") else ""
        msg_id = getattr(event, "msg_id", "") or getattr(event, "message_id", "")
        if msg_id:
            return f"{event_type}:{msg_id}"
        extra = ""
        if event_type == "chat":
            extra = getattr(event, "comment", "")
        return f"{event_type}:{uid}:{extra}"

    def _register_events(self):
        client = self._client

        @client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            room_id = getattr(event, "room_id", "") or self.unique_id
            if not self._ever_connected:
                logger.info(f"TikTok 直播间已连接: @{self.unique_id}")
                self._ever_connected = True
            else:
                logger.debug(f"TikTok 直播间重连成功: @{self.unique_id}")
            if room_id and str(room_id).isdigit():
                self._room_id = int(room_id)
            self._emit(
                "connected", {"room_id": str(room_id), "unique_id": self.unique_id}
            )

        @client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            if self._dedup.is_dup(self._make_key("chat", event)):
                return
            u = _safe_user(event)
            self._emit(
                "chat",
                {
                    "user": u["nickname"] or u["unique_id"],
                    "user_id": u["id"],
                    "content": event.comment,
                    "time": time.time(),
                },
            )

        @client.on(GiftEvent)
        async def on_gift(event: GiftEvent):
            if self._dedup.is_dup(self._make_key("gift", event)):
                return
            u = _safe_user(event)
            self._emit(
                "gift",
                {
                    "user": u["nickname"] or u["unique_id"],
                    "gift_name": event.gift.name if event.gift else "Gift",
                    "count": event.gift.count if event.gift else 1,
                    "diamond": event.gift.diamond_count if event.gift else 0,
                    "time": time.time(),
                },
            )

        @client.on(LikeEvent)
        async def on_like(event: LikeEvent):
            u = _safe_user(event)
            self._emit(
                "like",
                {
                    "user": u["nickname"] or u["unique_id"],
                    "user_id": u["id"],
                    "count": getattr(event, "count", 1),
                    "total": getattr(event, "total", 0),
                },
            )

        @client.on(JoinEvent)
        async def on_join(event: JoinEvent):
            if self._dedup.is_dup(self._make_key("join", event)):
                return
            u = _safe_user(event)
            self._emit(
                "member",
                {
                    "user": u["nickname"] or u["unique_id"],
                    "action": "joined the live",
                },
            )

        @client.on(FollowEvent)
        async def on_follow(event: FollowEvent):
            if self._dedup.is_dup(self._make_key("follow", event)):
                return
            u = _safe_user(event)
            self._emit(
                "follow",
                {
                    "user": u["nickname"] or u["unique_id"],
                },
            )

        @client.on(RoomUserSeqEvent)
        async def on_viewer(event: RoomUserSeqEvent):
            total = getattr(event, "total", 0)
            self._emit(
                "room_stats",
                {
                    "online": total,
                    "total_pv": "",
                },
            )

        @client.on(DisconnectEvent)
        async def on_disconnect(event: DisconnectEvent):
            logger.debug("WebSocket 连接断开，将自动重连")

    def stop(self):
        self._running = False
        if self._client:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._client.disconnect())
                else:
                    loop.run_until_complete(self._client.disconnect())
            except Exception:
                pass
