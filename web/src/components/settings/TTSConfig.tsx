import { Volume2 } from "lucide-react";

interface Props {
  config: Record<string, unknown>;
  onChange: (section: string, data: Record<string, unknown>) => void;
}

export function TTSConfig({ config, onChange }: Props) {
  const tts = (config.tts ?? {}) as Record<string, unknown>;
  const volc = (config.volcengine ?? {}) as Record<string, unknown>;
  const engine = (tts.engine as string) ?? "edge-tts";
  const isVolc = engine === "volcengine";

  const setTts = (key: string, value: unknown) => onChange("tts", { [key]: value });
  const setVolc = (key: string, value: unknown) => onChange("volcengine", { [key]: value });

  const rateNum = parseInt((tts.rate as string ?? "+0%").replace("%", ""), 10);
  const volumeNum = parseInt((tts.volume as string ?? "+0%").replace("%", ""), 10);
  const ratePct = ((rateNum + 50) / 100) * 100;
  const volumePct = ((volumeNum + 50) / 100) * 100;

  return (
    <div className="flex flex-col gap-4 rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)] px-5 pt-4 pb-5">
      <div className="flex items-center gap-2">
        <Volume2 size={16} className="text-[var(--accent-purple)]" />
        <span className="text-sm font-semibold text-[var(--font-primary)]">语音合成（TTS）</span>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-[var(--font-secondary)]">引擎</label>
        <select
          className="rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2.5 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
          value={engine}
          onChange={(e) => setTts("engine", e.target.value)}
        >
          <option value="edge-tts">Edge TTS（免费）</option>
          <option value="volcengine">火山引擎（声音复刻）</option>
        </select>
      </div>

      {isVolc ? (
        <>
          <Field label="Speaker ID (音色 ID)" value={volc.speaker_id as string} onChange={(v) => setVolc("speaker_id", v)} />
          <Field label="应用 ID（App ID）" value={volc.app_id as string} onChange={(v) => setVolc("app_id", v)} />
          <Field label="访问令牌（Access Token）" value={volc.access_token as string} onChange={(v) => setVolc("access_token", v)} type="password" />
          <Field label="资源 ID（Resource ID）" value={volc.resource_id as string} onChange={(v) => setVolc("resource_id", v)} />
        </>
      ) : (
        <Field label="音色（Voice）" value={tts.voice as string} onChange={(v) => setTts("voice", v)} />
      )}

      <div className="flex gap-6">
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <div className="flex items-center">
            <span className="text-xs font-medium text-[var(--font-secondary)]">语速</span>
            <span className="min-w-0 flex-1" />
            <span className="text-xs font-medium text-[var(--font-primary)]">
              {tts.rate as string ?? "+0%"}
            </span>
          </div>
          <div
            className="relative h-1 w-full cursor-pointer rounded-sm bg-[var(--border-app)]"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
              const val = Math.round(pct * 100 - 50);
              setTts("rate", `${val >= 0 ? "+" : ""}${val}%`);
            }}
          >
            <div
              className="absolute top-0 left-0 h-full rounded-sm bg-[var(--accent-purple)]"
              style={{ width: `${ratePct}%` }}
            />
          </div>
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <div className="flex items-center">
            <span className="text-xs font-medium text-[var(--font-secondary)]">音量</span>
            <span className="min-w-0 flex-1" />
            <span className="text-xs font-medium text-[var(--font-primary)]">
              {tts.volume as string ?? "+0%"}
            </span>
          </div>
          <div
            className="relative h-1 w-full cursor-pointer rounded-sm bg-[var(--border-app)]"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
              const val = Math.round(pct * 100 - 50);
              setTts("volume", `${val >= 0 ? "+" : ""}${val}%`);
            }}
          >
            <div
              className="absolute top-0 left-0 h-full rounded-sm bg-[var(--accent-blue)]"
              style={{ width: `${volumePct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-[var(--font-secondary)]">{label}</label>
      <input
        type={type}
        className="rounded-md border border-[var(--border-app)] bg-[var(--input-bg)] px-3 py-2.5 text-[13px] text-[var(--font-primary)] outline-none focus:border-[var(--accent-purple)]"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
