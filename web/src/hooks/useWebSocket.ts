import { useEffect, useRef } from "react";
import type { WSEvent } from "@/types";
import { useSessionStore } from "@/stores/sessionStore";
import { api } from "@/lib/api";
import { DEBUG_WS } from "@/lib/debugFlags";

function wsLog(...args: unknown[]) {
  if (DEBUG_WS) console.info("[tk-live:ws]", ...args);
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Fetch initial status on mount so we pick up any running session
    api.getStatus().then((s) => {
      const running = s.running as boolean;
      if (running) {
        const st = useSessionStore.getState();
        st.setStatus("running");
        st.setPlatform(s.platform as string);
        st.updateStats({
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
      wsLog("connecting", url);
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => wsLog("open");

      ws.onmessage = (e) => {
        const event: WSEvent = JSON.parse(e.data);
        if (DEBUG_WS && event.type === "chat_received") {
          const d = event.data as Record<string, unknown>;
          wsLog("onmessage chat_received", {
            top_ts: event.timestamp,
            content_preview:
              typeof d.content === "string" ? `${d.content.slice(0, 48)}…` : "",
          });
        }
        handleEvent(event);
      };

      ws.onclose = () => {
        wsLog("close, reconnect in 3s");
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        wsLog("error");
        ws.close();
      };
    }

    function handleEvent(event: WSEvent) {
      const { type, data, timestamp } = event;
      const store = useSessionStore.getState();

      switch (type) {
        case "session_started":
          store.setStatus("running");
          store.setPlatform(data.platform as string);
          break;

        case "session_stopped":
          store.reset();
          break;

        case "chat_received": {
          const msgUid = typeof data.msg_uid === "string" ? data.msg_uid : undefined;
          store.addChat({
            user: data.user as string,
            content: data.content as string,
            user_id: String(data.user_id ?? ""),
            timestamp,
            ...(msgUid ? { msg_uid: msgUid } : {}),
          });
          break;
        }

        case "ai_reply_start":
          // 不在列表里增加「生成中」卡片，仅在 ai_reply_done 时插入一条
          break;

        case "ai_reply_done": {
          if (DEBUG_WS) {
            const r = typeof data.reply === "string" ? data.reply : "";
            wsLog("ai_reply_done", { reply_preview: `${r.slice(0, 56)}…` });
          }
          store.addAIResponse({
            user: data.user as string,
            content: data.content as string,
            reply: data.reply as string,
            lang: data.lang as string,
            timestamp,
            status: "done",
          });
          break;
        }

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
          console.error("会话错误:", data.error);
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
