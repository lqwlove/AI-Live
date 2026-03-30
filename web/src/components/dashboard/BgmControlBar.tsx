import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Disc3, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type BgmStatus = {
  playing: boolean;
  file: string | null;
  volume: number;
  duck_volume: number;
};

export function BgmControlBar() {
  const [files, setFiles] = useState<string[]>([]);
  const [bgmStatus, setBgmStatus] = useState<BgmStatus | null>(null);
  const [volUi, setVolUi] = useState(0.3);
  const [pending, setPending] = useState(false);
  const volDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [f, s] = await Promise.all([api.listBgmFiles(), api.getBgmStatus()]);
      setFiles(f.files ?? []);
      const st = s as BgmStatus;
      setBgmStatus(st);
      setVolUi(st.volume);
    } catch {
      setFiles([]);
      setBgmStatus(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = window.setInterval(() => void refresh(), 8000);
    return () => window.clearInterval(t);
  }, [refresh]);

  const selectOptions = useMemo(() => {
    const set = new Set(files);
    const cur = bgmStatus?.file;
    if (cur && !set.has(cur)) {
      return [cur, ...files];
    }
    return files;
  }, [files, bgmStatus?.file]);

  const selectValue =
    bgmStatus?.playing && bgmStatus.file ? bgmStatus.file : "";

  const onSelectChange = async (value: string) => {
    setPending(true);
    try {
      if (!value) {
        await api.stopBgm();
      } else {
        await api.playBgm(value);
      }
      await refresh();
    } catch (e) {
      console.error(e);
      await refresh();
    } finally {
      setPending(false);
    }
  };

  const onVolumeInput = (v: number) => {
    if (volDebounce.current) clearTimeout(volDebounce.current);
    volDebounce.current = setTimeout(() => {
      api.setBgmVolume(v).then(() => refresh()).catch(console.error);
    }, 350);
  };

  return (
    <div
      className={cn(
        "flex min-w-0 w-full max-w-full flex-col gap-2 sm:w-[min(100%,360px)] sm:max-w-[360px] sm:flex-none",
      )}
    >
      <div className="flex items-center gap-2" style={{ gap: "var(--ds-tight-gap)" }}>
        <Disc3 className="size-4 shrink-0 text-[var(--accent-purple)]" aria-hidden />
        <div className="min-w-0 flex-1">
          <label htmlFor="dashboard-bgm" className="sr-only">
            背景音乐
          </label>
          <div className="relative">
            <select
              id="dashboard-bgm"
              value={selectValue}
              disabled={pending}
              onChange={(e) => void onSelectChange(e.target.value)}
              className={cn(
                "h-9 w-full min-w-0 rounded-lg border-2 border-[var(--border-app)] bg-[var(--bg-card)] px-3 pr-8 text-sm",
                "text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]",
                "disabled:opacity-50",
              )}
            >
              <option value="">停止播放</option>
              {selectOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            {pending ? (
              <Loader2 className="pointer-events-none absolute top-1/2 right-2 size-4 -translate-y-1/2 animate-spin text-[var(--font-muted)]" />
            ) : null}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 pl-6 sm:pl-0">
        <span className="shrink-0 text-[11px] text-[var(--font-muted)]">BGM 音量</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={volUi}
          onChange={(e) => {
            const n = Number(e.target.value);
            setVolUi(n);
            onVolumeInput(n);
          }}
          className="min-w-0 flex-1"
          aria-label="背景音乐音量"
        />
        <span className="w-8 shrink-0 text-right text-[11px] tabular-nums text-[var(--font-muted)]">
          {Math.round(volUi * 100)}%
        </span>
      </div>
    </div>
  );
}
