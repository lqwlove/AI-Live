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

export interface Product {
  id: string;
  name: string;
  price: number;
  original_price?: number | null;
  keywords: string[];
  description: string;
  selling_points: string[];
  active: boolean;
}

export interface AnnounceItem {
  id: string;
  title: string;
  text: string;
  enabled: boolean;
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

  /** 扫描 bgm 目录下的音频（mp3/wav/ogg/flac） */
  listBgmFiles: () =>
    request<{ files: string[]; dir: string }>("/api/bgm/files"),

  getBgmStatus: () =>
    request<{
      playing: boolean;
      file: string | null;
      volume: number;
      duck_volume: number;
    }>("/api/bgm"),

  playBgm: (file: string) =>
    request<{
      playing: boolean;
      file: string | null;
      volume: number;
      duck_volume: number;
    }>("/api/bgm/play", {
      method: "POST",
      body: JSON.stringify({ file }),
    }),

  stopBgm: () =>
    request<{ playing: boolean }>("/api/bgm/stop", { method: "POST" }),

  setBgmVolume: (volume: number) =>
    request<{
      playing: boolean;
      file: string | null;
      volume: number;
      duck_volume: number;
    }>("/api/bgm/volume", {
      method: "PUT",
      body: JSON.stringify({ volume }),
    }),

  stopSession: () =>
    request<Record<string, unknown>>("/api/session/stop", { method: "POST" }),

  getStatus: () => request<Record<string, unknown>>("/api/session/status"),

  getProducts: () => request<Product[]>("/api/products"),

  addProduct: (data: Omit<Product, "id">) =>
    request<Product>("/api/products", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateProduct: (id: string, data: Partial<Product>) =>
    request<Product>(`/api/products/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProduct: (id: string) =>
    request<{ ok: boolean }>(`/api/products/${id}`, { method: "DELETE" }),

  testMatch: (text: string) =>
    request<{ matched: Product[]; count: number }>("/api/products/test-match", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  getAnnounceItems: () => request<AnnounceItem[]>("/api/announce/items"),

  putAnnounceItems: (items: AnnounceItem[]) =>
    request<AnnounceItem[]>("/api/announce/items", {
      method: "PUT",
      body: JSON.stringify({ items }),
    }),

  getAnnounceRuntime: () =>
    request<{
      enabled: boolean;
      active_ids: string[];
      interval_seconds: number;
      voice_volume: number;
    }>("/api/announce/runtime"),

  putAnnounceRuntime: (body: {
    enabled?: boolean;
    active_ids?: string[];
    interval_seconds?: number;
    voice_volume?: number;
  }) =>
    request<{
      enabled: boolean;
      active_ids: string[];
      interval_seconds: number;
      voice_volume: number;
    }>("/api/announce/runtime", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};
