import { Bot } from "lucide-react";

interface Props {
  config: Record<string, unknown>;
  onChange: (section: string, data: Record<string, unknown>) => void;
}

export function AIConfig({ config, onChange }: Props) {
  const ai = (config.ai ?? {}) as Record<string, unknown>;
  const set = (key: string, value: unknown) => onChange("ai", { [key]: value });

  return (
    <div className="flex flex-col gap-4 rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)] px-5 pt-4 pb-5">
      <div className="flex items-center gap-2">
        <Bot size={16} className="text-[var(--accent-purple)]" />
        <span className="text-sm font-semibold text-[var(--font-primary)]">AI Configuration</span>
      </div>
      <Field label="Model" value={ai.model as string} onChange={(v) => set("model", v)} />
      <Field label="Base URL" value={ai.base_url as string} onChange={(v) => set("base_url", v)} />
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-[var(--font-secondary)]">System Prompt</label>
        <textarea
          className="h-20 resize-none rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2.5 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
          value={(ai.system_prompt as string) ?? ""}
          onChange={(e) => set("system_prompt", e.target.value)}
        />
      </div>
      <div className="flex items-center">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-[13px] font-medium text-[var(--font-primary)]">Multilingual</span>
          <span className="text-[11px] text-[var(--font-muted)]">Auto-detect language and reply accordingly</span>
        </div>
        <button
          type="button"
          onClick={() => set("multilang", !(ai.multilang as boolean))}
          className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${(ai.multilang as boolean) ? "bg-[var(--accent-purple)]" : "bg-[var(--font-muted)]"}`}
        >
          <div className={`absolute top-0.5 size-4 rounded-full bg-white transition-transform ${(ai.multilang as boolean) ? "left-[18px]" : "left-0.5"}`} />
        </button>
      </div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-[var(--font-secondary)]">{label}</label>
      <input
        className="rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2.5 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
