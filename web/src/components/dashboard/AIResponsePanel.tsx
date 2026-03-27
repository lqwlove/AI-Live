import { useRef, useEffect, useMemo } from "react";
import { Bot, User } from "lucide-react";
import { useSessionStore } from "@/stores/sessionStore";

const STATUS_CONFIG: Record<
  string,
  { text: string; dotColor: string; textColor: string; bgColor: string }
> = {
  speaking: {
    text: "Playing",
    dotColor: "var(--success)",
    textColor: "var(--success)",
    bgColor: "#22C55E22",
  },
  generating: {
    text: "Generating",
    dotColor: "var(--warning)",
    textColor: "var(--warning)",
    bgColor: "#F59E0B22",
  },
  done: {
    text: "Queued",
    dotColor: "",
    textColor: "var(--font-muted)",
    bgColor: "#A1A1AA22",
  },
};

function AudioWaveform() {
  const heights = [8, 14, 6, 16, 10, 6, 12, 8];
  return (
    <div
      className="flex items-center gap-0.5 rounded px-2"
      style={{ background: "#7C3AED33", height: 24, width: "100%" }}
    >
      {heights.map((h, i) => (
        <div
          key={i}
          className="rounded-sm bg-[var(--accent-purple)]"
          style={{ width: 3, height: h }}
        />
      ))}
    </div>
  );
}

export function AIResponsePanel() {
  const responses = useSessionStore((s) => s.aiResponses);
  const bottomRef = useRef<HTMLDivElement>(null);

  const pending = useMemo(
    () => responses.filter((r) => r.status === "generating" || r.status === "speaking").length,
    [responses],
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [responses.length]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)]">
      <div className="flex shrink-0 items-center gap-2 px-5 py-4">
        <Bot className="size-4 shrink-0 text-[var(--font-primary)]" strokeWidth={2} />
        <span className="text-sm font-semibold text-[var(--font-primary)]">AI Response Queue</span>
        <span className="min-w-0 flex-1" aria-hidden />
        <span
          className="rounded px-2 py-1 text-[11px] font-medium text-[var(--accent-purple)]"
          style={{ background: "#7C3AED22" }}
        >
          {pending} pending
        </span>
      </div>

      <div
        className="flex min-h-0 flex-1 flex-col overflow-y-auto px-5 pb-4"
        style={{ gap: "var(--ds-ai-card-gap)" }}
      >
        {responses.map((resp, i) => {
          const cfg = STATUS_CONFIG[resp.status] ?? STATUS_CONFIG.done;
          return (
            <div
              key={`${resp.timestamp}-${i}`}
              className="flex flex-col gap-2.5 rounded-[8px] border border-[var(--border-app)] bg-[var(--input-bg)] p-4"
            >
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5">
                  <User className="size-3.5 text-[var(--font-secondary)]" />
                  <span className="text-[13px] font-medium text-[var(--font-primary)]">{resp.user}</span>
                </div>
                <span className="min-w-0 flex-1" aria-hidden />
                <span
                  className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold"
                  style={{ background: cfg.bgColor, color: cfg.textColor }}
                >
                  {cfg.dotColor && (
                    <span
                      className="size-1.5 rounded-full"
                      style={{ background: cfg.dotColor }}
                    />
                  )}
                  {cfg.text}
                </span>
              </div>

              {resp.reply ? (
                <p className="text-[13px] leading-snug text-[var(--font-secondary)]">{resp.reply}</p>
              ) : resp.content ? (
                <p className="text-[13px] text-[var(--font-muted)]">
                  {resp.status === "done" ? "Waiting for AI response..." : resp.content}
                </p>
              ) : null}

              {resp.status === "speaking" && <AudioWaveform />}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
