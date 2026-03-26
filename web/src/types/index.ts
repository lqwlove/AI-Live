export interface ChatMessage {
  user: string;
  content: string;
  user_id?: string;
  timestamp: number;
}

export interface AIResponse {
  user: string;
  content: string;
  reply: string;
  lang: string;
  timestamp: number;
  status: "generating" | "speaking" | "done";
}

export interface Stats {
  messages: number;
  ai_replies: number;
  audio_played: number;
  uptime: number;
}

export interface SessionStatus {
  running: boolean;
  platform: string | null;
  messages: number;
  ai_replies: number;
  audio_played: number;
  uptime: number;
}

export interface WSEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export type Platform = "youtube" | "douyin" | "tiktok";
