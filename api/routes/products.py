from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/products")


@router.get("")
async def list_products(request: Request):
    store = request.app.state.product_store
    return store.get_all()


class ProductBody(BaseModel):
    name: str
    price: float
    keywords: list[str]
    description: str = ""
    original_price: float | None = None
    selling_points: list[str] = []
    active: bool = True


@router.post("")
async def add_product(body: ProductBody, request: Request):
    store = request.app.state.product_store
    return store.add(body.model_dump())


@router.put("/{product_id}")
async def update_product(product_id: str, request: Request):
    store = request.app.state.product_store
    data = await request.json()
    result = store.update(product_id, data)
    if result is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return result


@router.delete("/{product_id}")
async def delete_product(product_id: str, request: Request):
    store = request.app.state.product_store
    if not store.delete(product_id):
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"ok": True}


class TestMatchBody(BaseModel):
    text: str


@router.post("/test-match")
async def test_match(body: TestMatchBody, request: Request):
    store = request.app.state.product_store
    from knowledge.product_store import Product
    from dataclasses import asdict

    matched = store.search(body.text)
    return {"matched": [asdict(p) for p in matched], "count": len(matched)}
