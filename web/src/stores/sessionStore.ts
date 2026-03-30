import { create } from "zustand";
import type { AIResponse, ChatMessage, Stats } from "@/types";
import { DEBUG_WS } from "@/lib/debugFlags";

function storeLog(...args: unknown[]) {
  if (DEBUG_WS) console.info("[tk-live:store]", ...args);
}

interface SessionState {
  status: "idle" | "starting" | "running" | "stopping";
  platform: string | null;
  stats: Stats;
  chatMessages: ChatMessage[];
  aiResponses: AIResponse[];

  setStatus: (s: SessionState["status"]) => void;
  setPlatform: (p: string | null) => void;
  addChat: (msg: ChatMessage) => void;
  addAIResponse: (resp: AIResponse) => void;
  updateAIResponseStatus: (user: string, status: AIResponse["status"]) => void;
  updateStats: (s: Partial<Stats>) => void;
  reset: () => void;
}

const INITIAL_STATS: Stats = { messages: 0, ai_replies: 0, audio_played: 0, uptime: 0 };
const MAX_MESSAGES = 200;

export const useSessionStore = create<SessionState>((set) => ({
  status: "idle",
  platform: null,
  stats: { ...INITIAL_STATS },
  chatMessages: [],
  aiResponses: [],

  setStatus: (s) => set({ status: s }),
  setPlatform: (p) => set({ platform: p }),

  addChat: (msg) =>
    set((state) => {
      storeLog("addChat", { len: state.chatMessages.length, preview: msg.content.slice(0, 40) });
      return {
        chatMessages: [...state.chatMessages.slice(-(MAX_MESSAGES - 1)), msg],
      };
    }),

  addAIResponse: (resp) =>
    set((state) => ({
      aiResponses: [...state.aiResponses.slice(-(MAX_MESSAGES - 1)), resp],
    })),

  updateAIResponseStatus: (user, status) =>
    set((state) => {
      const idx = state.aiResponses.findLastIndex((r) => r.user === user);
      if (idx === -1) return {};
      const updated = [...state.aiResponses];
      updated[idx] = { ...updated[idx], status };
      return { aiResponses: updated };
    }),

  updateStats: (s) =>
    set((state) => ({ stats: { ...state.stats, ...s } })),

  reset: () =>
    set({
      status: "idle",
      platform: null,
      stats: { ...INITIAL_STATS },
      chatMessages: [],
      aiResponses: [],
    }),
}));
