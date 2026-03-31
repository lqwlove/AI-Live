"""
直播 AI 语音助手（支持抖音 + TikTok + YouTube）
- 定时批量收集弹幕，AI 挑重点统一回复
- TTS 语音合成并播放
- YouTube 直播间自动回复消息
- 支持 LangChain Agent + 商品知识库

用法:
  python main.py --mock                              # 模拟模式
  python main.py --room 123456789                    # 抖音直播间
  python main.py --platform tiktok --user username   # TikTok 直播间
  python main.py --platform youtube --video VIDEO_ID # YouTube 直播间
  python main.py --init-config                       # 生成配置模板
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "0")

from config import Config
from danmaku.client import DouyinDanmakuClient, MockDanmakuClient
from tts.speaker import TTSSpeaker
from utils.audio_player import AudioPlayer
from utils.message_queue import ChatTask, CommentBuffer, MessageFilter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)
logger = logging.getLogger("main")


class LiveAssistant:
    """直播 AI 助手主控制器（批量回复模式）"""

    def __init__(
        self,
        config: Config,
        platform: str = "douyin",
        mock_mode: bool = False,
        room_id: str = "",
        live_url: str = "",
        tiktok_user: str = "",
        youtube_video: str = "",
        youtube_channel: str = "",
    ):
        self.config = config
        self.mock_mode = mock_mode
        self.platform = platform
        self._auto_reply_chat = False
        self._reply_prefix = ""

        if mock_mode:
            self.danmaku = MockDanmakuClient(interval=5.0)
        elif platform == "youtube":
            from danmaku.youtube_client import YouTubeDanmakuClient

            yt_cfg = config.get("youtube")
            video_id = youtube_video or yt_cfg.get("video_id", "")
            channel_id = youtube_channel or yt_cfg.get("channel_id", "")
            api_key = yt_cfg.get("api_key", "")
            client_secrets = yt_cfg.get("client_secrets_file", "")
            if not video_id and not channel_id:
                logger.error(
                    "请提供 YouTube 视频 ID (--video) 或频道 ID (--channel)，\n"
                    "或者在 config.yaml 的 youtube 段中配置"
                )
                sys.exit(1)
            if not api_key and not client_secrets:
                logger.error(
                    "请在 config.yaml 的 youtube 段中配置 api_key 或 client_secrets_file"
                )
                sys.exit(1)
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

            unique_id = tiktok_user or config.get("tiktok", "unique_id")
            if not unique_id:
                logger.error("请提供 TikTok 用户名: --user <username>")
                sys.exit(1)
            proxy = config.get("tiktok", "proxy")
            self.danmaku = TikTokDanmakuClient(unique_id, proxy=proxy)
        else:
            url_or_id = live_url or room_id or config.get("douyin", "room_id")
            if not url_or_id:
                logger.error("请提供直播间链接或 room_id")
                sys.exit(1)
            cookie = config.get("douyin", "cookie")
            self.danmaku = DouyinDanmakuClient(url_or_id, cookie=cookie)

        # --- Knowledge base ---
        self.product_store = None
        knowledge_cfg = config.get("knowledge")
        if knowledge_cfg.get("enabled"):
            from knowledge.product_store import ProductStore

            self.product_store = ProductStore(
                file_path=knowledge_cfg.get("products_file", "products.json"),
                max_match=knowledge_cfg.get("max_match_products", 3),
            )

        # --- AI (agent or simple) ---
        ai_cfg = config.get("ai")
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

        tts_cfg = config.get("tts")
        tts_engine = tts_cfg.get("engine", "edge-tts")
        self._edge_tts_fallback = TTSSpeaker(
            voice=tts_cfg["voice"],
            rate=tts_cfg["rate"],
            volume=tts_cfg["volume"],
            output_dir=tts_cfg["output_dir"],
        )
        if tts_engine == "volcengine":
            from tts.volcengine_speaker import VolcengineSpeaker

            vc_cfg = config.get("volcengine")
            self.tts = VolcengineSpeaker(
                api_key=vc_cfg.get("api_key", ""),
                app_id=vc_cfg.get("app_id", ""),
                access_token=vc_cfg.get("access_token", ""),
                speaker_id=vc_cfg["speaker_id"],
                resource_id=vc_cfg.get("resource_id", "seed-icl-2.0"),
                output_dir=tts_cfg["output_dir"],
            )
        else:
            self.tts = self._edge_tts_fallback
        self._tts_engine = tts_engine

        self.player = AudioPlayer(use_afplay=True)

        filter_cfg = config.get("filter")
        self.msg_filter = MessageFilter(
            keywords=filter_cfg["keywords"],
            min_length=filter_cfg["min_length"],
            max_length=filter_cfg["max_length"],
            cooldown=filter_cfg["cooldown_seconds"],
        )

        self.comment_buffer = CommentBuffer(max_size=100)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._running = False
        self._loop = None

        self._like_buffer: dict[str, int] = {}
        self._like_total = 0
        self._like_flush_handle: asyncio.TimerHandle | None = None
        self._like_throttle = 3.0

    def _on_chat(self, data: dict):
        user = data.get("user", "未知用户")
        content = data.get("content", "")
        user_id = str(data.get("user_id", ""))

        logger.info(f"💬 [{user}]: {content}")

        require_keywords = not self.config.get("ai").get("free_reply", False)
        if self.msg_filter.should_reply(
            user_id, content, require_keywords=require_keywords
        ):
            logger.info(
                f"✅ [{user}]: {content} → 加入缓冲区 (buffer={self.comment_buffer.size + 1})"
            )
            self.comment_buffer.append(ChatTask(user=user, content=content))
        else:
            logger.info(
                f"⏭️ 跳过 [{user}]: {content}"
                + ("（未匹配触发词或长度/冷却）" if require_keywords else "（长度或冷却限制）")
            )

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
        if self._like_total:
            logger.info(f"❤️ 点赞 +{total_count}（{summary}）累计约 {self._like_total}")
        else:
            logger.info(f"❤️ 点赞 +{total_count}（{summary}）")

    def _on_gift(self, data: dict):
        user = data.get("user", "未知用户")
        gift = data.get("gift_name", "")
        count = data.get("count", 1)
        logger.info(f"🎁 [{user}] 送出 {gift} x{count}")

    def _on_member(self, data: dict):
        user = data.get("user", "未知用户")
        logger.info(f"👋 [{user}] 进入直播间")

    def _on_connected(self, data: dict):
        room_id = data.get("room_id", "")
        logger.info(f"已连接到直播间: {room_id}")

    async def _batch_loop(self):
        """Timer loop: drain buffer every batch_interval seconds."""
        while self._running:
            await asyncio.sleep(self._batch_interval)
            comments = self.comment_buffer.drain()
            if not comments:
                continue

            batch = [{"user": t.user, "content": t.content} for t in comments]
            logger.info(f"🔄 收集到 {len(batch)} 条增量评论，开始批量处理")

            try:
                loop = asyncio.get_event_loop()
                lang, reply = await loop.run_in_executor(
                    self.executor, self.ai.batch_reply, batch
                )
                if not reply:
                    continue

                logger.info(f"🤖 [{lang}] {reply}")

                if self._auto_reply_chat and hasattr(self.danmaku, "send_message"):
                    await loop.run_in_executor(
                        self.executor,
                        self.danmaku.send_message,
                        f"{self._reply_prefix}{reply}",
                    )

                speak_text = reply
                if self._tts_engine == "volcengine":
                    audio_path = await self.tts.synthesize(speak_text, lang=lang)
                    if not audio_path:
                        logger.warning("火山 TTS 失败，降级到 edge-tts")
                        audio_path = await self._edge_tts_fallback.synthesize(
                            speak_text
                        )
                else:
                    audio_path = await self.tts.synthesize(speak_text)
                if not audio_path:
                    continue

                logger.info(f"🔊 播放回复")
                await loop.run_in_executor(self.executor, self.player.play, audio_path)

            except Exception as e:
                logger.error(f"批量处理出错: {e}")

    async def run(self):
        self._running = True
        self._loop = asyncio.get_running_loop()

        self.danmaku.on("chat", self._on_chat)
        self.danmaku.on("like", self._on_like)
        self.danmaku.on("gift", self._on_gift)
        self.danmaku.on("member", self._on_member)
        self.danmaku.on("connected", self._on_connected)

        logger.info("=" * 50)
        if self.mock_mode:
            logger.info("模拟模式启动 - 使用模拟弹幕测试完整流程")
        elif self.platform == "youtube":
            logger.info("正在连接 YouTube 直播间...")
            if self._auto_reply_chat:
                logger.info("已启用自动回复 - AI 回复将发送到直播间聊天")
        elif self.platform == "tiktok":
            logger.info("正在连接 TikTok 直播间...")
        else:
            logger.info("正在连接抖音直播间...")
        logger.info(f"批量回复间隔: {self._batch_interval}s")
        logger.info("=" * 50)

        danmaku_task = asyncio.create_task(self.danmaku.start())
        process_task = asyncio.create_task(self._batch_loop())

        try:
            await asyncio.gather(danmaku_task, process_task)
        except KeyboardInterrupt:
            logger.info("收到退出信号，正在关闭...")
        finally:
            self._running = False
            self.danmaku.stop()
            self.executor.shutdown(wait=False)
            logger.info("已退出")


def main():
    parser = argparse.ArgumentParser(
        description="直播 AI 语音助手（抖音 / TikTok / YouTube）"
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="douyin",
        choices=["douyin", "tiktok", "youtube"],
        help="平台: douyin / tiktok / youtube",
    )
    parser.add_argument("--room", type=str, default="", help="抖音直播间 room_id")
    parser.add_argument("--url", type=str, default="", help="抖音直播间链接")
    parser.add_argument(
        "--user", type=str, default="", help="TikTok 用户名 (如 @username)"
    )
    parser.add_argument("--video", type=str, default="", help="YouTube 视频 ID")
    parser.add_argument("--channel", type=str, default="", help="YouTube 频道 ID")
    parser.add_argument("--mock", action="store_true", help="使用模拟弹幕测试模式")
    parser.add_argument(
        "--config", type=str, default="config.yaml", help="配置文件路径"
    )
    parser.add_argument("--init-config", action="store_true", help="生成配置文件模板")
    args = parser.parse_args()

    config = Config(args.config)

    if args.init_config:
        config.save_template(args.config)
        return

    mock_mode = args.mock
    platform = args.platform

    if not mock_mode:
        if platform == "youtube":
            if (
                not args.video
                and not args.channel
                and not config.get("youtube", "video_id")
                and not config.get("youtube", "channel_id")
            ):
                logger.info("未指定 YouTube 视频或频道，自动进入模拟测试模式")
                mock_mode = True
        elif platform == "tiktok":
            if not args.user and not config.get("tiktok", "unique_id"):
                logger.info("未指定 TikTok 用户名，自动进入模拟测试模式")
                mock_mode = True
        else:
            if not args.room and not args.url and not config.get("douyin", "room_id"):
                logger.info("未指定直播间，自动进入模拟测试模式")
                mock_mode = True

    assistant = LiveAssistant(
        config=config,
        platform=platform,
        mock_mode=mock_mode,
        room_id=args.room,
        live_url=args.url,
        tiktok_user=args.user,
        youtube_video=args.video,
        youtube_channel=args.channel,
    )

    try:
        asyncio.run(assistant.run())
    except KeyboardInterrupt:
        logger.info("程序已退出")


if __name__ == "__main__":
    main()
