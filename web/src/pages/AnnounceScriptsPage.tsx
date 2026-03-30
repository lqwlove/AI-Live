import { AnnounceScriptsConfig } from "@/components/settings/AnnounceScriptsConfig";

export function AnnounceScriptsPage() {
  return (
    <div className="tk-main-canvas">
      <header
        className="flex shrink-0 items-center"
        style={{ minHeight: "var(--ds-settings-header-h)", height: "var(--ds-settings-header-h)" }}
      >
        <h1 className="text-2xl leading-none font-bold tracking-tight text-[var(--font-primary)]">播报文案</h1>
      </header>

      <div className="min-h-0 flex-1">
        <AnnounceScriptsConfig />
      </div>
    </div>
  );
}
