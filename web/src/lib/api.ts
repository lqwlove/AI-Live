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
};
