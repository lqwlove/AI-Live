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
import uuid
from concurrent.futures import ThreadPoolExecutor

from config import Config
from core.events import Event, EventBus, EventType
from tts.speaker import TTSSpeaker
from utils.audio_player import AudioPlayer
from utils.bgm_player import BgmPlayer
from utils.message_queue import ChatTask, CommentBuffer, MessageFilter
from utils.paths import get_data_path
from utils.zh_text import append_zh_in_parens, is_primarily_chinese

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when required configuration is missing."""


class LiveEngine:
    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        announcement_store=None,
    ):
        self.config = config
        self.event_bus = event_bus
        self.announcement_store = announcement_store
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
        self._announce_task: asyncio.Task | None = None
        self._bgm_skip_autostart = False
        self._bgm_start_basename: str | None = None

        audio_cfg = self.config.get("audio")
        self.voice_volume = float(audio_cfg.get("voice_volume", 1.0))
        ann_cfg = self.config.get("announce")
        self._announce_interval = float(ann_cfg.get("interval_seconds", 30))
        self.announce_enabled = False
        self.announce_active_ids: list[str] = []
        self.announce_hold = False
        self._voice_lock: asyncio.Lock | None = None
        self._to_zh = None
        self._translation_tasks: set[asyncio.Task] = set()

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
                chat_warmup_seconds=float(
                    yt_cfg.get("chat_warmup_seconds", 2.0) or 0.0
                ),
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

            dy_cfg = self.config.get("douyin")
            room_id = (
                kwargs.get("room_id")
                or kwargs.get("live_url")
                or dy_cfg.get("room_id")
                or dy_cfg.get("live_url")
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

        self._to_zh = None
        if ai_cfg.get("translate_display", True):
            from ai.to_zh_translator import ToZhTranslator

            self._to_zh = ToZhTranslator(
                api_key=ai_cfg.get("api_key", ""),
                base_url=ai_cfg.get("base_url", ""),
                model=ai_cfg.get("model", "gpt-4o-mini"),
            )

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
        bgm_file_param = kwargs.get("bgm_file")
        bgm_dir = bgm_cfg.get("dir", "bgm")
        if not os.path.isabs(bgm_dir):
            bgm_dir = get_data_path(bgm_dir)

        self._bgm_skip_autostart = False
        self._bgm_start_basename = None
        if bgm_file_param is not None:
            if isinstance(bgm_file_param, str) and bgm_file_param.strip() == "":
                self._bgm_skip_autostart = True
            elif isinstance(bgm_file_param, str) and bgm_file_param.strip():
                self._bgm_start_basename = os.path.basename(bgm_file_param.strip())

        want_bgm_player = bool(bgm_cfg.get("enabled")) or (
            self._bgm_start_basename is not None
        )

        if want_bgm_player:
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
        if not self.running:
            return
        user = data.get("user", "未知用户")
        content = data.get("content", "")
        user_id = str(data.get("user_id", ""))

        self.stats["messages"] += 1
        logger.info(f"💬 [{user}]: {content}")

        msg_uid = uuid.uuid4().hex
        payload: dict = {
            "user": user,
            "content": content,
            "user_id": user_id,
            "msg_uid": msg_uid,
        }
        ts = time.time()
        ai_cfg = self.config.get("ai")
        need_translate = (
            ai_cfg.get("translate_display", True)
            and self._to_zh
            and self._to_zh.available
            and not is_primarily_chinese(content)
        )
        if need_translate:
            self._schedule_chat_received_with_translation(payload, ts, content)
        else:
            ev = Event(EventType.CHAT_RECEIVED, payload, timestamp=ts)
            self.event_bus.emit_sync(ev, self._loop)

        pause_any = self.config.get("announce", "pause_on_any_chat")
        if pause_any:
            self.announce_hold = True

        require_keywords = not ai_cfg.get("free_reply", False)
        if self.msg_filter and self.msg_filter.should_reply(
            user_id, content, require_keywords=require_keywords
        ):
            mode = "触发词" if require_keywords else "自由回复"
            logger.info(
                f"✅ [{mode}] [{user}]: {content} → 加入缓冲区 (buffer={self.comment_buffer.size + 1})"
            )
            self.comment_buffer.append(ChatTask(user=user, content=content))
            self.announce_hold = True
        else:
            if require_keywords:
                logger.info(f"⏭️ 跳过 [{user}]: {content}（未匹配触发词或长度/冷却）")
            else:
                logger.info(f"⏭️ 跳过 [{user}]: {content}（长度或冷却限制）")

    def _schedule_chat_received_with_translation(
        self, payload: dict, ts: float, content: str
    ):
        """非中文：先译再发一条 chat_received，content 为 原文(译文)。"""
        if not self._loop or not self.running:
            return
        msg_uid = str(payload.get("msg_uid", ""))

        async def _run():
            if not self.running or not self.executor:
                return
            out = dict(payload)
            try:
                loop = asyncio.get_event_loop()
                zh = await loop.run_in_executor(
                    self.executor, self._to_zh.translate, content
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("弹幕翻译任务失败: %s", e)
                zh = ""
            if not self.running:
                return
            out["content"] = append_zh_in_parens(content, zh) if zh else content
            if not self.running:
                return
            await self.event_bus.emit(
                Event(EventType.CHAT_RECEIVED, out, timestamp=ts)
            )
            logger.info(
                "chat_received 已投递(括号译文=%s) msg_uid=%s 预览=%s",
                "有" if zh else "无",
                msg_uid[:12],
                out["content"][:48],
            )

        def _cb():
            if not self.running:
                return
            task = asyncio.create_task(_run())
            self._translation_tasks.add(task)
            task.add_done_callback(self._translation_tasks.discard)

        self._loop.call_soon_threadsafe(_cb)

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

    def _play_voice_path_sync(self, path: str):
        if self.bgm:
            self.bgm.duck()
        try:
            self.player.play(path, self.voice_volume)
        finally:
            if self.bgm:
                self.bgm.unduck()

    async def _play_voice_path(self, path: str, *, preempt: bool = False) -> None:
        """串行播放人声；preempt=True 时先 stop() 打断当前口播/人声，再抢锁播放（AI 优先）。"""
        if preempt:
            self.player.stop()
        loop = asyncio.get_event_loop()
        async with self._voice_lock:
            await loop.run_in_executor(self.executor, self._play_voice_path_sync, path)

    def _resolve_announce_texts(self) -> list[str]:
        if not self.announcement_store or not self.announce_active_ids:
            return []
        texts: list[str] = []
        for iid in self.announce_active_ids:
            item = self.announcement_store.get_by_id(iid)
            if item and item.enabled and item.text.strip():
                texts.append(item.text.strip())
        return texts

    async def _announce_loop(self):
        logger.info("📢 自动播报循环已启动")
        idx = 0
        ann_lang = self.config.get("announce", "lang") or "zh"
        while self.running:
            await asyncio.sleep(0.2)
            if not self.announce_enabled or not self.announcement_store:
                await asyncio.sleep(0.8)
                continue
            texts = self._resolve_announce_texts()
            if not texts:
                await asyncio.sleep(0.8)
                continue

            while self.announce_hold and self.running:
                await asyncio.sleep(0.1)
            if not self.running:
                break

            line = texts[idx % len(texts)]
            idx += 1

            await self.event_bus.emit(
                Event(
                    EventType.ANNOUNCE_START,
                    {"text": line[:200]},
                )
            )
            logger.info(f"📢 [自动播报] 合成: {line[:80]}...")
            audio_path = ""
            try:
                if self._tts_engine == "volcengine":
                    audio_path = await self.tts.synthesize(line, lang=ann_lang)
                    if not audio_path:
                        audio_path = await self._edge_tts_fallback.synthesize(line)
                else:
                    audio_path = await self.tts.synthesize(line)
            except Exception as e:
                logger.error(f"📢 [自动播报] 合成出错: {e}", exc_info=True)
                await self.event_bus.emit(
                    Event(EventType.ANNOUNCE_DONE, {"ok": False, "error": str(e)})
                )
                await asyncio.sleep(self._announce_interval)
                continue

            if not audio_path:
                logger.warning("📢 [自动播报] TTS 失败，跳过本条")
                await self.event_bus.emit(Event(EventType.ANNOUNCE_DONE, {"ok": False}))
                await asyncio.sleep(self._announce_interval)
                continue

            while self.announce_hold and self.running:
                await asyncio.sleep(0.1)
            if not self.running:
                break
            try:
                await self._play_voice_path(audio_path, preempt=False)
                self.stats["audio_played"] += 1
                await self.event_bus.emit(Event(EventType.ANNOUNCE_DONE, {"ok": True}))
                await self._emit_stats()
            except Exception as e:
                logger.error(f"📢 [自动播报] 播放出错: {e}", exc_info=True)
                await self.event_bus.emit(
                    Event(EventType.ANNOUNCE_DONE, {"ok": False, "error": str(e)})
                )

            await asyncio.sleep(self._announce_interval)

    async def _batch_loop(self):
        """Timer loop: drain comment buffer every *batch_interval* seconds."""
        logger.info(f"🔄 批量处理循环已启动，间隔={self._batch_interval}s")
        pause_any = self.config.get("announce", "pause_on_any_chat")
        while self.running:
            await asyncio.sleep(self._batch_interval)
            comments = self.comment_buffer.drain()
            try:
                if not comments:
                    if pause_any:
                        self.announce_hold = False
                    logger.debug("🔄 轮询: 缓冲区为空，跳过")
                    continue

                self.announce_hold = True
                self.player.stop()

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

                loop = asyncio.get_event_loop()
                t0 = time.time()
                lang, reply = await loop.run_in_executor(
                    self.executor, self.ai.batch_reply, batch
                )
                ai_ms = int((time.time() - t0) * 1000)

                if not self.running:
                    logger.debug("会话已停止，跳过本次批量后续步骤（AI 请求可能仍在收尾）")
                    continue

                if not reply:
                    logger.warning("🤖 [AI] 批量回复为空，跳过")
                    continue

                self.stats["ai_replies"] += 1
                logger.info(f"🤖 [AI] 批量回复完成 ({ai_ms}ms) [{lang}] → {reply}")

                reply_zh = ""
                ai_cfg = self.config.get("ai")
                if (
                    self._to_zh
                    and self._to_zh.available
                    and ai_cfg.get("translate_display", True)
                    and not is_primarily_chinese(reply)
                ):
                    reply_zh = await loop.run_in_executor(
                        self.executor, self._to_zh.translate, reply
                    )

                if not self.running:
                    logger.debug("会话已停止，跳过回复翻译与 TTS")
                    continue

                reply_for_ui = (
                    append_zh_in_parens(reply, reply_zh) if reply_zh else reply
                )
                done_payload: dict = {
                    "user": users_str,
                    "content": f"{len(batch)} comments",
                    "reply": reply_for_ui,
                    "lang": lang,
                }
                await self.event_bus.emit(
                    Event(EventType.AI_REPLY_DONE, done_payload)
                )

                if self._auto_reply_chat and hasattr(self.danmaku, "send_message"):
                    await loop.run_in_executor(
                        self.executor,
                        self.danmaku.send_message,
                        f"{self._reply_prefix}{reply}",
                    )

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

                logger.info("🔊 [播放] 打断口播并优先播放 AI 回复")
                await self.event_bus.emit(
                    Event(EventType.AUDIO_PLAYING, {"user": users_str, "reply": reply})
                )
                t2 = time.time()
                await self._play_voice_path(audio_path, preempt=True)
                play_ms = int((time.time() - t2) * 1000)
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
            finally:
                self.announce_hold = False

    async def _emit_stats(self):
        uptime = time.time() - self.start_time if self.start_time else 0
        await self.event_bus.emit(
            Event(EventType.STATS_UPDATE, {**self.stats, "uptime": uptime})
        )

    # ---- Lifecycle -------------------------------------------------------

    def ensure_bgm_player(self) -> BgmPlayer | None:
        """直播中按需创建 BGM（例如开播时未启用，中途再切歌）。"""
        if self.bgm is not None:
            return self.bgm
        if not self.running:
            return None
        bgm_cfg = self.config.get("bgm")
        bgm_dir = bgm_cfg.get("dir", "bgm")
        if not os.path.isabs(bgm_dir):
            bgm_dir = get_data_path(bgm_dir)
        self.bgm = BgmPlayer(
            bgm_dir=bgm_dir,
            volume=bgm_cfg.get("volume", 0.3),
            duck_volume=bgm_cfg.get("duck_volume", 0.05),
        )
        return self.bgm

    async def start(self, platform: str, **kwargs):
        if self.running:
            raise RuntimeError("会话已在运行中")

        self._init_components(platform, **kwargs)
        self.running = True
        self.start_time = time.time()
        self.stats = {"messages": 0, "ai_replies": 0, "audio_played": 0}
        self._loop = asyncio.get_running_loop()
        self._voice_lock = asyncio.Lock()

        audio_cfg = self.config.get("audio")
        self.voice_volume = float(audio_cfg.get("voice_volume", 1.0))
        ann_cfg = self.config.get("announce")
        self._announce_interval = float(ann_cfg.get("interval_seconds", 30))

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
            if self._bgm_skip_autostart:
                pass
            elif self._bgm_start_basename:
                path = os.path.join(self.bgm.bgm_dir, self._bgm_start_basename)
                if os.path.isfile(path):
                    self.bgm.play(path)
                else:
                    logger.warning(
                        f"[BGM] 所选文件不存在: {self._bgm_start_basename}"
                    )
            else:
                bgm_file = self.config.get("bgm").get("file", "")
                self.bgm.play(bgm_file or None)
            if self.bgm.is_playing:
                await self.event_bus.emit(
                    Event(EventType.BGM_STARTED, self.bgm.get_status())
                )

        self._danmaku_task = asyncio.create_task(self.danmaku.start())
        self._process_task = asyncio.create_task(self._batch_loop())
        self._announce_task = asyncio.create_task(self._announce_loop())

    async def stop(self):
        if not self.running:
            return
        self.running = False

        pending_tr = list(self._translation_tasks)
        for t in pending_tr:
            t.cancel()
        if pending_tr:
            await asyncio.gather(*pending_tr, return_exceptions=True)

        if self.bgm and self.bgm.is_playing:
            self.bgm.stop()
            await self.event_bus.emit(Event(EventType.BGM_STOPPED, {}))
        if self.danmaku:
            self.danmaku.stop()
        for t in (self._danmaku_task, self._process_task, self._announce_task):
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        self._announce_task = None
        if self.executor:
            try:
                self.executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
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
