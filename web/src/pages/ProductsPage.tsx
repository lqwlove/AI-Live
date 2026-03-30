import { useEffect, useState } from "react";
import { Package, Plus, Pencil, Trash2, Search, X } from "lucide-react";
import { api, type Product } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [editing, setEditing] = useState<Partial<Product> | null>(null);
  const [testText, setTestText] = useState("");
  const [matchResult, setMatchResult] = useState<Product[] | null>(null);

  const reload = () => api.getProducts().then(setProducts).catch(console.error);

  useEffect(() => { reload(); }, []);

  const handleSave = async () => {
    if (!editing) return;
    try {
      if (editing.id) {
        await api.updateProduct(editing.id, editing);
      } else {
        await api.addProduct(editing as Omit<Product, "id">);
      }
      setEditing(null);
      reload();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteProduct(id).catch(console.error);
    reload();
  };

  const handleToggle = async (p: Product) => {
    await api.updateProduct(p.id, { active: !p.active }).catch(console.error);
    reload();
  };

  const handleTest = async () => {
    if (!testText.trim()) return;
    const res = await api.testMatch(testText).catch(() => null);
    if (res) setMatchResult(res.matched);
  };

  const newProduct = (): Partial<Product> => ({
    name: "", price: 0, keywords: [], description: "",
    original_price: null, selling_points: [], active: true,
  });

  return (
    <div className="tk-main-canvas">
      <header
        className="flex shrink-0 items-center"
        style={{ minHeight: "var(--ds-settings-header-h)", height: "var(--ds-settings-header-h)" }}
      >
        <h1 className="text-2xl leading-none font-bold tracking-tight text-[var(--font-primary)]">商品库</h1>
        <span className="min-w-0 flex-1" aria-hidden />
        <Button
          type="button"
          variant="outline"
          onClick={() => setEditing(newProduct())}
          className="box-border h-8 gap-1.5 rounded-md border-[var(--border-app)] bg-[var(--bg-card)] px-4 py-0 text-[13px] font-medium text-[var(--font-secondary)] hover:bg-[var(--bg-card-hover)]"
        >
          <Plus className="size-3.5" />
          添加商品
        </Button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-3" style={{ gap: "var(--ds-stack-gap)" }}>
        {/* Product list */}
        <div className="col-span-2 flex flex-col overflow-auto" style={{ gap: "var(--ds-stack-gap)" }}>
          {products.length === 0 && (
            <div className="flex flex-1 items-center justify-center text-[var(--font-muted)]">
              <div className="text-center">
                <Package className="mx-auto mb-3 size-10 opacity-40" />
                <p className="text-sm">暂无商品</p>
                <p className="mt-1 text-xs text-[var(--font-muted)]">添加商品后，AI 可根据关键词推荐讲解</p>
              </div>
            </div>
          )}
          {products.map((p) => (
            <div
              key={p.id}
              className="flex items-start gap-4 rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)] px-5 py-4"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-[var(--font-primary)]">{p.name}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${p.active ? "bg-[var(--success)]/15 text-[var(--success)]" : "bg-[var(--font-muted)]/15 text-[var(--font-muted)]"}`}>
                    {p.active ? "在售" : "下架"}
                  </span>
                </div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-lg font-bold text-[var(--accent-purple)]">¥{p.price}</span>
                  {p.original_price && (
                    <span className="text-xs text-[var(--font-muted)] line-through">¥{p.original_price}</span>
                  )}
                </div>
                {p.description && <p className="mt-1.5 text-xs text-[var(--font-secondary)]">{p.description}</p>}
                <div className="mt-2 flex flex-wrap gap-1">
                  {p.keywords.map((kw) => (
                    <span key={kw} className="rounded-md bg-[var(--accent-purple)]/10 px-2 py-0.5 text-[11px] text-[var(--accent-purple)]">{kw}</span>
                  ))}
                </div>
                {p.selling_points.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {p.selling_points.map((sp) => (
                      <span key={sp} className="rounded-md border border-[var(--border-app)] px-2 py-0.5 text-[11px] text-[var(--font-secondary)]">{sp}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button type="button" onClick={() => handleToggle(p)} className="rounded-md p-1.5 text-[var(--font-muted)] hover:bg-[var(--bg-card-hover)]" title={p.active ? "下架" : "上架"}>
                  <Package className="size-3.5" />
                </button>
                <button type="button" onClick={() => setEditing({ ...p })} className="rounded-md p-1.5 text-[var(--font-muted)] hover:bg-[var(--bg-card-hover)]">
                  <Pencil className="size-3.5" />
                </button>
                <button type="button" onClick={() => handleDelete(p.id)} className="rounded-md p-1.5 text-[var(--error)] hover:bg-[var(--error)]/10">
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Right panel: edit form or test match */}
        <div className="flex flex-col" style={{ gap: "var(--ds-stack-gap)" }}>
          {/* Test match */}
          <div className="rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)] px-5 pt-4 pb-5">
            <div className="flex items-center gap-2 mb-3">
              <Search size={16} className="text-[var(--accent-purple)]" />
              <span className="text-sm font-semibold text-[var(--font-primary)]">匹配测试</span>
            </div>
            <div className="flex gap-2">
              <input
                className="min-w-0 flex-1 rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
                placeholder="输入模拟弹幕内容…"
                value={testText}
                onChange={(e) => setTestText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleTest()}
              />
              <Button type="button" variant="outline" onClick={handleTest} className="h-auto shrink-0 rounded-md border-[var(--border-app)] bg-[var(--bg-card)] px-3 text-[13px]">
                测试
              </Button>
            </div>
            {matchResult !== null && (
              <div className="mt-3">
                {matchResult.length === 0 ? (
                  <p className="text-xs text-[var(--font-muted)]">未匹配到商品</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {matchResult.map((p) => (
                      <div key={p.id} className="rounded-md border border-[var(--accent-purple)]/20 bg-[var(--accent-purple)]/5 px-3 py-2">
                        <span className="text-[13px] font-medium text-[var(--font-primary)]">{p.name}</span>
                        <span className="ml-2 text-xs text-[var(--accent-purple)]">¥{p.price}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Edit form */}
          {editing && (
            <div className="rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)] px-5 pt-4 pb-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-[var(--font-primary)]">
                  {editing.id ? "编辑商品" : "新建商品"}
                </span>
                <button type="button" onClick={() => setEditing(null)} className="rounded-md p-1 text-[var(--font-muted)] hover:bg-[var(--bg-card-hover)]">
                  <X className="size-4" />
                </button>
              </div>
              <div className="flex flex-col gap-3">
                <FormField label="名称" value={editing.name ?? ""} onChange={(v) => setEditing({ ...editing, name: v })} />
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="价格" value={String(editing.price ?? 0)} onChange={(v) => setEditing({ ...editing, price: Number(v) || 0 })} />
                  <FormField label="原价（可选）" value={String(editing.original_price ?? "")} onChange={(v) => setEditing({ ...editing, original_price: v ? Number(v) : null })} />
                </div>
                <FormField label="描述" value={editing.description ?? ""} onChange={(v) => setEditing({ ...editing, description: v })} />
                <FormField
                  label="关键词（英文逗号分隔）"
                  value={(editing.keywords ?? []).join(", ")}
                  onChange={(v) => setEditing({ ...editing, keywords: v.split(",").map((s) => s.trim()).filter(Boolean) })}
                />
                <FormField
                  label="卖点（英文逗号分隔）"
                  value={(editing.selling_points ?? []).join(", ")}
                  onChange={(v) => setEditing({ ...editing, selling_points: v.split(",").map((s) => s.trim()).filter(Boolean) })}
                />
                <Button
                  type="button"
                  onClick={handleSave}
                  className="h-9 w-full rounded-md border-0 bg-gradient-to-b from-[var(--accent-purple)] to-[var(--accent-blue)] text-[13px] font-semibold text-white hover:opacity-90"
                >
                  保存
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FormField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-[var(--font-secondary)]">{label}</label>
      <input
        className="rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
