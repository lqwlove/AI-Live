import { CirclePlay, Settings, Play } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { PlatformSelectModal } from "@/components/modals/PlatformSelectModal";
import { Button } from "@/components/ui/button";

export function EmptyState() {
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <div
        className="flex min-h-0 min-w-0 flex-1 flex-col items-center justify-center rounded-[12px] border border-[var(--border-app)] bg-[var(--bg-card)]"
        style={{ gap: "var(--ds-empty-stack)" }}
      >
        <CirclePlay className="size-14 shrink-0 text-[var(--font-muted)]" strokeWidth={1.25} />
        <h2 className="text-[20px] font-bold leading-tight text-[var(--font-primary)]">当前未开播</h2>
        <p className="max-w-[400px] text-center text-sm leading-normal text-[var(--font-muted)]">
          请先在设置中配置平台，再启动直播助手以开始监听弹幕。
        </p>
        <div
          className="flex flex-wrap items-center justify-center"
          style={{ gap: "var(--ds-tight-gap)", paddingTop: "var(--ds-empty-btn-row-pt)" }}
        >
          <Button
            type="button"
            variant="outline"
            size="cta"
            onClick={() => navigate("/settings")}
            className="rounded-[8px] border-[var(--border-app)] bg-transparent text-sm font-medium leading-normal text-[var(--font-secondary)] hover:bg-[var(--bg-card-hover)]"
          >
            <Settings className="size-4 shrink-0" />
            前往设置
          </Button>
          <Button
            type="button"
            size="cta"
            onClick={() => setModalOpen(true)}
            className="rounded-[8px] border-0 bg-gradient-to-b from-[var(--accent-purple)] to-[var(--accent-blue)] text-sm font-semibold leading-normal text-white shadow-none hover:opacity-90"
          >
            <Play className="size-4 shrink-0" />
            开始直播
          </Button>
        </div>
      </div>

      <PlatformSelectModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}
