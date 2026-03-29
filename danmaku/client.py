import asyncio
import gzip
import hashlib
import logging
import os
import random
import re
import string
import subprocess
import threading
import time
import urllib.parse
from typing import Callable

import requests
import websocket

from proto.douyin import (
    PushFrame, Response, ChatMessage, GiftMessage,
    LikeMessage, MemberMessage, SocialMessage,
    RoomUserSeqMessage, ControlMessage,
)
from ac_signature import get__ac_signature
from utils.paths import get_bundle_dir

logger = logging.getLogger(__name__)


def generate_ms_token(length=182):
    base_str = string.ascii_letters + string.digits + '-_'
    return ''.join(random.choice(base_str) for _ in range(length))


def generate_signature(wss_url):
    params = (
        "live_id,aid,version_code,webcast_sdk_version,"
        "room_id,sub_room_id,sub_channel_id,did_rule,"
        "user_unique_id,device_platform,device_type,ac,identity"
    ).split(',')
    wss_params = urllib.parse.urlparse(wss_url).query.split('&')
    wss_maps = {p.split('=')[0]: p.split('=')[-1] for p in wss_params}
    tpl_params = [f"{k}={wss_maps.get(k, '')}" for k in params]
    param_str = ','.join(tpl_params)
    md5_param = hashlib.md5(param_str.encode()).hexdigest()

    wrapper_path = os.path.join(get_bundle_dir(), 'sign_wrapper.js')
    try:
        result = subprocess.run(
            ['node', wrapper_path, md5_param],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logger.error(f"签名脚本执行失败: {result.stderr}")
    except FileNotFoundError:
        logger.error("Node.js 未安装，请安装: brew install node")
    except Exception as e:
        logger.error(f"签名生成失败: {e}")
    return None


class DouyinDanmakuClient:
    """抖音直播弹幕 WebSocket 客户端（基于 websocket-client 同步实现）"""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, live_url_or_room_id: str, cookie: str = ""):
        self.live_id = self._extract_live_id(live_url_or_room_id)
        self.cookie = cookie
        self._ttwid = None
        self._room_id = None
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False
        self.ws = None
        self.session = requests.Session()

    def _extract_live_id(self, url_or_id: str) -> str:
        url_or_id = url_or_id.strip()
        if url_or_id.isdigit():
            return url_or_id
        match = re.search(r"live\.douyin\.com/(\d+)", url_or_id)
        if match:
            return match.group(1)
        match = re.search(r"(\d{8,})", url_or_id)
        if match:
            return match.group(1)
        # Douyin short links (v.douyin.com/xxx) need redirect resolution
        if "douyin.com" in url_or_id:
            resolved = self._resolve_short_url(url_or_id)
            if resolved:
                match = re.search(r"live\.douyin\.com/(\d+)", resolved)
                if match:
                    return match.group(1)
                match = re.search(r"(\d{8,})", resolved)
                if match:
                    return match.group(1)
        raise ValueError(f"无法从 '{url_or_id}' 提取直播间ID")

    @staticmethod
    def _resolve_short_url(short_url: str) -> str | None:
        try:
            resp = requests.head(
                short_url,
                headers={"User-Agent": "Mozilla/5.0"},
                allow_redirects=True,
                timeout=10,
            )
            resolved = resp.url
            logger.info(f"短链接解析: {short_url} → {resolved}")
            return resolved
        except Exception as e:
            logger.error(f"短链接解析失败: {e}")
            return None

    def on(self, event: str, callback: Callable):
        self._callbacks.setdefault(event, []).append(callback)

    def _emit(self, event: str, data: dict):
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"回调处理出错 [{event}]: {e}")

    @property
    def ttwid(self) -> str:
        if self._ttwid:
            return self._ttwid
        try:
            resp = self.session.get(
                "https://live.douyin.com/",
                headers={"User-Agent": self.USER_AGENT},
                timeout=10,
            )
            resp.raise_for_status()
            self._ttwid = resp.cookies.get("ttwid")
            if self._ttwid:
                logger.info(f"获取到 ttwid: {self._ttwid[:20]}...")
            else:
                logger.warning("未从首页获取到 ttwid")
        except Exception as e:
            logger.error(f"获取 ttwid 失败: {e}")
        return self._ttwid

    @property
    def room_id(self) -> str:
        """从直播间页面提取真正的 room_id（和 URL 中的 live_id 可能不同）"""
        if self._room_id:
            return self._room_id
        url = f"https://live.douyin.com/{self.live_id}"
        headers = {
            "User-Agent": self.USER_AGENT,
            "Cookie": f"ttwid={self.ttwid}&msToken={generate_ms_token()}; __ac_nonce=0123407cc00a9e438deb4",
        }
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            match = re.search(r'roomId\\":\\"(\d+)\\"', resp.text)
            if match:
                self._room_id = match.group(1)
                logger.info(f"提取到 room_id: {self._room_id}")
            else:
                logger.warning("未从页面提取到 roomId，使用 live_id 作为 room_id")
                self._room_id = self.live_id
        except Exception as e:
            logger.error(f"获取 room_id 失败: {e}")
            self._room_id = self.live_id
        return self._room_id

    def _build_wss_url(self) -> str:
        rid = self.room_id
        wss = (
            "wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/"
            "?app_name=douyin_web"
            "&version_code=180800"
            "&webcast_sdk_version=1.0.14-beta.0"
            "&update_version_code=1.0.14-beta.0"
            "&compress=gzip"
            "&device_platform=web"
            "&cookie_enabled=true"
            "&screen_width=1536&screen_height=864"
            "&browser_language=zh-CN"
            "&browser_platform=MacIntel"
            "&browser_name=Mozilla"
            "&browser_version=5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2010_15_7)%20AppleWebKit/537.36%20"
            "(KHTML,%20like%20Gecko)%20Chrome/131.0.0.0%20Safari/537.36"
            "&browser_online=true"
            "&tz_name=Asia/Shanghai"
            "&cursor=d-1_u-1_fh-7392091211001140287_t-1721106114633_r-1"
            f"&internal_ext=internal_src:dim|wss_push_room_id:{rid}"
            f"|wss_push_did:7319483754668557238"
            f"|first_req_ms:1721106114541|fetch_time:1721106114633|seq:1"
            f"|wss_info:0-1721106114633-0-0|wrds_v:7392094459690748497"
            f"&host=https://live.douyin.com"
            f"&aid=6383&live_id=1&did_rule=3&endpoint=live_pc&support_wrds=1"
            f"&user_unique_id=7319483754668557238"
            f"&im_path=/webcast/im/fetch/"
            f"&identity=audience"
            f"&need_persist_msg_count=15&insert_task_id=&live_reason="
            f"&room_id={rid}"
            f"&heartbeatDuration=0"
        )
        return wss

    def _on_open(self, ws):
        logger.info("WebSocket 连接成功")
        self._emit("connected", {"room_id": self.room_id, "live_id": self.live_id})
        threading.Thread(target=self._send_heartbeat, daemon=True).start()

    def _on_message(self, ws, message):
        try:
            package = PushFrame().parse(message)
            response = Response().parse(gzip.decompress(package.payload))

            if response.need_ack:
                ack = PushFrame(
                    log_id=package.log_id,
                    payload_type='ack',
                    payload=response.internal_ext.encode('utf-8'),
                ).SerializeToString()
                ws.send(ack, websocket.ABNF.OPCODE_BINARY)

            for msg in response.messages_list:
                self._handle_message(msg)
        except Exception as e:
            logger.debug(f"消息解析出错: {e}")

    def _on_error(self, ws, error):
        logger.error(f"WebSocket 错误: {error}")

    def _on_close(self, ws, close_status_code=None, close_msg=None):
        logger.warning(f"WebSocket 连接关闭: code={close_status_code} msg={close_msg}")

    def _send_heartbeat(self):
        while self._running and self.ws:
            try:
                hb = PushFrame(payload_type='hb').SerializeToString()
                self.ws.send(hb, websocket.ABNF.OPCODE_BINARY)
                logger.debug("发送心跳包")
            except Exception as e:
                logger.debug(f"心跳包发送失败: {e}")
                break
            time.sleep(10)

    def _handle_message(self, msg):
        method = msg.method
        try:
            if method == 'WebcastChatMessage':
                chat = ChatMessage().parse(msg.payload)
                self._emit("chat", {
                    "user": chat.user.nick_name,
                    "user_id": chat.user.id,
                    "content": chat.content,
                    "time": time.time(),
                })
            elif method == 'WebcastGiftMessage':
                gift = GiftMessage().parse(msg.payload)
                self._emit("gift", {
                    "user": gift.user.nick_name,
                    "gift_name": gift.gift.name if gift.gift else "未知礼物",
                    "count": gift.combo_count,
                    "diamond": gift.gift.diamond_count if gift.gift else 0,
                    "time": time.time(),
                })
            elif method == 'WebcastLikeMessage':
                like = LikeMessage().parse(msg.payload)
                self._emit("like", {
                    "user": like.user.nick_name,
                    "user_id": like.user.id,
                    "count": like.count,
                    "total": like.total,
                })
            elif method == 'WebcastMemberMessage':
                member = MemberMessage().parse(msg.payload)
                self._emit("member", {
                    "user": member.user.nick_name,
                    "action": "进入直播间",
                })
            elif method == 'WebcastRoomUserSeqMessage':
                seq = RoomUserSeqMessage().parse(msg.payload)
                self._emit("room_stats", {
                    "online": seq.total_user,
                    "total_pv": seq.total_pv_for_anchor,
                })
            elif method == 'WebcastSocialMessage':
                social = SocialMessage().parse(msg.payload)
                self._emit("follow", {
                    "user": social.user.nick_name,
                })
            elif method == 'WebcastControlMessage':
                ctrl = ControlMessage().parse(msg.payload)
                if ctrl.status == 3:
                    logger.info("直播间已结束")
                    self._emit("live_end", {})
                    self.stop()
        except Exception as e:
            logger.debug(f"处理消息失败 [{method}]: {e}")

    def _connect(self):
        wss_url = self._build_wss_url()
        logger.info("正在生成签名...")
        signature = generate_signature(wss_url)
        if signature:
            wss_url += f"&signature={signature}"
            logger.info("签名生成成功")
        else:
            logger.warning("签名生成失败，尝试无签名连接")

        headers = {
            "Cookie": f"ttwid={self.ttwid}",
            "User-Agent": self.USER_AGENT,
        }

        self.ws = websocket.WebSocketApp(
            wss_url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self.ws.run_forever()

    async def start(self):
        """异步启动（在线程中运行同步 WebSocket）"""
        self._running = True
        logger.info(f"正在连接直播间 {self.live_id} ...")

        _ = self.ttwid
        _ = self.room_id

        retry_count = 0
        max_retry = 10

        while self._running and retry_count < max_retry:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._connect)
            except Exception as e:
                logger.error(f"连接异常: {e}")

            if not self._running:
                break

            retry_count += 1
            wait = min(retry_count * 3, 30)
            logger.info(f"将在 {wait} 秒后重连 (第 {retry_count}/{max_retry} 次)...")
            await asyncio.sleep(wait)

    def stop(self):
        self._running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass


class MockDanmakuClient:
    """模拟弹幕客户端，用于测试完整流程"""

    MOCK_MESSAGES = [
        {"user": "小明", "content": "主播在卖什么呀？"},
        {"user": "花花", "content": "这个多少钱？"},
        {"user": "大壮", "content": "有没有优惠？"},
        {"user": "莉莉", "content": "质量怎么样？"},
        {"user": "阿杰", "content": "能发顺丰吗？"},
        {"user": "小红", "content": "主播好漂亮"},
        {"user": "老王", "content": "这个颜色还有别的吗？"},
        {"user": "甜甜", "content": "可以退货吗？"},
        {"user": "强哥", "content": "买两件能便宜点吗？"},
        {"user": "小芳", "content": "什么时候发货？"},
        {"user": "浩子", "content": "主播从哪里发货？"},
        {"user": "美美", "content": "有没有大码的？"},
    ]

    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False

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
        logger.info("模拟弹幕客户端已启动")
        self._emit("connected", {"room_id": "mock_room"})

        while self._running:
            msg = random.choice(self.MOCK_MESSAGES)
            self._emit("chat", {
                "user": msg["user"],
                "user_id": random.randint(10000, 99999),
                "content": msg["content"],
                "time": time.time(),
            })
            await asyncio.sleep(self.interval + random.uniform(-1, 2))

    def stop(self):
        self._running = False
