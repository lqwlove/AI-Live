"""
LiveEngine — batch-mode live assistant engine.

Key design:
  * Comments accumulate in a CommentBuffer.
  * A timer loop drains the buffer every *batch_interval* seconds.
  * If there are new comments, they are sent to the AI in one batch call.
  * AI picks the important questions and returns a single combined reply.
  * TTS synthesises and plays that reply once.
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

from config import Config
from core.events import Event, EventBus, EventType
from tts.speaker import TTSSpeaker
from utils.audio_player import AudioPlayer
from utils.bgm_player import BgmPlayer
from utils.message_queue import ChatTask, CommentBuffer, MessageFilter
from utils.paths import get_data_path

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when required configuration is missing."""


class LiveEngine:
    def __init__(self, config: Config, event_bus: EventBus):
        self.config = config
        self.event_bus = event_bus
        self.running = False
        self.platform: str | None = None
        self.start_time: float | None = None
        self.stats = {"messages": 0, "ai_replies": 0, "audio_played": 0}
        self._auto_reply_chat = False
        self._reply_prefix = ""

        self.danmaku = None
        self.ai = None
        self.tts = None
        self._edge_tts_fallback: TTSSpeaker | None = None
        self._tts_engine = "edge-tts"
        self.player: AudioPlayer | None = None
        self.bgm: BgmPlayer | None = None
        self.msg_filter: MessageFilter | None = None
        self.comment_buffer: CommentBuffer | None = None
        self.product_store = None
        self.executor: ThreadPoolExecutor | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._batch_interval: float = 5.0

        self._like_buffer: dict[str, int] = {}
        self._like_total = 0
        self._like_flush_handle: asyncio.TimerHandle | None = None
        self._like_throttle = 3.0

        self._danmaku_task: asyncio.Task | None = None
        self._process_task: asyncio.Task | None = None

    def _init_components(self, platform: str, **kwargs):
        """Initialise AI, TTS, filter, player and the danmaku client."""
        self.platform = platform

        # --- Danmaku client ---
        mock_mode = kwargs.get("mock_mode", False)
        if mock_mode:
            from danmaku.client import MockDanmakuClient

            self.danmaku = MockDanmakuClient(interval=5.0)
        elif platform == "youtube":
            from danmaku.youtube_client import YouTubeDanmakuClient

            yt_cfg = self.config.get("youtube")
            video_id = kwargs.get("video_id") or yt_cfg.get("video_id", "")
            channel_id = kwargs.get("channel_id") or yt_cfg.get("channel_id", "")
            api_key = yt_cfg.get("api_key", "")
            client_secrets = yt_cfg.get("client_secrets_file", "")
            if not video_id and not channel_id:
                raise ConfigError("YouTube 需要 video_id 或 channel_id")
            if not api_key and not client_secrets:
                raise ConfigError("YouTube 需要 api_key 或 client_secrets_file")
            self.danmaku = YouTubeDanmakuClient(
                video_id=video_id,
                channel_id=channel_id,
                api_key=api_key,
                client_secrets_file=client_secrets,
            )
            self._auto_reply_chat = yt_cfg.get("auto_reply", False)
            self._reply_prefix = yt_cfg.get("reply_prefix", "")
        elif platform == "tiktok":
            from danmaku.tiktok_client import TikTokDanmakuClient

            unique_id = kwargs.get("unique_id") or self.config.get(
                "tiktok", "unique_id"
            )
            if not unique_id:
                raise ConfigError("TikTok 需要 unique_id")
            proxy = self.config.get("tiktok", "proxy")
            self.danmaku = TikTokDanmakuClient(unique_id, proxy=proxy)
        else:
            from danmaku.client import DouyinDanmakuClient

            room_id = (
                kwargs.get("room_id")
                or kwargs.get("live_url")
                or self.config.get("douyin", "room_id")
            )
            if not room_id:
                raise ConfigError("抖音需要 room_id 或 live_url")
            cookie = self.config.get("douyin", "cookie")
            self.danmaku = DouyinDanmakuClient(room_id, cookie=cookie)

        # --- Knowledge base ---
        knowledge_cfg = self.config.get("knowledge")
        if knowledge_cfg.get("enabled"):
            from knowledge.product_store import ProductStore

            self.product_store = ProductStore(
                file_path=knowledge_cfg.get("products_file", "products.json"),
                max_match=knowledge_cfg.get("max_match_products", 3),
            )

        # --- AI (agent or simple) ---
        ai_cfg = self.config.get("ai")
        engine_type = ai_cfg.get("engine", "agent")
        if engine_type == "agent":
            from ai.agent import LiveAgent

            self.ai = LiveAgent(
                api_key=ai_cfg["api_key"],
                base_url=ai_cfg["base_url"],
                model=ai_cfg["model"],
                system_prompt=ai_cfg["system_prompt"],
                max_history=ai_cfg["max_history"],
                multilang=ai_cfg.get("multilang", False),
                product_store=self.product_store,
            )
        else:
            from ai.replier import AIReplier

            self.ai = AIReplier(
                api_key=ai_cfg["api_key"],
                base_url=ai_cfg["base_url"],
                model=ai_cfg["model"],
                system_prompt=ai_cfg["system_prompt"],
                max_history=ai_cfg["max_history"],
                multilang=ai_cfg.get("multilang", False),
            )

        self._batch_interval = float(ai_cfg.get("batch_interval", 5))

        # --- TTS ---
        tts_cfg = self.config.get("tts")
        self._tts_engine = tts_cfg.get("engine", "edge-tts")
        output_dir = tts_cfg["output_dir"]
        if not os.path.isabs(output_dir):
            output_dir = get_data_path(output_dir)
        self._edge_tts_fallback = TTSSpeaker(
            voice=tts_cfg["voice"],
            rate=tts_cfg["rate"],
            volume=tts_cfg["volume"],
            output_dir=output_dir,
        )
        if self._tts_engine == "volcengine":
            from tts.volcengine_speaker import VolcengineSpeaker

            vc_cfg = self.config.get("volcengine")
            self.tts = VolcengineSpeaker(
                api_key=vc_cfg.get("api_key", ""),
                app_id=vc_cfg.get("app_id", ""),
                access_token=vc_cfg.get("access_token", ""),
                speaker_id=vc_cfg["speaker_id"],
                resource_id=vc_cfg.get("resource_id", "seed-icl-2.0"),
                output_dir=output_dir,
            )
        else:
            self.tts = self._edge_tts_fallback

        # --- Audio player ---
        self.player = AudioPlayer(use_afplay=True)

        # --- BGM ---
        bgm_cfg = self.config.get("bgm")
        if bgm_cfg.get("enabled"):
            bgm_dir = bgm_cfg.get("dir", "bgm")
            if not os.path.isabs(bgm_dir):
                bgm_dir = get_data_path(bgm_dir)
            self.bgm = BgmPlayer(
                bgm_dir=bgm_dir,
                volume=bgm_cfg.get("volume", 0.3),
                duck_volume=bgm_cfg.get("duck_volume", 0.05),
            )

        # --- Filter ---
        filter_cfg = self.config.get("filter")
        self.msg_filter = MessageFilter(
            keywords=filter_cfg["keywords"],
            min_length=filter_cfg["min_length"],
            max_length=filter_cfg["max_length"],
            cooldown=filter_cfg["cooldown_seconds"],
        )

        # --- Comment buffer & executor ---
        self.comment_buffer = CommentBuffer(max_size=100)
        self.executor = ThreadPoolExecutor(max_workers=2)

    # ---- Event callbacks ------------------------------------------------

    def _on_chat(self, data: dict):
        user = data.get("user", "未知用户")
        content = data.get("content", "")
        user_id = str(data.get("user_id", ""))

        self.stats["messages"] += 1
        logger.info(f"💬 [{user}]: {content}")

        self.event_bus.emit_sync(
            Event(
                EventType.CHAT_RECEIVED,
                {"user": user, "content": content, "user_id": user_id},
            ),
            self._loop,
        )

        if self.msg_filter and self.msg_filter.should_reply(user_id, content):
            logger.info(
                f"✅ 触发词匹配 [{user}]: {content} → 加入缓冲区 (buffer={self.comment_buffer.size + 1})"
            )
            self.comment_buffer.append(ChatTask(user=user, content=content))
        else:
            logger.info(f"⏭️ 跳过 [{user}]: {content}（未匹配触发词）")

    def _on_like(self, data: dict):
        user = data.get("user", "未知用户")
        count = data.get("count", 1)
        total = data.get("total") or 0
        self._like_buffer[user] = self._like_buffer.get(user, 0) + count
        if total:
            self._like_total = max(self._like_total, total)
        if self._like_flush_handle is None and self._loop:
            self._like_flush_handle = self._loop.call_later(
                self._like_throttle, self._flush_likes
            )

    def _flush_likes(self):
        self._like_flush_handle = None
        if not self._like_buffer:
            return
        parts = [f"{u} x{c}" for u, c in self._like_buffer.items()]
        total_count = sum(self._like_buffer.values())
        self._like_buffer.clear()
        summary = "、".join(parts[:5])
        if len(parts) > 5:
            summary += f" 等{len(parts)}人"
        logger.info(f"❤️ 点赞 +{total_count}（{summary}）")
        self.event_bus.emit_sync(
            Event(EventType.LIKE, {"count": total_count, "total": self._like_total}),
            self._loop,
        )

    def _on_gift(self, data: dict):
        user = data.get("user", "未知用户")
        gift = data.get("gift_name", "")
        count = data.get("count", 1)
        logger.info(f"🎁 [{user}] 送出 {gift} x{count}")
        self.event_bus.emit_sync(Event(EventType.GIFT, data), self._loop)

    def _on_member(self, data: dict):
        user = data.get("user", "未知用户")
        logger.info(f"👋 [{user}] 进入直播间")
        self.event_bus.emit_sync(Event(EventType.MEMBER_JOIN, data), self._loop)

    def _on_connected(self, data: dict):
        room_id = data.get("room_id", "")
        logger.info(f"已连接到直播间: {room_id}")
        self.event_bus.emit_sync(Event(EventType.CONNECTED, data), self._loop)

    # ---- Batch processing -----------------------------------------------

    async def _batch_loop(self):
        """Timer loop: drain comment buffer every *batch_interval* seconds."""
        logger.info(f"🔄 批量处理循环已启动，间隔={self._batch_interval}s")
        while self.running:
            await asyncio.sleep(self._batch_interval)
            buf_size = self.comment_buffer.size
            comments = self.comment_buffer.drain()
            if not comments:
                logger.debug(f"🔄 轮询: 缓冲区为空，跳过")
                continue

            batch = [{"user": t.user, "content": t.content} for t in comments]
            users_str = ", ".join(t.user for t in comments[:5])
            logger.info(
                f"🔄 收集到 {len(batch)} 条增量评论 [{users_str}]，开始批量处理"
            )

            await self.event_bus.emit(
                Event(
                    EventType.AI_REPLY_START,
                    {
                        "user": users_str,
                        "content": f"{len(batch)} comments",
                    },
                )
            )

            try:
                loop = asyncio.get_event_loop()
                t0 = time.time()
                lang, reply = await loop.run_in_executor(
                    self.executor, self.ai.batch_reply, batch
                )
                ai_ms = int((time.time() - t0) * 1000)

                if not reply:
                    logger.warning("🤖 [AI] 批量回复为空，跳过")
                    continue

                self.stats["ai_replies"] += 1
                logger.info(f"🤖 [AI] 批量回复完成 ({ai_ms}ms) [{lang}] → {reply}")

                await self.event_bus.emit(
                    Event(
                        EventType.AI_REPLY_DONE,
                        {
                            "user": users_str,
                            "content": f"{len(batch)} comments",
                            "reply": reply,
                            "lang": lang,
                        },
                    )
                )

                # YouTube auto-reply
                if self._auto_reply_chat and hasattr(self.danmaku, "send_message"):
                    await loop.run_in_executor(
                        self.executor,
                        self.danmaku.send_message,
                        f"{self._reply_prefix}{reply}",
                    )

                # TTS
                speak_text = reply
                logger.info(
                    f"🗣️ [TTS] 开始合成语音 (引擎: {self._tts_engine})，文本: {speak_text[:60]}..."
                )
                await self.event_bus.emit(
                    Event(EventType.TTS_START, {"text": speak_text})
                )

                t1 = time.time()
                if self._tts_engine == "volcengine":
                    audio_path = await self.tts.synthesize(speak_text, lang=lang)
                    if not audio_path:
                        logger.warning("🗣️ [TTS] 火山引擎合成失败，降级到 edge-tts")
                        audio_path = await self._edge_tts_fallback.synthesize(
                            speak_text
                        )
                else:
                    audio_path = await self.tts.synthesize(speak_text)
                tts_ms = int((time.time() - t1) * 1000)

                if not audio_path:
                    logger.error("🗣️ [TTS] 语音合成失败，无音频文件")
                    continue
                logger.info(f"🗣️ [TTS] 合成完成 ({tts_ms}ms) → {audio_path}")
                await self.event_bus.emit(
                    Event(EventType.TTS_DONE, {"audio_path": audio_path})
                )

                # Play (duck BGM while TTS speaks)
                logger.info(f"🔊 [播放] 开始播放批量回复")
                if self.bgm:
                    self.bgm.duck()
                await self.event_bus.emit(
                    Event(EventType.AUDIO_PLAYING, {"user": users_str, "reply": reply})
                )
                t2 = time.time()
                await loop.run_in_executor(self.executor, self.player.play, audio_path)
                play_ms = int((time.time() - t2) * 1000)
                if self.bgm:
                    self.bgm.unduck()
                self.stats["audio_played"] += 1
                logger.info(
                    f"🔊 [播放] 播放完成 ({play_ms}ms) | "
                    f"总计: AI {ai_ms}ms + TTS {tts_ms}ms + 播放 {play_ms}ms = {ai_ms + tts_ms + play_ms}ms"
                )
                await self.event_bus.emit(
                    Event(EventType.AUDIO_DONE, {"user": users_str})
                )
                await self._emit_stats()

            except Exception as e:
                logger.error(f"❌ 批量处理出错: {e}", exc_info=True)
                await self.event_bus.emit(
                    Event(EventType.SESSION_ERROR, {"error": str(e)})
                )

    async def _emit_stats(self):
        uptime = time.time() - self.start_time if self.start_time else 0
        await self.event_bus.emit(
            Event(EventType.STATS_UPDATE, {**self.stats, "uptime": uptime})
        )

    # ---- Lifecycle -------------------------------------------------------

    async def start(self, platform: str, **kwargs):
        if self.running:
            raise RuntimeError("会话已在运行中")

        self._init_components(platform, **kwargs)
        self.running = True
        self.start_time = time.time()
        self.stats = {"messages": 0, "ai_replies": 0, "audio_played": 0}
        self._loop = asyncio.get_running_loop()

        self.danmaku.on("chat", self._on_chat)
        self.danmaku.on("like", self._on_like)
        self.danmaku.on("gift", self._on_gift)
        self.danmaku.on("member", self._on_member)
        self.danmaku.on("connected", self._on_connected)

        logger.info(
            f"启动直播助手 — 平台: {platform}，批量间隔: {self._batch_interval}s"
        )
        await self.event_bus.emit(
            Event(EventType.SESSION_STARTED, {"platform": platform})
        )

        if self.bgm:
            bgm_file = self.config.get("bgm").get("file", "")
            self.bgm.play(bgm_file or None)
            if self.bgm.is_playing:
                await self.event_bus.emit(
                    Event(EventType.BGM_STARTED, self.bgm.get_status())
                )

        self._danmaku_task = asyncio.create_task(self.danmaku.start())
        self._process_task = asyncio.create_task(self._batch_loop())

    async def stop(self):
        if not self.running:
            return
        self.running = False
        if self.bgm and self.bgm.is_playing:
            self.bgm.stop()
            await self.event_bus.emit(Event(EventType.BGM_STOPPED, {}))
        if self.danmaku:
            self.danmaku.stop()
        for t in (self._danmaku_task, self._process_task):
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        self.platform = None
        self.start_time = None
        await self.event_bus.emit(Event(EventType.SESSION_STOPPED, {}))
        logger.info("直播助手已停止")

    def get_status(self) -> dict:
        uptime = time.time() - self.start_time if self.start_time else 0
        return {
            "running": self.running,
            "platform": self.platform,
            "uptime": uptime,
            **self.stats,
        }
