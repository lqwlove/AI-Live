import asyncio
import hashlib
import logging
import os

import edge_tts

logger = logging.getLogger(__name__)


class TTSSpeaker:
    """使用 edge-tts 将文本转为语音文件"""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%",
                 volume: str = "+0%", output_dir: str = "audio_cache"):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _get_cache_path(self, text: str) -> str:
        text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
        return os.path.join(self.output_dir, f"{text_hash}.mp3")

    async def synthesize(self, text: str) -> str:
        """将文本合成为 mp3 文件，返回文件路径。相同文本使用缓存。"""
        if not text.strip():
            return ""

        cache_path = self._get_cache_path(text)
        if os.path.exists(cache_path):
            logger.debug(f"使用 TTS 缓存: {cache_path}")
            return cache_path

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
            )
            await communicate.save(cache_path)
            logger.info(f"TTS 合成完成: {cache_path}")
            return cache_path
        except Exception as e:
            logger.error(f"TTS 合成失败: {e}")
            return ""

    def synthesize_sync(self, text: str) -> str:
        """同步版本的语音合成"""
        return asyncio.run(self.synthesize(text))
