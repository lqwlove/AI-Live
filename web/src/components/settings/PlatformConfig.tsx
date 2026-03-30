import { useState } from "react";
import { Globe } from "lucide-react";
import type { Platform } from "@/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  config: Record<string, unknown>;
  onChange: (section: string, data: Record<string, unknown>) => void;
}

const TABS: { key: Platform; label: string }[] = [
  { key: "youtube", label: "YouTube" },
  { key: "douyin", label: "Douyin" },
  { key: "tiktok", label: "TikTok" },
];

export function PlatformConfig({ config, onChange }: Props) {
  const [activeTab, setActiveTab] = useState<Platform>("youtube");

  return (
    <div className="overflow-hidden rounded-[10px] border border-[var(--border-app)] bg-[var(--bg-card)]">
      <div className="flex items-center gap-2 px-5 pt-4 pb-3">
        <Globe className="size-4 text-[var(--font-primary)]" strokeWidth={2} />
        <span className="text-sm font-semibold text-[var(--font-primary)]">平台配置</span>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as Platform)} className="gap-0">
        <TabsList
          variant="line"
          className="h-auto w-full justify-start gap-0 rounded-none border-b border-[var(--border-app)] bg-transparent p-0 px-5"
        >
          {TABS.map((tab) => (
            <TabsTrigger
              key={tab.key}
              value={tab.key}
              className="flex-none rounded-none border-0 border-b-2 border-transparent bg-transparent px-4 py-2.5 text-[13px] font-medium text-[var(--font-muted)] shadow-none data-active:border-[var(--font-primary)] data-active:bg-transparent data-active:text-[var(--font-primary)] dark:data-active:bg-transparent"
            >
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {TABS.map((tab) => (
          <TabsContent key={tab.key} value={tab.key} className="px-5 pt-4 pb-5">
            <PlatformTabBody tab={tab.key} config={config} onChange={onChange} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

function PlatformTabBody({
  tab,
  config,
  onChange,
}: {
  tab: Platform;
  config: Record<string, unknown>;
  onChange: (section: string, data: Record<string, unknown>) => void;
}) {
  const section = (config[tab] ?? {}) as Record<string, unknown>;
  const set = (key: string, value: unknown) => onChange(tab, { [key]: value });

  return (
    <div className="flex flex-col gap-4">
      {tab === "youtube" && (
        <>
          <ConfigField label="视频 ID（Video ID）" value={section.video_id as string} onChange={(v) => set("video_id", v)} />
          <ConfigField label="频道 ID（Channel ID）" value={section.channel_id as string} onChange={(v) => set("channel_id", v)} />
          <ConfigField label="API 密钥" value={section.api_key as string} onChange={(v) => set("api_key", v)} />
          <ToggleField label="自动回复聊天" checked={section.auto_reply as boolean} onChange={(v) => set("auto_reply", v)} />
        </>
      )}
      {tab === "douyin" && (
        <>
          <ConfigField label="房间 ID" value={section.room_id as string} onChange={(v) => set("room_id", v)} />
          <ConfigField label="直播链接" value={section.live_url as string} onChange={(v) => set("live_url", v)} />
          <ConfigField label="Cookie" value={section.cookie as string} onChange={(v) => set("cookie", v)} />
        </>
      )}
      {tab === "tiktok" && (
        <>
          <ConfigField label="用户名（不带 @）" value={section.unique_id as string} onChange={(v) => set("unique_id", v)} />
          <ConfigField
            label="代理"
            value={section.proxy as string}
            onChange={(v) => set("proxy", v)}
            placeholder="http://127.0.0.1:7890"
          />
        </>
      )}
    </div>
  );
}

function ConfigField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs font-medium text-[var(--font-secondary)]">{label}</Label>
      <Input
        placeholder={placeholder}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 border-[var(--border-app)] bg-[var(--input-bg)] text-[13px] text-[var(--font-primary)] placeholder:text-[var(--font-muted)]"
      />
    </div>
  );
}

function ToggleField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full transition-colors ${checked ? "bg-[var(--accent-purple)]" : "bg-[var(--font-muted)]"}`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${checked ? "translate-x-[18px]" : "translate-x-0.5"}`}
        />
      </button>
      <span className="text-[13px] font-medium text-[var(--font-primary)]">{label}</span>
    </div>
  );
}
