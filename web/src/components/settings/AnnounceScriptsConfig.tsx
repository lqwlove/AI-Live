import { useEffect, useState } from "react";
import { Megaphone, Plus, Trash2, Save } from "lucide-react";
import { api, type AnnounceItem } from "@/lib/api";
import { Button } from "@/components/ui/button";

function newItem(): AnnounceItem {
  return {
    id: crypto.randomUUID(),
    title: "",
    text: "",
    enabled: true,
  };
}

export function AnnounceScriptsConfig() {
  const [items, setItems] = useState<AnnounceItem[]>([]);
  const [saving, setSaving] = useState(false);

  const load = () => api.getAnnounceItems().then(setItems).catch(console.error);

  useEffect(() => {
    load();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.putAnnounceItems(items);
      await load();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="flex flex-col rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)] p-5"
      style={{ gap: "var(--ds-stack-gap)" }}
    >
      <div className="flex items-center gap-2">
        <Megaphone className="size-5 text-[var(--accent-purple)]" />
        <h2 className="text-lg font-semibold text-[var(--font-primary)]">播报文案库</h2>
        <span className="min-w-0 flex-1" />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setItems((prev) => [...prev, newItem()])}
          className="h-8 border-[var(--border-app)]"
        >
          <Plus className="size-3.5" />
          添加
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={saving}
          onClick={() => void save()}
          className="h-8 bg-[var(--accent-purple)] text-white hover:opacity-90"
        >
          <Save className="size-3.5" />
          {saving ? "保存中…" : "保存"}
        </Button>
      </div>
      <p className="text-xs text-[var(--font-muted)]">
        在控制台开播后勾选要循环播放的条目。触发词匹配的弹幕会暂停播报，AI 播完后再继续。
      </p>

      <div className="max-h-[420px] space-y-3 overflow-y-auto">
        {items.length === 0 && (
          <p className="py-6 text-center text-sm text-[var(--font-muted)]">暂无文案，点击「添加」</p>
        )}
        {items.map((row, idx) => (
          <div
            key={row.id}
            className="rounded-lg border border-[var(--border-app)] p-3"
            style={{ gap: "8px" }}
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="text-xs text-[var(--font-muted)]">#{idx + 1}</span>
              <label className="flex items-center gap-1.5 text-xs text-[var(--font-secondary)]">
                <input
                  type="checkbox"
                  checked={row.enabled}
                  onChange={(e) =>
                    setItems((prev) =>
                      prev.map((x) => (x.id === row.id ? { ...x, enabled: e.target.checked } : x)),
                    )
                  }
                />
                启用
              </label>
              <span className="flex-1" />
              <button
                type="button"
                className="rounded p-1 text-[var(--font-muted)] hover:bg-[var(--bg-card-hover)] hover:text-red-500"
                aria-label="删除"
                onClick={() => setItems((prev) => prev.filter((x) => x.id !== row.id))}
              >
                <Trash2 className="size-4" />
              </button>
            </div>
            <input
              type="text"
              placeholder="标题（便于识别）"
              value={row.title}
              onChange={(e) =>
                setItems((prev) =>
                  prev.map((x) => (x.id === row.id ? { ...x, title: e.target.value } : x)),
                )
              }
              className="mb-2 w-full rounded-md border border-[var(--border-app)] bg-transparent px-2 py-1.5 text-sm text-[var(--font-primary)]"
            />
            <textarea
              placeholder="播报正文（将用当前 TTS 引擎合成）"
              rows={3}
              value={row.text}
              onChange={(e) =>
                setItems((prev) =>
                  prev.map((x) => (x.id === row.id ? { ...x, text: e.target.value } : x)),
                )
              }
              className="w-full resize-y rounded-md border border-[var(--border-app)] bg-transparent px-2 py-1.5 text-sm text-[var(--font-primary)]"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
