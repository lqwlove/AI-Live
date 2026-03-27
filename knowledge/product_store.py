import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class Product:
    id: str
    name: str
    price: float
    keywords: list[str]
    description: str = ""
    original_price: float | None = None
    selling_points: list[str] = field(default_factory=list)
    active: bool = True


class ProductStore:
    """JSON-backed product knowledge base with keyword search."""

    def __init__(self, file_path: str = "products.json", max_match: int = 3):
        self.file_path = file_path
        self.max_match = max_match
        self._products: list[Product] = []
        self.load()

    def load(self):
        abs_path = os.path.abspath(self.file_path)
        if not os.path.exists(self.file_path):
            logger.info(f"[ProductStore] 商品文件不存在: {abs_path}")
            self._products = []
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._products = [Product(**item) for item in data]
            names = [p.name for p in self._products]
            logger.info(
                f"[ProductStore] 从 {abs_path} 加载了 {len(self._products)} 个商品: {names}"
            )
        except Exception as e:
            logger.error(f"[ProductStore] 加载商品数据失败({abs_path}): {e}")
            self._products = []

    def save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(p) for p in self._products], f, ensure_ascii=False, indent=2
                )
        except Exception as e:
            logger.error(f"保存商品数据失败: {e}")

    def search(self, query: str) -> list[Product]:
        """Return active products whose keywords appear in *query*."""
        matched: list[Product] = []
        query_lower = query.lower()
        for p in self._products:
            if not p.active:
                logger.debug(f"[Search] 跳过下架商品: {p.name}")
                continue
            hits = [kw for kw in p.keywords if kw.lower() in query_lower]
            if hits:
                logger.info(
                    f'[Search] 商品「{p.name}」命中关键词 {hits}，query="{query}"'
                )
                matched.append(p)
                if len(matched) >= self.max_match:
                    break
        if not matched:
            all_kws = [kw for p in self._products if p.active for kw in p.keywords]
            logger.info(f'[Search] 无匹配，query="{query}"，所有关键词={all_kws}')
        return matched

    def format_for_prompt(self, products: list[Product]) -> str:
        lines = ["【当前直播间商品信息】"]
        for i, p in enumerate(products, 1):
            price_str = f"直播价 ¥{p.price}"
            if p.original_price:
                price_str += f"（原价 ¥{p.original_price}）"
            lines.append(f"{i}. {p.name} | {price_str}")
            if p.description:
                lines.append(f"   简介：{p.description}")
            if p.selling_points:
                lines.append(f"   卖点：{'、'.join(p.selling_points)}")
        return "\n".join(lines)

    def get_all(self) -> list[dict]:
        return [asdict(p) for p in self._products]

    def get_by_id(self, product_id: str) -> Product | None:
        for p in self._products:
            if p.id == product_id:
                return p
        return None

    def add(self, data: dict) -> dict:
        data.setdefault("id", uuid.uuid4().hex[:8])
        product = Product(**data)
        self._products.append(product)
        self.save()
        return asdict(product)

    def update(self, product_id: str, data: dict) -> dict | None:
        for i, p in enumerate(self._products):
            if p.id == product_id:
                merged = {**asdict(p), **data, "id": product_id}
                self._products[i] = Product(**merged)
                self.save()
                return asdict(self._products[i])
        return None

    def delete(self, product_id: str) -> bool:
        for i, p in enumerate(self._products):
            if p.id == product_id:
                self._products.pop(i)
                self.save()
                return True
        return False
