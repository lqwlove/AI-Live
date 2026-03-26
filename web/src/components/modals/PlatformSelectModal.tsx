import { useEffect, useState } from "react";
import { Play, MonitorPlay, Music, Music2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useSessionStore } from "@/stores/sessionStore";
import type { Platform } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";

interface Props {
  open: boolean;
  onClose: () => void;
}

const PLATFORMS: {
  id: Platform;
  title: string;
  icon: typeof MonitorPlay;
  iconActiveClass: string;
}[] = [
  { id: "youtube", title: "YouTube", icon: MonitorPlay, iconActiveClass: "text-[#FF0000]" },
  { id: "douyin", title: "抖音 Douyin", icon: Music, iconActiveClass: "text-[#25F4EE]" },
  { id: "tiktok", title: "TikTok", icon: Music2, iconActiveClass: "text-[#69C9D0]" },
];

export function PlatformSelectModal({ open, onClose }: Props) {
  const [selected, setSelected] = useState<Platform | "">("");
  const [configStatus, setConfigStatus] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const store = useSessionStore();

  useEffect(() => {
    if (!open) return;
    setSelected("");
    PLATFORMS.forEach((p) =>
      api
        .validatePlatform(p.id)
        .then((r) => setConfigStatus((prev) => ({ ...prev, [p.id]: r.configured })))
        .catch(() => {}),
    );
  }, [open]);

  const handleOpenChange = (next: boolean) => {
    if (!next) onClose();
  };

  const handleStart = async () => {
    if (!selected) return;
    setLoading(true);
    try {
      store.setStatus("starting");
      await api.startSession(selected as Platform);
      onClose();
    } catch (e) {
      console.error(e);
      store.setStatus("idle");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        showCloseButton={false}
        overlayClassName="bg-[rgba(0,0,0,0.53)] backdrop-blur-[2px]"
        className={cn(
          "gap-6 rounded-2xl border border-[var(--border-app)] bg-[var(--bg-card)] p-8",
          "shadow-[0_8px_32px_rgba(0,0,0,0.4)] sm:max-w-[480px]",
        )}
      >
        <DialogHeader className="gap-2 text-left">
          <DialogTitle className="font-heading text-[22px] font-bold text-[var(--font-primary)]">
            Select Platform
          </DialogTitle>
          <DialogDescription className="text-sm text-[var(--font-muted)]">
            Choose which platform to connect for this live session.
          </DialogDescription>
        </DialogHeader>

        <RadioGroup
          value={selected || undefined}
          onValueChange={(v) => setSelected(v as Platform)}
          className="grid gap-3"
        >
          {PLATFORMS.map((p) => {
            const configured = configStatus[p.id] ?? false;
            const disabled = !configured;
            const isSelected = selected === p.id;
            const Icon = p.icon;
            return (
              <Label
                key={p.id}
                htmlFor={`plat-${p.id}`}
                className={cn(
                  "flex cursor-pointer items-center gap-4 rounded-[10px] border-2 p-4 transition-colors",
                  isSelected && configured
                    ? "border-[var(--accent-purple)] bg-[#7C3AED15]"
                    : "border-[var(--border-app)] bg-transparent",
                  disabled && "cursor-not-allowed opacity-50",
                )}
              >
                <RadioGroupItem value={p.id} id={`plat-${p.id}`} disabled={disabled} className="size-5" />
                <div className="min-w-0 flex-1">
                  <div className="text-[15px] font-semibold text-[var(--font-primary)]">{p.title}</div>
                  <div
                    className={cn(
                      "text-xs",
                      configured ? "text-[var(--success)]" : "text-[var(--font-muted)]",
                    )}
                  >
                    {configured
                      ? p.id === "youtube"
                        ? "✓ Configured · Video ID set"
                        : "✓ Configured"
                      : "Not configured"}
                  </div>
                </div>
                <Icon
                  className={cn(
                    "size-6 shrink-0",
                    disabled ? "text-[var(--font-muted)]" : p.iconActiveClass,
                  )}
                />
              </Label>
            );
          })}
        </RadioGroup>

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            className="h-auto rounded-lg border-[var(--border-app)] bg-transparent px-6 py-2.5 text-sm font-medium text-[var(--font-secondary)] hover:bg-[var(--bg-card-hover)]"
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!selected || loading}
            onClick={handleStart}
            className="h-auto gap-2 rounded-lg border-0 bg-gradient-to-b from-[var(--accent-purple)] to-[var(--accent-blue)] px-6 py-2.5 text-sm font-semibold text-white shadow-none hover:opacity-90 disabled:opacity-40"
          >
            <Play className="size-4" />
            {loading ? "Starting..." : "Start"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
