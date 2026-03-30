import logging
import os
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)


class AudioPlayer:
    """音频播放器，使用 macOS 原生 afplay 或 pygame 播放 mp3。

    pygame 模式下使用 Sound channel（而非 music）播放，
    以便 BGM 可以同时通过 pygame.mixer.music 循环播放。
    支持 volume（0.0–1.0）；afplay 多数版本无独立音量参数，仅 pygame 下有效。
    支持 stop() 打断当前口播/人声，供 AI 回复抢占播放。
    """

    def __init__(self, use_afplay: bool = True):
        self.use_afplay = use_afplay and sys.platform == "darwin"
        self._pygame = None
        self._lock = threading.Lock()
        self._afplay_proc: subprocess.Popen | None = None
        self._pygame_voice_ch = None
        if not self.use_afplay:
            self._init_pygame()

    def _init_pygame(self):
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._pygame = pygame
            logger.info("使用 pygame Sound channel 播放音频")
        except ImportError:
            logger.error("pygame 未安装，请运行: pip install pygame")
            self._pygame = None

    def stop(self):
        """立即打断当前人声播放（afplay / pygame Sound），不影响 BGM music。"""
        with self._lock:
            if self._afplay_proc is not None and self._afplay_proc.poll() is None:
                try:
                    self._afplay_proc.terminate()
                except Exception as e:
                    logger.debug("终止 afplay 时: %s", e)
            ch = self._pygame_voice_ch
            self._pygame_voice_ch = None
        if ch is not None:
            try:
                ch.stop()
            except Exception as e:
                logger.debug("停止 pygame channel 时: %s", e)

    def play(self, audio_path: str, volume: float | None = None):
        if not audio_path or not os.path.exists(audio_path):
            logger.warning(f"音频文件不存在: {audio_path}")
            return

        vol = 1.0 if volume is None else max(0.0, min(1.0, float(volume)))

        if self.use_afplay:
            self._play_afplay(audio_path, vol)
        elif self._pygame:
            self._play_pygame(audio_path, vol)
        else:
            logger.error("没有可用的音频播放器")

    def _play_afplay(self, audio_path: str, volume: float):
        """macOS 原生播放，阻塞直到播放完成或被 stop() 终止。"""
        try:
            cmd: list[str]
            if volume < 0.999:
                cmd = ["afplay", "-v", str(volume), audio_path]
                with self._lock:
                    if self._afplay_proc is not None and self._afplay_proc.poll() is None:
                        self._afplay_proc.terminate()
                    p = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._afplay_proc = p
                rc = p.wait()
                with self._lock:
                    if self._afplay_proc is p:
                        self._afplay_proc = None
                if rc == 0:
                    return
                logger.debug("afplay -v 不可用或失败，回退无音量参数播放")

            cmd = ["afplay", audio_path]
            with self._lock:
                if self._afplay_proc is not None and self._afplay_proc.poll() is None:
                    self._afplay_proc.terminate()
                p = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._afplay_proc = p
            p.wait()
            with self._lock:
                if self._afplay_proc is p:
                    self._afplay_proc = None
        except subprocess.CalledProcessError as e:
            logger.error(f"afplay 播放失败: {e}")
        except FileNotFoundError:
            logger.error("afplay 命令不可用，切换到 pygame")
            self.use_afplay = False
            self._init_pygame()
            self._play_pygame(audio_path, volume)

    def _play_pygame(self, audio_path: str, volume: float):
        """使用 pygame.mixer.Sound 播放，不占用 music 通道（留给 BGM）。"""
        try:
            import time

            sound = self._pygame.mixer.Sound(audio_path)
            sound.set_volume(volume)
            channel = sound.play()
            if channel:
                with self._lock:
                    self._pygame_voice_ch = channel
                try:
                    while channel.get_busy():
                        time.sleep(0.1)
                finally:
                    with self._lock:
                        if self._pygame_voice_ch is channel:
                            self._pygame_voice_ch = None
        except Exception as e:
            logger.error(f"pygame 播放失败: {e}")
