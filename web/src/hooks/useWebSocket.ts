import { useEffect, useRef } from "react";
import type { WSEvent } from "@/types";
import { useSessionStore } from "@/stores/sessionStore";
import { api } from "@/lib/api";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const store = useSessionStore();

  useEffect(() => {
    // Fetch initial status on mount so we pick up any running session
    api.getStatus().then((s) => {
      const running = s.running as boolean;
      if (running) {
        store.setStatus("running");
        store.setPlatform(s.platform as string);
        store.updateStats({
          messages: s.messages as number,
          ai_replies: s.ai_replies as number,
          audio_played: s.audio_played as number,
          uptime: s.uptime as number,
        });
      }
    }).catch(() => {});

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws`;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        const event: WSEvent = JSON.parse(e.data);
        handleEvent(event);
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    }

    function handleEvent(event: WSEvent) {
      const { type, data, timestamp } = event;

      switch (type) {
        case "session_started":
          store.setStatus("running");
          store.setPlatform(data.platform as string);
          break;

        case "session_stopped":
          store.reset();
          break;

        case "chat_received":
          store.addChat({
            user: data.user as string,
            content: data.content as string,
            user_id: data.user_id as string,
            timestamp,
          });
          break;

        case "ai_reply_start":
          store.addAIResponse({
            user: data.user as string,
            content: data.content as string,
            reply: "",
            lang: "",
            timestamp,
            status: "generating",
          });
          break;

        case "ai_reply_done":
          store.addAIResponse({
            user: data.user as string,
            content: data.content as string,
            reply: data.reply as string,
            lang: data.lang as string,
            timestamp,
            status: "done",
          });
          break;

        case "audio_playing":
          store.updateAIResponseStatus(data.user as string, "speaking");
          break;

        case "audio_done":
          store.updateAIResponseStatus(data.user as string, "done");
          break;

        case "stats_update":
          store.updateStats({
            messages: data.messages as number,
            ai_replies: data.ai_replies as number,
            audio_played: data.audio_played as number,
            uptime: data.uptime as number,
          });
          break;

        case "session_error":
          console.error("Session error:", data.error);
          break;
      }
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
