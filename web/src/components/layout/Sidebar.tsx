import { NavLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { LayoutDashboard, Settings, Play, Square, Package, Megaphone } from "lucide-react";
import { useSessionStore } from "@/stores/sessionStore";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Platform } from "@/types";
import { useState } from "react";
import { PlatformSelectModal } from "@/components/modals/PlatformSelectModal";
import { Button } from "@/components/ui/button";

const NAV_ITEMS: {
  to: string;
  icon: LucideIcon;
  label: string;
  end?: boolean;
}[] = [
  { to: "/", icon: LayoutDashboard, label: "控制台", end: true },
  { to: "/products", icon: Package, label: "商品库" },
  { to: "/announcements", icon: Megaphone, label: "播报文案" },
  { to: "/settings", icon: Settings, label: "设置" },
];

const PLATFORMS: { id: Platform; label: string }[] = [
  { id: "youtube", label: "YouTube" },
  { id: "douyin", label: "Douyin" },
  { id: "tiktok", label: "TikTok" },
];

export function Sidebar() {
  const { status, platform } = useSessionStore();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <aside
        className="flex h-full w-[200px] shrink-0 flex-col border-r border-[var(--border-app)] bg-[var(--bg-card)]"
        style={{
          paddingLeft: "var(--ds-sidebar-pad-x)",
          paddingRight: "var(--ds-sidebar-pad-x)",
          paddingTop: "var(--ds-sidebar-pad-y)",
          paddingBottom: "var(--ds-sidebar-pad-y)",
        }}
      >
        <div
          className="flex items-center"
          style={{ gap: "var(--ds-logo-gap)" }}
        >
          <div className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-b from-[var(--accent-purple)] to-[var(--accent-blue)]">
            <span className="text-[13px] font-bold text-white">AI</span>
          </div>
          <span className="text-base font-bold text-[var(--font-primary)]">直播助手</span>
        </div>

        {/* pen：Logo 下沿与 nav 容器顶对齐，nav 内 padding-top 20px */}
        <nav
          className="flex flex-col gap-1"
          style={{ paddingTop: "var(--ds-nav-section-pt)" }}
        >
          {NAV_ITEMS.map((item) => {
            if (item.to.startsWith("#")) {
              return (
                <a
                  key={item.label}
                  href={item.to}
                  onClick={(e) => e.preventDefault()}
                  className="flex items-center gap-2.5 rounded-md px-3 text-[13px] font-medium text-[var(--font-muted)] hover:text-[var(--font-secondary)]"
                  style={{ minHeight: "var(--ds-nav-item-h)" }}
                >
                  <item.icon className="size-[18px] shrink-0" strokeWidth={2} />
                  {item.label}
                </a>
              );
            }
            return (
              <NavLink
                key={item.label}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-md px-3 text-[13px] font-medium transition-colors",
                    isActive
                      ? "bg-[var(--accent-purple)] text-white"
                      : "text-[var(--font-muted)] hover:text-[var(--font-secondary)]",
                  )
                }
                style={{ minHeight: "var(--ds-nav-item-h)" }}
              >
                <item.icon className="size-[18px] shrink-0" strokeWidth={2} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div
          className="flex flex-col gap-2.5"
          style={{ paddingTop: "var(--ds-nav-section-pt)" }}
        >
          <span className="text-[11px] font-semibold tracking-[0.1em] text-[var(--font-muted)]">
            平台
          </span>
          {PLATFORMS.map((p) => {
            const live = status === "running" && platform === p.id;
            return (
              <div key={p.id} className="flex items-center gap-2 py-1">
                <span
                  className={cn(
                    "size-2 shrink-0 rounded-full",
                    live ? "bg-[var(--success)]" : "bg-[var(--font-muted)]",
                  )}
                />
                <span className="text-[13px] text-[var(--font-secondary)]">{p.label}</span>
              </div>
            );
          })}
        </div>

        <div className="min-h-4 flex-1" />

        {status === "running" ? (
          <Button
            variant="destructive"
            size="cta"
            className="w-full rounded-lg border border-[var(--error)] bg-transparent text-[13px] font-semibold text-[var(--error)] hover:bg-[var(--error)]/10"
            onClick={async () => {
              useSessionStore.getState().setStatus("stopping");
              await api.stopSession().catch(() => {});
            }}
          >
            <Square className="size-3.5" />
            停止直播
          </Button>
        ) : (
          <Button
            type="button"
            size="cta"
            onClick={() => setModalOpen(true)}
            className="w-full rounded-lg border-0 bg-gradient-to-b from-[var(--accent-purple)] to-[var(--accent-blue)] text-[13px] font-semibold leading-normal text-white shadow-none hover:opacity-90"
          >
            <Play className="size-4" />
            开始直播
          </Button>
        )}
      </aside>

      <PlatformSelectModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}
