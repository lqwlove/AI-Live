"""
YouTube 直播聊天客户端
- gRPC streamList 流式接收消息（低延迟，服务端推送）
- REST API liveChatMessages.insert 发送消息（需 OAuth2）

认证模式：
  1. API Key 模式（只读）：只需 API 密钥即可监听聊天，不能发消息
  2. OAuth2 模式（读写）：需 OAuth2 客户端凭证，可监听 + 发送消息
"""

import asyncio
import logging
import os
import time
from typing import Callable

import grpc
from googleapiclient.discovery import build

from proto import stream_list_pb2, stream_list_pb2_grpc

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube"]
TOKEN_FILE = "youtube_token.json"
GRPC_TARGET = "dns:///youtube.googleapis.com:443"


class YouTubeDanmakuClient:
    """YouTube 直播聊天客户端

    支持两种认证方式:
      - api_key: 只读模式，通过 API 密钥监听聊天（公开数据）
      - client_secrets_file: 读写模式，OAuth2 授权后可发送消息
    """

    def __init__(
        self,
        video_id: str = "",
        channel_id: str = "",
        api_key: str = "",
        client_secrets_file: str = "",
        chat_warmup_seconds: float = 0.0,
    ):
        self.video_id = video_id
        self.channel_id = channel_id
        self.api_key = api_key
        self.client_secrets_file = client_secrets_file
        self._chat_warmup_seconds = max(0.0, float(chat_warmup_seconds or 0.0))
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False
        self._youtube = None
        self._live_chat_id: str | None = None
        self._credentials = None
        self._seen_msg_ids: set[str] = set()
        self._next_page_token: str | None = None
        self._readonly = True
        self._chat_emit_deadline: float | None = None

    @property
    def can_send(self) -> bool:
        return not self._readonly

    def on(self, event: str, callback: Callable):
        self._callbacks.setdefault(event, []).append(callback)

    def _emit(self, event: str, data: dict):
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"回调处理出错 [{event}]: {e}")

    # ── 认证 ─────────────────────────────────────────────────────

    def _init_auth(self):
        """根据配置选择认证方式，初始化 YouTube REST client"""
        has_oauth = self.client_secrets_file and (
            os.path.exists(self.client_secrets_file) or os.path.exists(TOKEN_FILE)
        )

        if has_oauth:
            self._init_oauth2()
        elif self.api_key:
            self._init_api_key()
        else:
            raise ValueError(
                "请提供 YouTube 认证信息：\n"
                "  - api_key: API 密钥（只读，从 Google Cloud Console 获取）\n"
                "  - client_secrets_file: OAuth2 凭证文件（读写）"
            )

    def _init_api_key(self):
        """API Key 模式：只读，不需要 OAuth2"""
        self._youtube = build("youtube", "v3", developerKey=self.api_key)
        self._readonly = True
        logger.info("YouTube 认证方式: API Key（只读模式，不支持发送消息）")

    def _init_oauth2(self):
        """OAuth2 模式：读写，支持发送消息"""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    logger.warning("Token 刷新失败，重新授权...")
                    creds = None

            if not creds:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"找不到 OAuth2 凭证文件: {self.client_secrets_file}\n"
                        "请从 Google Cloud Console 下载 OAuth2 客户端凭证。"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        self._credentials = creds
        self._youtube = build("youtube", "v3", credentials=creds)
        self._readonly = False
        logger.info("YouTube 认证方式: OAuth2（读写模式，支持发送消息）")

    def _get_access_token(self) -> str:
        """获取有效的 OAuth2 access token（仅 OAuth2 模式）"""
        from google.auth.transport.requests import Request

        if self._credentials.expired and self._credentials.refresh_token:
            self._credentials.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(self._credentials.to_json())
        return self._credentials.token

    # ── 获取 liveChatId ──────────────────────────────────────────

    def _get_live_chat_id(self) -> str | None:
        if self.video_id:
            return self._chat_id_from_video(self.video_id)
        if self.channel_id:
            return self._chat_id_from_channel(self.channel_id)
        if not self._readonly:
            return self._chat_id_from_own_broadcast()
        logger.error("API Key 模式下必须提供 video_id 或 channel_id")
        return None

    def _chat_id_from_video(self, video_id: str) -> str | None:
        resp = self._youtube.videos().list(
            part="liveStreamingDetails,snippet", id=video_id
        ).execute()
        items = resp.get("items", [])
        if not items:
            logger.error(f"找不到视频: {video_id}")
            return None
        video = items[0]
        details = video.get("liveStreamingDetails", {})
        chat_id = details.get("activeLiveChatId")
        if not chat_id:
            logger.error(f"视频 {video_id} 当前没有活跃的直播聊天")
            return None
        title = video.get("snippet", {}).get("title", "")
        logger.info(f"直播间: {title}")
        return chat_id

    def _chat_id_from_channel(self, channel_id: str) -> str | None:
        resp = self._youtube.search().list(
            part="id",
            channelId=channel_id,
            type="video",
            eventType="live",
            maxResults=1,
        ).execute()
        items = resp.get("items", [])
        if not items:
            logger.error(f"频道 {channel_id} 当前没有正在进行的直播")
            return None
        video_id = items[0]["id"]["videoId"]
        logger.info(f"找到直播视频: {video_id}")
        return self._chat_id_from_video(video_id)

    def _chat_id_from_own_broadcast(self) -> str | None:
        """从自己的频道获取当前直播（仅 OAuth2 模式）"""
        resp = self._youtube.liveBroadcasts().list(
            part="snippet", broadcastStatus="active", broadcastType="all"
        ).execute()
        items = resp.get("items", [])
        if not items:
            resp = self._youtube.liveBroadcasts().list(
                part="snippet", broadcastStatus="upcoming", broadcastType="all"
            ).execute()
            items = resp.get("items", [])
        if not items:
            logger.error("找不到自己频道的直播")
            return None
        broadcast = items[0]
        chat_id = broadcast["snippet"].get("liveChatId")
        title = broadcast["snippet"].get("title", "")
        logger.info(f"找到自己的直播: {title}")
        return chat_id

    # ── 发送消息（REST API，仅 OAuth2 模式）────────────────────

    def send_message(self, text: str) -> bool:
        """通过 REST API 发送消息到直播聊天（需要 OAuth2 认证）"""
        if self._readonly:
            logger.warning("API Key 只读模式不支持发送消息，如需发送请配置 OAuth2 凭证")
            return False
        if not self._youtube or not self._live_chat_id:
            logger.warning("YouTube API 未连接，无法发送消息")
            return False

        try:
            self._get_access_token()
            self._youtube.liveChatMessages().insert(
                part="snippet",
                body={
                    "snippet": {
                        "liveChatId": self._live_chat_id,
                        "type": "textMessageEvent",
                        "textMessageDetails": {"messageText": text},
                    }
                },
            ).execute()
            logger.info(f"✅ 已发送到直播间: {text}")
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    # ── gRPC streamList 流式接收 ─────────────────────────────────

    def _build_grpc_metadata(self) -> tuple:
        """根据认证模式构建 gRPC 请求头"""
        if self._readonly:
            return (("x-goog-api-key", self.api_key),)
        else:
            access_token = self._get_access_token()
            return (("authorization", f"Bearer {access_token}"),)

    def _create_grpc_stream(self, stub, metadata):
        request = stream_list_pb2.LiveChatMessageListRequest(
            live_chat_id=self._live_chat_id,
            part=["snippet", "authorDetails"],
            max_results=500,
        )
        if self._next_page_token:
            request.page_token = self._next_page_token

        return stub.StreamList(request, metadata=metadata)

    def _stream_messages_sync(self):
        """同步 gRPC 流式接收（在线程池中运行）"""
        ssl_creds = grpc.ssl_channel_credentials()
        error_count = 0
        max_errors = 15
        first_connect = True

        while self._running and error_count < max_errors:
            try:
                metadata = self._build_grpc_metadata()

                with grpc.secure_channel(GRPC_TARGET, ssl_creds) as channel:
                    stub = stream_list_pb2_grpc.V3DataLiveChatMessageServiceStub(channel)
                    response_stream = self._create_grpc_stream(stub, metadata)

                    if first_connect:
                        logger.info("gRPC 流式连接已建立，开始接收消息...")
                        if self._chat_warmup_seconds > 0:
                            self._chat_emit_deadline = (
                                time.monotonic() + self._chat_warmup_seconds
                            )
                            logger.info(
                                "YouTube: 开播预热 %.1fs，此期间不派发历史积压聊天；"
                                "可在配置 youtube.chat_warmup_seconds 调整，0 关闭",
                                self._chat_warmup_seconds,
                            )
                        else:
                            self._chat_emit_deadline = None
                        first_connect = False
                    else:
                        logger.debug("gRPC 流自动续连")
                    error_count = 0

                    for response in response_stream:
                        if not self._running:
                            break

                        if response.next_page_token:
                            self._next_page_token = response.next_page_token

                        for item in response.items:
                            msg_id = item.id
                            if msg_id in self._seen_msg_ids:
                                continue
                            self._seen_msg_ids.add(msg_id)
                            self._process_grpc_message(item)

                        if len(self._seen_msg_ids) > 5000:
                            keep = set(list(self._seen_msg_ids)[-2000:])
                            self._seen_msg_ids = keep

                        if response.offline_at:
                            logger.info(f"直播已结束 (offline_at: {response.offline_at})")
                            self._running = False
                            break

                if self._running:
                    logger.debug("gRPC 流正常结束，重新连接...")

            except grpc.RpcError as e:
                code = e.code()
                detail = e.details() or ""

                if code == grpc.StatusCode.NOT_FOUND:
                    logger.error(f"直播聊天不存在: {detail}")
                    break
                elif code == grpc.StatusCode.PERMISSION_DENIED:
                    logger.error(f"权限不足: {detail}")
                    break
                elif code == grpc.StatusCode.FAILED_PRECONDITION:
                    logger.warning(f"直播聊天已结束或被禁用: {detail}")
                    break
                elif code == grpc.StatusCode.RESOURCE_EXHAUSTED:
                    error_count += 1
                    wait = min(error_count * 5, 30)
                    logger.warning(f"请求过于频繁，{wait}s 后重试 ({error_count}/{max_errors})")
                    time.sleep(wait)
                elif code == grpc.StatusCode.UNAUTHENTICATED:
                    if self._readonly:
                        logger.error("API Key 无效或未启用 YouTube Data API v3")
                        break
                    logger.warning("OAuth2 认证过期，正在刷新 token...")
                    error_count += 1
                    time.sleep(1)
                else:
                    error_count += 1
                    wait = min(error_count * 3, 30)
                    logger.warning(f"gRPC 错误 [{code}]: {detail}，{wait}s 后重连 ({error_count}/{max_errors})")
                    time.sleep(wait)

            except Exception as e:
                error_count += 1
                wait = min(error_count * 3, 30)
                logger.error(f"流式接收异常: {e}，{wait}s 后重连 ({error_count}/{max_errors})")
                time.sleep(wait)

        if error_count >= max_errors:
            logger.error("连续错误过多，停止接收")

    # ── 消息处理 ─────────────────────────────────────────────────

    def _process_grpc_message(self, item):
        """处理 gRPC protobuf 消息，转为统一事件格式"""
        snippet = item.snippet
        author = item.author_details
        msg_type = snippet.type

        display_name = author.display_name or "Unknown"
        channel_id = author.channel_id or ""
        is_owner = author.is_chat_owner
        is_moderator = author.is_chat_moderator

        Type = stream_list_pb2.LiveChatMessageSnippet.TypeWrapper.Type

        if msg_type == Type.TEXT_MESSAGE_EVENT:
            text = snippet.text_message_details.message_text
            if (
                self._chat_emit_deadline is not None
                and time.monotonic() < self._chat_emit_deadline
            ):
                return
            self._emit(
                "chat",
                {
                    "user": display_name,
                    "user_id": channel_id,
                    "content": text,
                    "is_owner": is_owner,
                    "is_moderator": is_moderator,
                    "time": time.time(),
                },
            )

        elif msg_type == Type.SUPER_CHAT_EVENT:
            details = snippet.super_chat_details
            self._emit(
                "gift",
                {
                    "user": display_name,
                    "gift_name": "Super Chat",
                    "count": 1,
                    "amount": details.amount_display_string,
                    "comment": details.user_comment,
                    "time": time.time(),
                },
            )

        elif msg_type == Type.SUPER_STICKER_EVENT:
            details = snippet.super_sticker_details
            self._emit(
                "gift",
                {
                    "user": display_name,
                    "gift_name": "Super Sticker",
                    "count": 1,
                    "amount": details.amount_display_string,
                    "time": time.time(),
                },
            )

        elif msg_type == Type.NEW_SPONSOR_EVENT:
            details = snippet.new_sponsor_details
            self._emit(
                "member",
                {
                    "user": display_name,
                    "action": "became a member",
                    "level": details.member_level_name,
                    "time": time.time(),
                },
            )

        elif msg_type == Type.MEMBER_MILESTONE_CHAT_EVENT:
            details = snippet.member_milestone_chat_details
            self._emit(
                "member",
                {
                    "user": display_name,
                    "action": f"member milestone ({details.member_month} months)",
                    "comment": details.user_comment,
                    "time": time.time(),
                },
            )

        elif msg_type == Type.MEMBERSHIP_GIFTING_EVENT:
            details = snippet.membership_gifting_details
            self._emit(
                "gift",
                {
                    "user": display_name,
                    "gift_name": f"Gift Membership x{details.gift_memberships_count}",
                    "count": details.gift_memberships_count,
                    "time": time.time(),
                },
            )

        elif msg_type == Type.CHAT_ENDED_EVENT:
            logger.info("直播聊天已结束")
            self._running = False

    # ── 生命周期 ─────────────────────────────────────────────────

    async def start(self):
        self._running = True
        logger.info("正在初始化 YouTube API...")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._init_auth)
        except Exception as e:
            logger.error(f"YouTube 认证失败: {e}")
            return

        logger.info("正在查找直播聊天...")
        self._live_chat_id = await asyncio.get_event_loop().run_in_executor(
            None, self._get_live_chat_id
        )
        if not self._live_chat_id:
            logger.error("无法获取直播聊天 ID，请检查 video_id 或 channel_id 配置")
            return

        self._emit(
            "connected",
            {
                "room_id": self._live_chat_id,
                "video_id": self.video_id,
                "channel_id": self.channel_id,
            },
        )

        mode = "只读" if self._readonly else "读写"
        logger.info(f"开始 gRPC 流式监听 YouTube 直播聊天 [{mode}模式] (chat_id: {self._live_chat_id})")
        await asyncio.get_event_loop().run_in_executor(
            None, self._stream_messages_sync
        )

    def stop(self):
        self._running = False
        logger.info("YouTube 客户端已停止")
