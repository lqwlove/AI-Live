"""
SessionManager — manages the LiveEngine lifecycle.

Provides a single entry point for starting/stopping sessions and
querying the current status. Used by the API layer.
"""

import logging

from config import Config
from core.engine import ConfigError, LiveEngine
from core.events import EventBus

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, config, event_bus: EventBus, announcement_store=None):
        self.config = config
        self.event_bus = event_bus
        self.announcement_store = announcement_store
        self.engine = LiveEngine(config, event_bus, announcement_store)

    async def start(self, platform: str, **kwargs) -> dict:
        """Start a live session. Returns status dict or raises."""
        if self.engine.running:
            raise RuntimeError("会话已在运行中，请先停止当前会话")
        await self.engine.start(platform, **kwargs)
        return self.engine.get_status()

    async def stop(self) -> dict:
        await self.engine.stop()
        self.engine = LiveEngine(
            self.config, self.event_bus, self.announcement_store
        )
        return {"running": False}

    def get_status(self) -> dict:
        return self.engine.get_status()

    def reload_config(self, config: Config):
        """Hot-reload configuration (only takes effect on next start)."""
        self.config = config
        if not self.engine.running:
            self.engine = LiveEngine(config, self.event_bus, self.announcement_store)
