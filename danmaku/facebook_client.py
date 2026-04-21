"""
Facebook 直播聊天客户端
- SSE streaming-graph 流式接收评论（低延迟，服务端推送）
- Graph API 发送评论回复
- 自动刷新 Access Token（短期 → 长期）

认证：需要 Facebook App ID、App Secret 和初始 Access Token。
Token 刷新逻辑：
  1. 启动时尝试将短期 token 交换为长期 token（60 天有效）
  2. 用长期用户 token 获取 Page Access Token（永不过期）
  3. API 调用失败时自动重试刷新
"""

import asyncio
import json
import logging
import time
from typing import Callable

import requests

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v25.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
STREAMING_BASE = f"https://streaming-graph.facebook.com/{GRAPH_API_VERSION}"


class FacebookDanmakuClient:
    """Facebook 直播聊天客户端（Graph API + SSE）"""

    def __init__(
        self,
        page_id: str = "",
        live_video_id: str = "",
        access_token: str = "",
        app_id: str = "",
        app_secret: str = "",
        auto_reply: bool = False,
        reply_prefix: str = "",
        proxy: str = "",
    ):
        self.page_id = page_id
        self.live_video_id = live_video_id
        self._access_token = access_token
        self._app_id = app_id
        self._app_secret = app_secret
        self.auto_reply = auto_reply
        self.reply_prefix = reply_prefix

        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False
        self._seen_comment_ids: set[str] = set()
        self._page_access_token: str | None = None
        self._token_refreshed = False

        self._session = requests.Session()
        if proxy:
            self._session.proxies = {"http": proxy, "https": proxy}
            logger.info("Facebook 客户端使用代理: %s", proxy)

    @property
    def access_token(self) -> str:
        return self._page_access_token or self._access_token

    def on(self, event: str, callback: Callable):
        self._callbacks.setdefault(event, []).append(callback)

    def _emit(self, event: str, data: dict):
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"回调处理出错 [{event}]: {e}")

    # ── Token 管理 ─────────────────────────────────────────────

    def _exchange_long_lived_token(self) -> str | None:
        """将短期 token 交换为长期 token（约 60 天有效）"""
        if not self._app_id or not self._app_secret:
            logger.debug("未提供 app_id/app_secret，跳过 token 交换")
            return None
        try:
            resp = self._session.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self._app_id,
                    "client_secret": self._app_secret,
                    "fb_exchange_token": self._access_token,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            new_token = data.get("access_token")
            if new_token:
                expires_in = data.get("expires_in", 0)
                logger.info(
                    "已交换为长期 token (有效期 %d 天)",
                    expires_in // 86400 if expires_in else 0,
                )
                return new_token
        except Exception as e:
            logger.warning(f"token 交换失败: {e}")
        return None

    def _get_page_access_token(self) -> str | None:
        """用用户 token 获取 Page Access Token（永不过期）"""
        if not self.page_id:
            return None
        try:
            resp = self._session.get(
                f"{GRAPH_API_BASE}/{self.page_id}",
                params={
                    "fields": "access_token,name",
                    "access_token": self._access_token,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            page_token = data.get("access_token")
            page_name = data.get("name", "")
            if page_token:
                logger.info("已获取页面 '%s' 的 Page Access Token", page_name)
                return page_token
        except Exception as e:
            logger.warning(f"获取 Page Access Token 失败: {e}")
        return None

    def _refresh_tokens(self):
        """刷新 token 链（仅首次有效，避免重复交换）"""
        if self._token_refreshed:
            logger.debug("token 已刷新过，跳过重复交换")
            return

        orig_preview = self._access_token[:20] + "..." if self._access_token else "(empty)"
        logger.info("开始刷新 token 链, 原始 token=%s, page_id=%s", orig_preview, self.page_id or "(空)")

        long_token = self._exchange_long_lived_token()
        if long_token:
            new_preview = long_token[:20] + "..."
            logger.info("长期 token 交换成功: %s → %s", orig_preview, new_preview)
            self._access_token = long_token
        else:
            logger.warning("长期 token 交换失败，继续使用原始 token")

        page_token = self._get_page_access_token()
        if page_token:
            page_preview = page_token[:20] + "..."
            logger.info("Page Access Token 获取成功: %s", page_preview)
            self._page_access_token = page_token
        else:
            logger.info("未获取 Page Access Token (page_id=%s)", self.page_id or "空")

        final_preview = self.access_token[:20] + "..." if self.access_token else "(empty)"
        logger.info("token 刷新完成，最终使用 token=%s", final_preview)
        self._token_refreshed = True

    def _check_token_error(self, resp: requests.Response) -> bool:
        """检查响应是否为 token 过期错误，尝试刷新后返回是否已修复"""
        if resp.status_code not in (400, 401):
            return False
        try:
            err = resp.json().get("error", {})
        except Exception:
            return False
        code = err.get("code", 0)
        subcode = err.get("error_subcode", 0)
        if code == 190 or subcode in (463, 467):
            logger.warning("Access Token 已过期 (code=%s, subcode=%s)，尝试刷新...", code, subcode)
            self._refresh_tokens()
            return True
        return False

    # ── 获取直播视频 ID ────────────────────────────────────────

    def _resolve_live_video_id(self) -> str | None:
        if self.live_video_id:
            return self.live_video_id
        if not self.page_id:
            return None
        max_retries = 2
        for attempt in range(max_retries):
            try:
                resp = self._session.get(
                    f"{GRAPH_API_BASE}/{self.page_id}/live_videos",
                    params={
                        "access_token": self.access_token,
                        "broadcast_status": '["LIVE"]',
                        "fields": "id,title,status",
                    },
                    timeout=30,
                )
                if self._check_token_error(resp) and attempt < max_retries - 1:
                    continue
                resp.raise_for_status()
                items = resp.json().get("data", [])
                if not items:
                    logger.error("页面 %s 当前没有正在进行的直播", self.page_id)
                    return None
                vid = items[0]["id"]
                title = items[0].get("title", "")
                logger.info("找到 Facebook 直播: %s (id=%s)", title or "(无标题)", vid)
                return vid
            except requests.HTTPError as e:
                logger.error(f"查找直播视频失败: {e}")
                return None
            except Exception as e:
                logger.error(f"查找直播视频异常: {e}")
                return None
        return None

    # ── SSE 实时接收评论 ───────────────────────────────────────

    def _stream_comments_sync(self):
        """先尝试 SSE 流式接收评论，失败则回退到 Graph API 轮询"""
        if self._try_sse_stream():
            return
        logger.info("SSE 不可用，回退到 Graph API 轮询模式")
        self._poll_comments_sync()

    def _try_sse_stream(self) -> bool:
        """通过 SSE 流实时接收评论，返回 True 表示正常结束（直播已结束）"""
        url = f"{STREAMING_BASE}/{self.live_video_id}/live_comments"
        error_count = 0
        max_errors = 10
        auth_failures = 0

        token_preview = self.access_token[:20] + "..." if self.access_token else "(empty)"
        logger.info(
            "SSE 连接参数: url=%s, token=%s, proxy=%s",
            url, token_preview, self._session.proxies or "无",
        )

        while self._running and error_count < max_errors:
            try:
                params = {
                    "access_token": self.access_token,
                    "fields": "from{id,name},message,created_time",
                    "comment_rate": "ten_per_second",
                }
                logger.debug("SSE 请求: GET %s (token=%s)", url, token_preview)
                resp = self._session.get(
                    url,
                    params=params,
                    stream=True,
                    timeout=(30, None),
                )

                logger.info(
                    "SSE 响应: HTTP %s, headers=%s",
                    resp.status_code,
                    {k: v for k, v in resp.headers.items() if k.lower() in ("content-type", "www-authenticate", "x-fb-trace-id")},
                )

                if resp.status_code in (400, 401):
                    error_count += 1
                    auth_failures += 1
                    body = ""
                    try:
                        body = resp.text[:1000]
                    except Exception:
                        pass
                    logger.warning(
                        "SSE 认证失败 (HTTP %s): %s (%d/%d)",
                        resp.status_code, body, error_count, max_errors,
                    )
                    if auth_failures == 1:
                        self._refresh_tokens()
                    if auth_failures >= 3:
                        logger.warning("SSE 连续认证失败 %d 次，放弃 SSE 模式", auth_failures)
                        return False
                    wait = min(auth_failures * 5, 15)
                    time.sleep(wait)
                    continue

                if resp.status_code == 404:
                    logger.error("SSE 端点返回 404，直播可能不存在或已结束")
                    return False

                resp.raise_for_status()

                error_count = 0
                auth_failures = 0
                logger.info("SSE 评论流已建立，开始接收...")

                for line in resp.iter_lines(decode_unicode=True):
                    if not self._running:
                        break
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data: "):
                        self._handle_sse_comment(line[6:])

                if self._running:
                    logger.debug("SSE 流正常结束，重新连接...")

            except requests.HTTPError as e:
                error_count += 1
                status = getattr(e.response, "status_code", 0) if e.response is not None else 0
                body = ""
                try:
                    body = e.response.text[:500] if e.response is not None else ""
                except Exception:
                    pass
                if status == 404:
                    logger.error("直播视频不存在或已结束")
                    return True
                wait = min(error_count * 5, 30)
                logger.warning(
                    "SSE 请求失败 (HTTP %s): %s | body: %s，%ds 后重连 (%d/%d)",
                    status, e, body, wait, error_count, max_errors,
                )
                time.sleep(wait)

            except Exception as e:
                error_count += 1
                wait = min(error_count * 5, 30)
                logger.warning(
                    "SSE 评论流异常: %s，%ds 后重连 (%d/%d)",
                    e, wait, error_count, max_errors,
                )
                time.sleep(wait)

        if error_count >= max_errors:
            logger.error("SSE 连续错误过多，尝试回退")
            return False
        return True

    def _poll_comments_sync(self):
        """通过 Graph API 轮询评论（SSE 不可用时的回退方案）"""
        url = f"{GRAPH_API_BASE}/{self.live_video_id}/comments"
        poll_interval = 3
        error_count = 0
        max_errors = 20
        after_cursor = ""

        token_preview = self.access_token[:20] + "..." if self.access_token else "(empty)"
        logger.info(
            "开始 Graph API 轮询评论 (间隔 %ds), url=%s, token=%s",
            poll_interval, url, token_preview,
        )

        while self._running and error_count < max_errors:
            try:
                params = {
                    "access_token": self.access_token,
                    "fields": "from{id,name},message,created_time",
                    "order": "chronological",
                    "limit": 50,
                }
                if after_cursor:
                    params["after"] = after_cursor

                resp = self._session.get(url, params=params, timeout=20)

                if resp.status_code in (400, 401):
                    error_count += 1
                    body = ""
                    try:
                        body = resp.text[:1000]
                    except Exception:
                        pass
                    logger.warning("轮询认证失败 (HTTP %s): %s (%d/%d)",
                                   resp.status_code, body, error_count, max_errors)
                    if error_count == 1:
                        self._token_refreshed = False
                        self._refresh_tokens()
                    time.sleep(min(error_count * 5, 30))
                    continue

                resp.raise_for_status()
                error_count = 0
                data = resp.json()

                for comment in data.get("data", []):
                    comment_id = comment.get("id", "")
                    if comment_id and comment_id not in self._seen_comment_ids:
                        self._seen_comment_ids.add(comment_id)
                        sender = comment.get("from", {})
                        self._emit("chat", {
                            "user": sender.get("name", "Unknown"),
                            "user_id": sender.get("id", ""),
                            "content": comment.get("message", ""),
                            "time": time.time(),
                        })

                paging = data.get("paging", {})
                cursors = paging.get("cursors", {})
                after_cursor = cursors.get("after", after_cursor)

                if len(self._seen_comment_ids) > 5000:
                    self._seen_comment_ids = set(list(self._seen_comment_ids)[-2000:])

            except requests.HTTPError as e:
                error_count += 1
                body = ""
                try:
                    body = e.response.text[:1000] if e.response is not None else ""
                except Exception:
                    pass
                logger.warning("轮询评论 HTTP 错误: %s | body: %s (%d/%d)", e, body, error_count, max_errors)
            except Exception as e:
                error_count += 1
                logger.warning("轮询评论异常: %s (%d/%d)", e, error_count, max_errors)

            time.sleep(poll_interval)

        if error_count >= max_errors:
            logger.error("轮询连续错误过多，停止接收")

    def _handle_sse_comment(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        comment_id = data.get("id", "")
        if comment_id in self._seen_comment_ids:
            return
        self._seen_comment_ids.add(comment_id)
        if len(self._seen_comment_ids) > 5000:
            self._seen_comment_ids = set(list(self._seen_comment_ids)[-2000:])

        sender = data.get("from", {})
        self._emit("chat", {
            "user": sender.get("name", "Unknown"),
            "user_id": sender.get("id", ""),
            "content": data.get("message", ""),
            "time": time.time(),
        })

    # ── 轮询 reactions（可选补充）─────────────────────────────

    def _poll_reactions_sync(self):
        """定期轮询 reactions 作为 like 事件"""
        last_total = 0
        while self._running:
            time.sleep(10)
            if not self._running:
                break
            try:
                resp = self._session.get(
                    f"{GRAPH_API_BASE}/{self.live_video_id}/reactions",
                    params={
                        "access_token": self.access_token,
                        "summary": "true",
                        "limit": 0,
                    },
                    timeout=20,
                )
                if resp.status_code == 200:
                    total = resp.json().get("summary", {}).get("total_count", 0)
                    if total > last_total:
                        delta = total - last_total
                        last_total = total
                        self._emit("like", {
                            "user": "",
                            "count": delta,
                            "total": total,
                        })
            except Exception:
                pass

    # ── 发送消息（Graph API）──────────────────────────────────

    def send_message(self, text: str) -> bool:
        """通过 Graph API 发送评论到直播视频"""
        if not self.live_video_id:
            return False
        try:
            resp = self._session.post(
                f"{GRAPH_API_BASE}/{self.live_video_id}/comments",
                params={"access_token": self.access_token},
                json={"message": text},
                timeout=30,
            )
            if self._check_token_error(resp):
                resp = self._session.post(
                    f"{GRAPH_API_BASE}/{self.live_video_id}/comments",
                    params={"access_token": self.access_token},
                    json={"message": text},
                    timeout=30,
                )
            resp.raise_for_status()
            logger.info("已发送到 Facebook 直播间: %s", text[:80])
            return True
        except Exception as e:
            logger.error("发送消息失败: %s", e)
            return False

    # ── 生命周期 ──────────────────────────────────────────────

    async def start(self):
        self._running = True
        logger.info("正在初始化 Facebook Live API...")

        loop = asyncio.get_event_loop()

        await loop.run_in_executor(None, self._refresh_tokens)

        video_id = await loop.run_in_executor(None, self._resolve_live_video_id)
        if not video_id:
            logger.error("无法获取 Facebook 直播视频 ID，请检查 page_id 或 live_video_id 配置")
            return
        self.live_video_id = video_id

        self._emit("connected", {
            "room_id": self.live_video_id,
            "page_id": self.page_id,
        })

        mode = "读写" if self.auto_reply else "只读"
        logger.info(
            "开始 SSE 流式监听 Facebook 直播评论 [%s模式] (video_id: %s)",
            mode, self.live_video_id,
        )

        reaction_task = loop.run_in_executor(None, self._poll_reactions_sync)
        try:
            await loop.run_in_executor(None, self._stream_comments_sync)
        finally:
            self._running = False
            reaction_task.cancel()

    def stop(self):
        self._running = False
        logger.info("Facebook 客户端已停止")
