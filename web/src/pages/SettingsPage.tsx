import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { api } from "@/lib/api";
import { PlatformConfig } from "@/components/settings/PlatformConfig";
import { TriggerKeywords } from "@/components/settings/TriggerKeywords";
import { AIConfig } from "@/components/settings/AIConfig";
import { TTSConfig } from "@/components/settings/TTSConfig";
import { Button } from "@/components/ui/button";

export function SettingsPage() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getConfig().then(setConfig).catch(console.error);
  }, []);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await api.updateConfig(config);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const update = (section: string, data: Record<string, unknown>) => {
    setConfig((prev) =>
      prev ? { ...prev, [section]: { ...(prev[section] as Record<string, unknown>), ...data } } : prev,
    );
  };

  if (!config) {
    return (
      <div className="flex h-full items-center justify-center text-[var(--font-muted)]">Loading...</div>
    );
  }

  return (
    <div className="tk-main-canvas">
      <header
        className="flex shrink-0 items-center"
        style={{ minHeight: "var(--ds-settings-header-h)", height: "var(--ds-settings-header-h)" }}
      >
        <h1 className="text-2xl leading-none font-bold tracking-tight text-[var(--font-primary)]">Settings</h1>
        <span className="min-w-0 flex-1" aria-hidden />
        <Button
          type="button"
          variant="outline"
          onClick={handleSave}
          disabled={saving}
          className="box-border h-8 gap-1.5 rounded-md border-[var(--border-app)] bg-[var(--bg-card)] px-4 py-0 text-[13px] font-medium text-[var(--font-secondary)] hover:bg-[var(--bg-card-hover)]"
        >
          <Save className="size-3.5" />
          {saving ? "Saving..." : "Save Config"}
        </Button>
      </header>

      <div
        className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-2"
        style={{ gap: "var(--ds-stack-gap)" }}
      >
        <div className="flex min-h-0 flex-col" style={{ gap: "var(--ds-stack-gap)" }}>
          <PlatformConfig config={config} onChange={update} />
          <div className="min-h-0 flex-1">
            <TriggerKeywords config={config} onChange={update} />
          </div>
        </div>
        <div className="flex flex-col" style={{ gap: "var(--ds-stack-gap)" }}>
          <AIConfig config={config} onChange={update} />
          <TTSConfig config={config} onChange={update} />
        </div>
      </div>
    </div>
  );
}
