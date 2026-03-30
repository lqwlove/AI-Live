import { useSessionStore } from "@/stores/sessionStore";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { ChatPanel } from "@/components/dashboard/ChatPanel";
import { AIResponsePanel } from "@/components/dashboard/AIResponsePanel";
import { BgmControlBar } from "@/components/dashboard/BgmControlBar";
import { AnnounceControlBar } from "@/components/dashboard/AnnounceControlBar";

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
      <header className="flex shrink-0 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div
          className="flex shrink-0 flex-wrap items-center"
          style={{ gap: "var(--ds-tight-gap)" }}
        >
          <h1 className="shrink-0 text-2xl leading-none font-bold tracking-tight whitespace-nowrap text-[var(--font-primary)]">
            控制台
          </h1>
          {isRunning ? (
            <div
              className="inline-flex items-center rounded-xl py-1 pr-2.5 pl-2.5"
              style={{ background: "#16A34A22", gap: "6px" }}
            >
              <span className="size-2 shrink-0 rounded-full bg-[var(--success)]" />
              <span className="text-xs leading-none font-semibold text-[var(--success)]">
                直播中 · {platformLabel(platform)}
              </span>
            </div>
          ) : (
            <div
              className="inline-flex items-center rounded-xl py-1 pr-2.5 pl-2.5"
              style={{ background: "#71717A22", gap: "6px" }}
            >
              <span className="size-2 shrink-0 rounded-full bg-[var(--font-muted)]" />
              <span className="text-xs leading-none font-semibold text-[var(--font-muted)]">未开播</span>
            </div>
          )}
        </div>
        {isRunning ? (
          <div className="flex w-full min-w-0 flex-wrap items-center gap-3 sm:w-auto sm:shrink-0 sm:justify-end">
            <BgmControlBar />
            <AnnounceControlBar />
          </div>
        ) : null}
      </header>

      {isRunning ? (
        <div className="flex min-h-0 min-w-0 flex-1" style={{ gap: "var(--ds-row-gap)" }}>
          <ChatPanel />
          <AIResponsePanel />
        </div>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}
