import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


class AudioPlayer:
    """音频播放器，使用 macOS 原生 afplay 或 pygame 播放 mp3"""

    def __init__(self, use_afplay: bool = True):
        self.use_afplay = use_afplay and sys.platform == "darwin"
        if not self.use_afplay:
            self._init_pygame()

    def _init_pygame(self):
        try:
            import pygame
            pygame.mixer.init()
            self._pygame = pygame
            logger.info("使用 pygame 播放音频")
        except ImportError:
            logger.error("pygame 未安装，请运行: pip install pygame")
            self._pygame = None

    def play(self, audio_path: str):
        if not audio_path or not os.path.exists(audio_path):
            logger.warning(f"音频文件不存在: {audio_path}")
            return

        if self.use_afplay:
            self._play_afplay(audio_path)
        elif self._pygame:
            self._play_pygame(audio_path)
        else:
            logger.error("没有可用的音频播放器")

    def _play_afplay(self, audio_path: str):
        """macOS 原生播放，阻塞直到播放完成"""
        try:
            subprocess.run(["afplay", audio_path], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"afplay 播放失败: {e}")
        except FileNotFoundError:
            logger.error("afplay 命令不可用，切换到 pygame")
            self.use_afplay = False
            self._init_pygame()
            self._play_pygame(audio_path)

    def _play_pygame(self, audio_path: str):
        """使用 pygame 播放，阻塞直到播放完成"""
        try:
            import time
            self._pygame.mixer.music.load(audio_path)
            self._pygame.mixer.music.play()
            while self._pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"pygame 播放失败: {e}")
