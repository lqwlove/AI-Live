import { useCallback, useEffect, useState } from "react";
import { Megaphone, Play, Square } from "lucide-react";
import { api, type AnnounceItem } from "@/lib/api";
import { useSessionStore } from "@/stores/sessionStore";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function AnnounceControlBar() {
  const status = useSessionStore((s) => s.status);
  const announceCurrent = useSessionStore((s) => s.announceCurrent);
  const setAnnounceCurrent = useSessionStore((s) => s.setAnnounceCurrent);
  const isLive = status === "running";

  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AnnounceItem[]>([]);
  const [enabled, setEnabled] = useState(false);
  const [activeIds, setActiveIds] = useState<Set<string>>(new Set());
  const [intervalSec, setIntervalSec] = useState(30);
  const [voiceVol, setVoiceVol] = useState(1);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  const loadItems = useCallback(() => {
    api.getAnnounceItems().then(setItems).catch(() => setItems([]));
  }, []);

  const loadRuntime = useCallback(() => {
    api
      .getAnnounceRuntime()
      .then((r) => {
        setEnabled(r.enabled);
        setActiveIds(new Set(r.active_ids ?? []));
        setAnnounceCurrent(r.current ?? null);
        setIntervalSec(Math.round(r.interval_seconds ?? 30));
        setVoiceVol(r.voice_volume ?? 1);
      })
      .catch(() => {});
  }, [setAnnounceCurrent]);

  useEffect(() => {
    loadItems();
    loadRuntime();
  }, [loadItems, loadRuntime, isLive]);

  useEffect(() => {
    if (open) {
      loadItems();
      loadRuntime();
    }
  }, [open, loadItems, loadRuntime]);

  const toggleId = (id: string) => {
    setActiveIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const orderedActiveIds = items.filter((i) => activeIds.has(i.id)).map((i) => i.id);

  const stopCurrent = async () => {
    if (!isLive || stopping) return;
    setStopping(true);
    try {
      const r = await api.stopAnnouncement();
      setAnnounceCurrent(r.current ?? null);
    } catch (e) {
      console.error(e);
    } finally {
      setStopping(false);
    }
  };

  const playItem = async (id: string) => {
    if (!isLive || actionId) return;
    setActionId(id);
    try {
      const r = await api.playAnnouncement(id);
      setAnnounceCurrent(r.current ?? null);
    } catch (e) {
      console.error(e);
    } finally {
      setActionId(null);
    }
  };

  const apply = async (): Promise<boolean> => {
    if (!isLive) return false;
    setSaving(true);
    try {
      const r = await api.putAnnounceRuntime({
        enabled,
        active_ids: orderedActiveIds,
        interval_seconds: intervalSec,
        voice_volume: voiceVol,
      });
      setAnnounceCurrent(r.current ?? null);
      loadRuntime();
      return true;
    } catch (e) {
      console.error(e);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const enabledItems = items.filter((i) => i.enabled);

  return (
    <>
      <Button
        type="button"
        variant="outline"
        disabled={!isLive}
        onClick={() => setOpen(true)}
        className="box-border h-8 shrink-0 gap-1.5 rounded-md border-[var(--border-app)] bg-[var(--bg-card)] px-3 py-0 text-[13px] font-medium text-[var(--font-secondary)] hover:bg-[var(--bg-card-hover)]"
      >
        <Megaphone className="size-3.5 shrink-0 text-[var(--accent-purple)]" aria-hidden />
        自动播报
        {isLive && enabled ? (
          <span className="rounded bg-[var(--accent-purple)]/15 px-1.5 py-0 text-[11px] font-semibold text-[var(--accent-purple)]">
            {announceCurrent ? "播报中" : "开"}
          </span>
        ) : null}
      </Button>

      {isLive && announceCurrent ? (
        <Button
          type="button"
          variant="outline"
          disabled={stopping}
          onClick={() => void stopCurrent()}
          className="box-border h-8 shrink-0 gap-1.5 rounded-md border-red-500/30 bg-red-500/10 px-3 py-0 text-[13px] font-medium text-red-500 hover:bg-red-500/15"
        >
          <Square className="size-3.5 shrink-0" aria-hidden />
          {stopping ? "停止中…" : "停止播报"}
        </Button>
      ) : null}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          showCloseButton
          className="max-h-[min(85vh,640px)] w-full max-w-[calc(100%-2rem)] gap-0 overflow-hidden border-[var(--border-app)] bg-[var(--bg-card)] p-0 text-[var(--font-primary)] sm:max-w-lg"
        >
          <DialogHeader className="border-b border-[var(--border-app)] px-5 py-4 text-left">
            <DialogTitle className="flex items-center gap-2 text-lg font-semibold text-[var(--font-primary)]">
              <Megaphone className="size-5 text-[var(--accent-purple)]" aria-hidden />
              自动播报
            </DialogTitle>
            <DialogDescription className="text-[13px] text-[var(--font-muted)]">
              选择参与循环的文案、间隔与语音音量，保存后作用于当前直播。
            </DialogDescription>
          </DialogHeader>

          <div
            className="flex max-h-[min(60vh,480px)] flex-col overflow-y-auto px-5 py-4"
            style={{ gap: "var(--ds-tight-gap)" }}
          >
            <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--font-secondary)]">
              <input
                type="checkbox"
                checked={enabled}
                disabled={!isLive}
                onChange={(e) => setEnabled(e.target.checked)}
                className="size-4 rounded border-[var(--border-app)]"
              />
              开启循环播报
            </label>

            {announceCurrent ? (
              <div className="rounded-lg border border-[var(--accent-purple)]/30 bg-[var(--accent-purple)]/10 px-3 py-2">
                <div className="mb-1 flex items-center gap-2">
                  <span className="size-2 rounded-full bg-[var(--accent-purple)]" />
                  <span className="text-xs font-semibold text-[var(--accent-purple)]">正在播报</span>
                  <span className="min-w-0 flex-1 truncate text-xs text-[var(--font-muted)]">
                    {announceCurrent.source === "manual" ? "手动" : "自动"}
                  </span>
                  <button
                    type="button"
                    disabled={stopping}
                    onClick={() => void stopCurrent()}
                    className="text-xs font-semibold text-red-500 hover:underline disabled:opacity-60"
                  >
                    停止
                  </button>
                </div>
                <div className="truncate text-sm font-medium text-[var(--font-primary)]">
                  {announceCurrent.title || "（无标题）"}
                </div>
                <div className="truncate text-xs text-[var(--font-muted)]">{announceCurrent.text}</div>
              </div>
            ) : null}

            <div className="text-xs font-medium text-[var(--font-muted)]">参与循环的文案（顺序为列表顺序）</div>
            <div className="max-h-40 space-y-1.5 overflow-y-auto rounded-md border border-[var(--border-app)]/60 p-2">
              {enabledItems.length === 0 ? (
                <p className="px-1 py-2 text-xs text-[var(--font-muted)]">请在侧栏「播报文案」中添加文案</p>
              ) : (
                enabledItems.map((i) => {
                  const isPlaying = announceCurrent?.id === i.id;
                  return (
                    <div
                      key={i.id}
                      className="flex items-start gap-2 rounded-md px-1 py-0.5 hover:bg-[var(--bg-card-hover)]"
                    >
                    <input
                      type="checkbox"
                      checked={activeIds.has(i.id)}
                      disabled={!isLive}
                      onChange={() => toggleId(i.id)}
                      className="mt-0.5 size-4 shrink-0 rounded border-[var(--border-app)]"
                    />
                    <span className="min-w-0 text-xs text-[var(--font-primary)]">
                      <span className="font-medium">
                        {i.title || "（无标题）"}
                        {isPlaying ? (
                          <span className="ml-1 rounded bg-[var(--accent-purple)]/15 px-1 text-[var(--accent-purple)]">
                            正在播
                          </span>
                        ) : null}
                      </span>
                      <span className="block truncate text-[var(--font-muted)]">{i.text}</span>
                    </span>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!isLive || actionId !== null}
                      onClick={() => void playItem(i.id)}
                      className="ml-auto h-7 shrink-0 rounded-md border-[var(--border-app)] bg-transparent px-2 text-xs text-[var(--font-secondary)]"
                    >
                      <Play className="size-3" />
                      {actionId === i.id ? "切换中…" : isPlaying ? "重播" : "播这条"}
                    </Button>
                    </div>
                  );
                })
              )}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs text-[var(--font-muted)]">间隔（秒）</label>
                <input
                  type="number"
                  min={1}
                  max={3600}
                  value={intervalSec}
                  disabled={!isLive}
                  onChange={(e) => setIntervalSec(Number(e.target.value) || 30)}
                  className={cn(
                    "h-9 w-full rounded-lg border-2 border-[var(--border-app)] bg-transparent px-2 text-sm",
                    "text-[var(--font-primary)]",
                  )}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--font-muted)]">
                  语音音量 {Math.round(voiceVol * 100)}%（建议用 pygame 播放以生效）
                </label>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={voiceVol}
                  disabled={!isLive}
                  onChange={(e) => setVoiceVol(Number(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 border-t border-[var(--border-app)] px-5 py-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              className="h-9 rounded-lg border-[var(--border-app)] bg-transparent text-[var(--font-secondary)]"
            >
              关闭
            </Button>
            <Button
              type="button"
              disabled={!isLive || saving}
              onClick={() => void apply().then((ok) => ok && setOpen(false))}
              className="h-9 rounded-lg bg-[var(--accent-purple)] text-sm text-white hover:opacity-90"
            >
              {saving ? "应用中…" : "应用到直播"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
