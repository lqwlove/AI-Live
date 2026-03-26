import { useSessionStore } from "@/stores/sessionStore";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { ChatPanel } from "@/components/dashboard/ChatPanel";
import { AIResponsePanel } from "@/components/dashboard/AIResponsePanel";

function platformLabel(id: string | null) {
  if (id === "youtube") return "YouTube";
  if (id === "douyin") return "Douyin";
  if (id === "tiktok") return "TikTok";
  return "";
}

export function DashboardPage() {
  const { status, platform } = useSessionStore();
  const isRunning = status === "running" || status === "starting";


  return (
    <div className="tk-main-canvas">
      <header className="flex shrink-0 items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <h1 className="text-2xl leading-none font-bold tracking-tight text-[var(--font-primary)]">
            Dashboard
          </h1>
          {isRunning ? (
            <div
              className="inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1"
              style={{ background: "#16A34A22" }}
            >
              <span className="size-2 shrink-0 rounded-full bg-[var(--success)]" />
              <span className="text-xs leading-none font-semibold text-[var(--success)]">
                Live · {platformLabel(platform)}
              </span>
            </div>
          ) : (
            <div
              className="inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1"
              style={{ background: "#71717A22" }}
            >
              <span className="size-2 shrink-0 rounded-full bg-[var(--font-muted)]" />
              <span className="text-xs leading-none font-semibold text-[var(--font-muted)]">Offline</span>
            </div>
          )}
        </div>
      </header>

      {isRunning ? (
        <div className="flex min-h-0 flex-1 gap-4">
          <ChatPanel />
          <AIResponsePanel />
        </div>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}
