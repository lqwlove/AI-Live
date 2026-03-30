import { useRef, useEffect } from "react";
import { MessageSquare } from "lucide-react";
import { useSessionStore } from "@/stores/sessionStore";
import { Badge } from "@/components/ui/badge";

const AVATAR_PALETTE = ["#7C3AED", "#2563EB", "#EF4444", "#F59E0B", "#22C55E"] as const;

function avatarColor(index: number) {
  return AVATAR_PALETTE[index % AVATAR_PALETTE.length];
}

function platformBadgeLabel(platform: string | null) {
  if (platform === "youtube") return "YouTube";
  if (platform === "douyin") return "Douyin";
  if (platform === "tiktok") return "TikTok";
  return "直播中";
}

export function ChatPanel() {
  const messages = useSessionStore((s) => s.chatMessages);
  const platform = useSessionStore((s) => s.platform);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)]">
      <div
        className="box-border flex shrink-0 items-center gap-2 px-5 py-4"
      >
        <MessageSquare className="size-4 shrink-0 text-[var(--font-primary)]" strokeWidth={2} />
        <span className="text-sm font-semibold text-[var(--font-primary)]">实时弹幕</span>
        <span className="min-w-0 flex-1" aria-hidden />
        <Badge
          variant="secondary"
          className="h-auto shrink-0 rounded px-2 py-1 text-[11px] font-medium tracking-normal text-[var(--font-secondary)] bg-[var(--border-app)] hover:bg-[var(--border-app)]"
        >
          {platformBadgeLabel(platform)}
        </Badge>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div
          className="flex flex-col px-5 pb-4"
          style={{ gap: "var(--ds-msg-gap)" }}
        >
          {messages.map((msg, i) => (
            <div key={`${msg.timestamp}-${i}`} className="flex" style={{ gap: "10px" }}>
              <div
                className="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                style={{ background: avatarColor(i) }}
              >
                {msg.user[0]?.toUpperCase() ?? "?"}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold text-[var(--font-primary)]">{msg.user}</div>
                <p className="mt-0.5 text-[13px] leading-snug text-[var(--font-secondary)]">
                  {msg.content}
                </p>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
