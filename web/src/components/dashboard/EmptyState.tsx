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
        className="flex min-h-0 flex-1 flex-col items-center justify-center rounded-xl border border-[var(--border-app)] bg-[var(--bg-card)] px-6 py-10"
        style={{ gap: "var(--ds-empty-stack)" }}
      >
        <CirclePlay className="size-14 text-[var(--font-muted)]" strokeWidth={1.25} />
        <h2 className="text-xl font-bold text-[var(--font-primary)]">No Active Session</h2>
        <p className="max-w-[400px] text-center text-sm text-[var(--font-muted)]">
          Configure your platform settings and start the live assistant to begin monitoring chat.
        </p>
        <div className="flex gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/settings")}
            className="h-auto gap-2 rounded-lg border-[var(--border-app)] bg-transparent px-5 py-2.5 text-sm font-medium text-[var(--font-secondary)] hover:bg-[var(--bg-card-hover)]"
          >
            <Settings className="size-4" />
            Go to Settings
          </Button>
          <Button
            type="button"
            onClick={() => setModalOpen(true)}
            className="h-auto gap-2 rounded-lg border-0 bg-gradient-to-b from-[var(--accent-purple)] to-[var(--accent-blue)] px-5 py-2.5 text-sm font-semibold text-white shadow-none hover:opacity-90"
          >
            <Play className="size-4" />
            Start Live Assistant
          </Button>
        </div>
      </div>

      <PlatformSelectModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}
