import os

import yaml

from utils.paths import get_data_path

DEFAULT_CONFIG = {
    "douyin": {
        "live_url": "",
        "room_id": "",
        "cookie": "",
    },
    "tiktok": {
        "unique_id": "",
        "proxy": "",
    },
    "youtube": {
        "video_id": "",
        "channel_id": "",
        "api_key": "",
        "client_secrets_file": "",
        "auto_reply": False,
        "reply_prefix": "",
        "chat_warmup_seconds": 2.0,
    },
    "ai": {
        "model": "gpt-4o-mini",
        "engine": "agent",
        "system_prompt": (
            "你是一个直播间的AI卖货助手。"
            "你会收到最近一批观众评论，请：\n"
            "1. 从中挑选最有价值、最需要回答的问题（忽略无意义的刷屏）\n"
            "2. 用简短、友好、有趣的方式统一回答\n"
            "3. 回答控制在100字以内，适合语音播报\n"
            "4. 可以点名回复重要问题的观众\n"
            "5. 如果需要查询商品信息，使用 product_search 工具\n"
            "6. 不要使用markdown格式、表情符号或特殊符号"
        ),
        "max_history": 10,
        "multilang": False,
        "batch_interval": 5,
        "translate_display": True,
        "free_reply": False,
    },
    "knowledge": {
        "enabled": True,
        "products_file": "products.json",
        "max_match_products": 3,
    },
    "tts": {
        "engine": "edge-tts",
        "voice": "zh-CN-XiaoxiaoNeural",
        "rate": "+0%",
        "volume": "+0%",
        "output_dir": "audio_cache",
    },
    "filter": {
        "keywords": [
            "怎么",
            "什么",
            "吗",
            "如何",
            "为什么",
            "多少",
            "哪",
            "谁",
            "?",
            "？",
            "how",
            "what",
            "why",
            "when",
            "where",
            "who",
            "?",
        ],
        "min_length": 2,
        "max_length": 200,
        "cooldown_seconds": 3,
    },
    "audio": {
        "device": "default",
        "voice_volume": 1.0,
    },
    "announce": {
        "items_file": "announcements.json",
        "interval_seconds": 30.0,
        "pause_on_any_chat": False,
        "lang": "zh",
    },
    "bgm": {
        "enabled": False,
        "dir": "bgm",
        "file": "",
        "volume": 0.3,
        "duck_volume": 0.05,
    },
}


import copy
import re

_SENSITIVE_KEYS = re.compile(r"(api_key|access_token|cookie|secret)", re.I)


class Config:
    def __init__(self, config_path: str | None = None):
        if config_path is None:
            config_path = get_data_path("config.yaml")
        self._path = config_path
        self._data = copy.deepcopy(DEFAULT_CONFIG)
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            self._deep_merge(self._data, user_config)
        self._apply_internal_credentials()

    def _apply_internal_credentials(self):
        """AI 密钥 / Base URL 与火山引擎配置仅从 internal_credentials 注入，不由 yaml 或 Web 覆盖。"""
        from internal_credentials import (
            get_ai_api_key,
            get_ai_base_url,
            get_volcengine_config,
        )

        ai = self._data.setdefault("ai", {})
        ai["api_key"] = get_ai_api_key()
        ai["base_url"] = get_ai_base_url()
        self._data["volcengine"] = get_volcengine_config()

    def _deep_merge(self, base, override, *, skip_masked_secrets: bool = False):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(
                    base[key], value, skip_masked_secrets=skip_masked_secrets
                )
            elif (
                skip_masked_secrets
                and isinstance(value, str)
                and _SENSITIVE_KEYS.search(key)
                and self._is_masked_secret_placeholder(value)
            ):
                # 前端 GET 返回脱敏串，保存时勿覆盖真实密钥
                continue
            else:
                base[key] = value

    @staticmethod
    def _is_masked_secret_placeholder(value: str) -> bool:
        """与 get_sanitized 规则一致：前 4 字符 + 其余全为 *。"""
        if len(value) <= 4:
            return False
        suffix = value[4:]
        return bool(suffix) and all(c == "*" for c in suffix)

    def get(self, *keys):
        result = self._data
        for key in keys:
            result = result[key]
        return result

    def get_all(self) -> dict:
        return copy.deepcopy(self._data)

    def get_sanitized(self) -> dict:
        """Return config for Web UI：脱敏，且不包含仅服务端持有的 AI 密钥与火山配置。"""
        d = self._mask(copy.deepcopy(self._data))
        d.pop("volcengine", None)
        ai = d.get("ai")
        if isinstance(ai, dict):
            ai.pop("api_key", None)
            ai.pop("base_url", None)
        return d

    def _mask(self, obj, _key=""):
        if isinstance(obj, dict):
            return {k: self._mask(v, k) for k, v in obj.items()}
        if isinstance(obj, str) and _SENSITIVE_KEYS.search(_key) and len(obj) > 4:
            return obj[:4] + "*" * (len(obj) - 4)
        return obj

    def update(self, data: dict):
        """Merge *data* into current config and persist to disk."""
        payload = copy.deepcopy(data)
        payload.pop("volcengine", None)
        if "ai" in payload and isinstance(payload["ai"], dict):
            payload["ai"] = {
                k: v for k, v in payload["ai"].items() if k not in ("api_key", "base_url")
            }
        self._deep_merge(self._data, payload, skip_masked_secrets=True)
        self._apply_internal_credentials()
        self.save(self._path)

    def _persistable_config_copy(self) -> dict:
        """写入 yaml 时去掉仅存在于内存、由 internal_credentials 提供的字段。"""
        to_write = copy.deepcopy(self._data)
        if "ai" in to_write and isinstance(to_write["ai"], dict):
            to_write["ai"] = {
                k: v for k, v in to_write["ai"].items() if k not in ("api_key", "base_url")
            }
        to_write.pop("volcengine", None)
        return to_write

    def save(self, path: str | None = None):
        path = path or self._path
        to_write = self._persistable_config_copy()
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(to_write, f, allow_unicode=True, default_flow_style=False)

    def save_template(self, path="config.yaml"):
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._persistable_config_copy(), f, allow_unicode=True, default_flow_style=False)
        print(f"配置模板已保存到 {path}")

    def validate_platform(self, platform: str) -> dict:
        """Check if a platform has the minimum required configuration."""
        if platform == "youtube":
            yt = self.get("youtube")
            has_id = bool(yt.get("video_id") or yt.get("channel_id"))
            has_auth = bool(yt.get("api_key") or yt.get("client_secrets_file"))
            return {"configured": has_id and has_auth, "platform": platform}
        if platform == "tiktok":
            return {
                "configured": bool(self.get("tiktok", "unique_id")),
                "platform": platform,
            }
        if platform == "douyin":
            dy = self.get("douyin")
            return {
                "configured": bool(dy.get("room_id") or dy.get("live_url")),
                "platform": platform,
            }
        return {"configured": False, "platform": platform}
