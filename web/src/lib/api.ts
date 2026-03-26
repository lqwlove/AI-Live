const BASE = "";

async function request<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  getConfig: () => request<Record<string, unknown>>("/api/config"),

  updateConfig: (data: Record<string, unknown>) =>
    request<{ ok: boolean }>("/api/config", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  validatePlatform: (platform: string) =>
    request<{ configured: boolean; platform: string }>("/api/config/validate", {
      method: "POST",
      body: JSON.stringify({ platform }),
    }),

  startSession: (platform: string, opts: Record<string, unknown> = {}) =>
    request<Record<string, unknown>>("/api/session/start", {
      method: "POST",
      body: JSON.stringify({ platform, ...opts }),
    }),

  stopSession: () =>
    request<Record<string, unknown>>("/api/session/stop", { method: "POST" }),

  getStatus: () => request<Record<string, unknown>>("/api/session/status"),
};
