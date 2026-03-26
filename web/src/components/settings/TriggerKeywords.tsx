import { useState } from "react";
import { Filter, Plus, X } from "lucide-react";

interface Props {
  config: Record<string, unknown>;
  onChange: (section: string, data: Record<string, unknown>) => void;
}

export function TriggerKeywords({ config, onChange }: Props) {
  const filter = (config.filter ?? {}) as Record<string, unknown>;
  const keywords = (filter.keywords ?? []) as string[];
  const [input, setInput] = useState("");

  const addKeyword = () => {
    const kw = input.trim();
    if (!kw || keywords.includes(kw)) return;
    onChange("filter", { keywords: [...keywords, kw] });
    setInput("");
  };

  const removeKeyword = (kw: string) => {
    onChange("filter", { keywords: keywords.filter((k) => k !== kw) });
  };

  const setFilter = (key: string, value: unknown) => onChange("filter", { [key]: value });

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)]">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-[var(--border-app)] px-5 pt-4 pb-3">
        <Filter size={16} className="text-[var(--accent-purple)]" />
        <span className="text-sm font-semibold text-[var(--font-primary)]">
          Message Filter / Trigger Words
        </span>
        <span className="ml-auto text-xs text-[var(--font-muted)]">
          {keywords.length} keywords
        </span>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col gap-3 overflow-auto px-5 pb-5">
        <label className="text-xs font-medium text-[var(--font-secondary)]">Trigger Keywords</label>

        {/* Tag cloud */}
        <div className="flex flex-wrap gap-2">
          {keywords.map((kw) => (
            <span
              key={kw}
              className="flex items-center gap-1.5 rounded-md bg-[var(--accent-purple)] px-3 py-1.5 text-xs font-medium text-white"
            >
              {kw}
              <button onClick={() => removeKeyword(kw)} className="opacity-70 hover:opacity-100">
                <X size={12} />
              </button>
            </span>
          ))}
        </div>

        {/* Input + add */}
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2.5 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
            placeholder="Type a keyword and press Add..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addKeyword()}
          />
          <button
            onClick={addKeyword}
            className="flex items-center gap-1.5 rounded-md bg-[var(--accent-purple)] px-4 py-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
          >
            <Plus size={14} />
            Add
          </button>
        </div>

        {/* Separator */}
        <hr className="border-[var(--border-app)]" />
        <label className="text-xs font-semibold text-[var(--font-muted)]">Advanced Filters</label>

        {/* Min / Max */}
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--font-secondary)]">Min Length</label>
            <input
              type="number"
              className="rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2.5 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
              value={filter.min_length as number ?? 2}
              onChange={(e) => setFilter("min_length", Number(e.target.value))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--font-secondary)]">Max Length</label>
            <input
              type="number"
              className="rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2.5 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
              value={filter.max_length as number ?? 200}
              onChange={(e) => setFilter("max_length", Number(e.target.value))}
            />
          </div>
        </div>

        {/* Cooldown */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--font-secondary)]">Cooldown (seconds)</label>
          <input
            type="number"
            className="rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2.5 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
            value={filter.cooldown_seconds as number ?? 3}
            onChange={(e) => setFilter("cooldown_seconds", Number(e.target.value))}
          />
        </div>
      </div>
    </div>
  );
}
