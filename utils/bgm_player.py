"""
Background music player using pygame.mixer.music.

Uses pygame.mixer.music for streaming loop playback. Supports volume ducking
during TTS so the AI voice stays clear over background music.
"""

import glob
import logging
import os
import threading

logger = logging.getLogger(__name__)


class BgmPlayer:
    def __init__(
        self,
        bgm_dir: str = "bgm",
        volume: float = 0.3,
        duck_volume: float = 0.05,
    ):
        self.bgm_dir = bgm_dir
        self.volume = max(0.0, min(1.0, volume))
        self.duck_volume = max(0.0, min(1.0, duck_volume))
        self._playing = False
        self._current_file: str | None = None
        self._lock = threading.Lock()
        self._pygame_ready = False
        self._init_pygame()

    def _init_pygame(self):
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._pygame = pygame
            self._pygame_ready = True
            logger.info("[BGM] pygame.mixer 初始化成功")
        except Exception as e:
            logger.warning(f"[BGM] pygame.mixer 初始化失败: {e}")
            self._pygame = None
            self._pygame_ready = False

    def list_files(self) -> list[str]:
        if not os.path.isdir(self.bgm_dir):
            return []
        patterns = ("*.mp3", "*.wav", "*.ogg", "*.flac")
        files = []
        for pat in patterns:
            files.extend(glob.glob(os.path.join(self.bgm_dir, pat)))
        files.sort()
        return files

    def play(self, file_path: str | None = None):
        if not self._pygame_ready:
            logger.warning("[BGM] pygame 不可用，无法播放背景音乐")
            return

        with self._lock:
            if file_path is None:
                files = self.list_files()
                if not files:
                    logger.info("[BGM] bgm 目录为空，跳过背景音乐")
                    return
                file_path = files[0]

            if not os.path.isfile(file_path):
                logger.warning(f"[BGM] 文件不存在: {file_path}")
                return

            try:
                self._pygame.mixer.music.load(file_path)
                self._pygame.mixer.music.set_volume(self.volume)
                self._pygame.mixer.music.play(loops=-1)
                self._playing = True
                self._current_file = file_path
                logger.info(
                    f"[BGM] 开始播放: {os.path.basename(file_path)} (音量: {self.volume})"
                )
            except Exception as e:
                logger.error(f"[BGM] 播放失败: {e}")

    def stop(self):
        if not self._pygame_ready:
            return
        with self._lock:
            if self._playing:
                try:
                    self._pygame.mixer.music.stop()
                    self._pygame.mixer.music.unload()
                except Exception:
                    pass
                self._playing = False
                self._current_file = None
                logger.info("[BGM] 已停止")

    def duck(self):
        if not self._pygame_ready or not self._playing:
            return
        try:
            self._pygame.mixer.music.set_volume(self.duck_volume)
        except Exception:
            pass

    def unduck(self):
        if not self._pygame_ready or not self._playing:
            return
        try:
            self._pygame.mixer.music.set_volume(self.volume)
        except Exception:
            pass

    def set_volume(self, volume: float):
        self.volume = max(0.0, min(1.0, volume))
        if self._pygame_ready and self._playing:
            try:
                self._pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def current_file(self) -> str | None:
        return self._current_file

    def get_status(self) -> dict:
        return {
            "playing": self._playing,
            "file": os.path.basename(self._current_file) if self._current_file else None,
            "volume": self.volume,
            "duck_volume": self.duck_volume,
        }
