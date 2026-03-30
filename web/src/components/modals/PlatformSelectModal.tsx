import { useEffect, useState } from "react";
import { Play, MonitorPlay, Music, Music2, Disc3 } from "lucide-react";
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

const BGM_DEFAULT = "__bgm_default__";
const BGM_NONE = "__bgm_none__";

export function PlatformSelectModal({ open, onClose }: Props) {
  const [selected, setSelected] = useState<Platform | "">("");
  const [configStatus, setConfigStatus] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [bgmFiles, setBgmFiles] = useState<string[]>([]);
  const [bgmChoice, setBgmChoice] = useState<string>(BGM_DEFAULT);
  const store = useSessionStore();

  useEffect(() => {
    if (!open) return;
    setSelected("");
    setBgmChoice(BGM_DEFAULT);
    PLATFORMS.forEach((p) =>
      api
        .validatePlatform(p.id)
        .then((r) => setConfigStatus((prev) => ({ ...prev, [p.id]: r.configured })))
        .catch(() => {}),
    );
    api
      .listBgmFiles()
      .then((r) => setBgmFiles(r.files ?? []))
      .catch(() => setBgmFiles([]));
  }, [open]);

  const handleOpenChange = (next: boolean) => {
    if (!next) onClose();
  };

  const handleStart = async () => {
    if (!selected) return;
    setLoading(true);
    try {
      store.setStatus("starting");
      const sessionOpts: Record<string, unknown> = {};
      if (bgmChoice !== BGM_DEFAULT) {
        sessionOpts.bgm_file = bgmChoice === BGM_NONE ? "" : bgmChoice;
      }
      await api.startSession(selected as Platform, sessionOpts);
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
          <DialogTitle className="font-heading text-[22px] font-bold text-[var(--font-primary)]">选择平台</DialogTitle>
          <DialogDescription className="text-sm text-[var(--font-muted)]">
            选择本次直播要连接的平台。
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
                        ? "✓ 已配置（已填 Video ID 等）"
                        : "✓ 已配置"
                      : "未配置"}
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

        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--font-primary)]">
            <Disc3 className="size-4 text-[var(--accent-purple)]" />
            背景音乐
          </div>
          <p className="text-xs text-[var(--font-muted)]">
            将音频文件放入项目根目录的 <code className="rounded bg-[var(--bg-card-hover)] px-1">bgm</code>{" "}
            文件夹后，开播时可在此选择；需安装 pygame 以播放循环 BGM。
          </p>
          <select
            value={bgmChoice}
            onChange={(e) => setBgmChoice(e.target.value)}
            className={cn(
              "h-10 w-full rounded-[10px] border-2 border-[var(--border-app)] bg-transparent px-3 text-sm",
              "text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]",
            )}
          >
            <option value={BGM_DEFAULT}>默认（按配置文件 bgm 设置）</option>
            <option value={BGM_NONE}>本场不播放背景音乐</option>
            {bgmFiles.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            className="h-auto rounded-lg border-[var(--border-app)] bg-transparent px-6 py-2.5 text-sm font-medium text-[var(--font-secondary)] hover:bg-[var(--bg-card-hover)]"
          >
            取消
          </Button>
          <Button
            type="button"
            disabled={!selected || loading}
            onClick={handleStart}
            className="h-auto gap-2 rounded-lg border-0 bg-gradient-to-b from-[var(--accent-purple)] to-[var(--accent-blue)] px-6 py-2.5 text-sm font-semibold text-white shadow-none hover:opacity-90 disabled:opacity-40"
          >
            <Play className="size-4" />
            {loading ? "启动中…" : "开始"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
