"""
火山引擎语音合成（豆包语音 V3 HTTP Chunked）
- 支持声音复刻音色（需提前在控制台训练）
- 支持多语言合成（中文/英文）
- 流式接收音频数据，拼接后写入文件
"""

import asyncio
import base64
import hashlib
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

API_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

LANG_MAP = {
    "zh": "zh-cn",
    "en": "en",
}


class VolcengineSpeaker:
    """火山引擎 TTS，支持声音复刻 + 中英双语。兼容新版/旧版控制台认证。"""

    def __init__(
        self,
        app_id: str = "",
        access_token: str = "",
        api_key: str = "",
        speaker_id: str = "",
        resource_id: str = "seed-icl-2.0",
        audio_format: str = "mp3",
        sample_rate: int = 24000,
        output_dir: str = "audio_cache",
    ):
        self.speaker_id = speaker_id
        self.resource_id = resource_id
        self.audio_format = audio_format
        self.sample_rate = sample_rate
        self.output_dir = output_dir
        self._session = requests.Session()
        os.makedirs(output_dir, exist_ok=True)

        if api_key:
            self._headers = {
                "X-Api-App-Key": api_key,
                "X-Api-Access-Key": api_key,
                "X-Api-Resource-Id": resource_id,
                "Content-Type": "application/json",
            }
            logger.info("火山 TTS 使用新版控制台 API Key 认证")
        elif app_id and access_token:
            self._headers = {
                "X-Api-App-Id": app_id,
                "X-Api-Access-Key": access_token,
                "X-Api-Resource-Id": resource_id,
                "Content-Type": "application/json",
            }
            logger.info("火山 TTS 使用旧版控制台 App ID + Access Token 认证")
        else:
            raise ValueError("请提供 volcengine.api_key（新版控制台）或 app_id + access_token（旧版控制台）")

    def _get_cache_path(self, text: str, lang: str) -> str:
        key = f"{self.speaker_id}:{lang}:{text}"
        text_hash = hashlib.md5(key.encode()).hexdigest()[:12]
        return os.path.join(self.output_dir, f"{text_hash}.{self.audio_format}")

    def _synthesize_sync(self, text: str, lang: str = "zh") -> str:
        """同步调用火山引擎 TTS API，返回音频文件路径"""
        if not text.strip():
            return ""

        cache_path = self._get_cache_path(text, lang)
        if os.path.exists(cache_path):
            logger.debug(f"使用 TTS 缓存: {cache_path}")
            return cache_path

        explicit_lang = LANG_MAP.get(lang, "zh-cn")

        payload = {
            "user": {"uid": "live-assistant"},
            "req_params": {
                "text": text,
                "speaker": self.speaker_id,
                "audio_params": {
                    "format": self.audio_format,
                    "sample_rate": self.sample_rate,
                },
                "additions": json.dumps({
                    "explicit_language": explicit_lang,
                }),
            },
        }

        try:
            resp = self._session.post(
                API_URL, headers=self._headers, json=payload, stream=True, timeout=30
            )

            if resp.status_code != 200:
                body = resp.text[:500]
                logger.error(
                    f"火山 TTS HTTP {resp.status_code}: {body}\n"
                    f"  resource_id={self.resource_id}, speaker={self.speaker_id}"
                )
                return ""

            audio_chunks: list[bytes] = []
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                code = data.get("code", -1)
                if code == 0 and data.get("data"):
                    audio_chunks.append(base64.b64decode(data["data"]))
                elif code == 20000000:
                    break
                elif code not in (0, 20000000):
                    msg = data.get("message", "")
                    if msg:
                        logger.error(f"火山 TTS 业务错误: code={code}, msg={msg}")
                        return ""

            if not audio_chunks:
                logger.error("火山 TTS 未返回音频数据")
                return ""

            with open(cache_path, "wb") as f:
                for chunk in audio_chunks:
                    f.write(chunk)

            logger.info(f"TTS 合成完成 [{lang}]: {cache_path}")
            return cache_path

        except Exception as e:
            logger.error(f"火山 TTS 合成失败: {e}")
            return ""

    async def synthesize(self, text: str, lang: str = "zh") -> str:
        """异步合成语音（在线程池中执行同步 HTTP 请求）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text, lang)
