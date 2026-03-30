"""JSON-backed announcement script library for live auto-broadcast."""

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AnnouncementItem:
    id: str
    title: str
    text: str
    enabled: bool = True


class AnnouncementStore:
    def __init__(self, file_path: str = "announcements.json"):
        self.file_path = file_path
        self._items: list[AnnouncementItem] = []
        self.load()

    def load(self):
        if not os.path.exists(self.file_path):
            logger.info(f"[Announce] 文件不存在，使用空库: {self.file_path}")
            self._items = []
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._items = [AnnouncementItem(**item) for item in data]
            logger.info(
                f"[Announce] 从 {self.file_path} 加载 {len(self._items)} 条播报文案"
            )
        except Exception as e:
            logger.error(f"[Announce] 加载失败: {e}")
            self._items = []

    def save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(x) for x in self._items],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"[Announce] 保存失败: {e}")

    def get_all(self) -> list[dict]:
        return [asdict(x) for x in self._items]

    def replace_all(self, items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[AnnouncementItem] = []
        for raw in items:
            iid = str(raw.get("id") or "").strip() or str(uuid.uuid4())
            if iid in seen:
                iid = str(uuid.uuid4())
            seen.add(iid)
            out.append(
                AnnouncementItem(
                    id=iid,
                    title=str(raw.get("title", "")),
                    text=str(raw.get("text", "")),
                    enabled=bool(raw.get("enabled", True)),
                )
            )
        self._items = out
        self.save()
        return self.get_all()

    def get_by_id(self, iid: str) -> AnnouncementItem | None:
        for x in self._items:
            if x.id == iid:
                return x
        return None

    def validate_active_ids(self, ids: list[str]) -> tuple[bool, str]:
        for iid in ids:
            item = self.get_by_id(iid)
            if item is None:
                return False, f"未知条目: {iid}"
            if not item.enabled:
                return False, f"条目已禁用: {iid}"
        return True, ""
