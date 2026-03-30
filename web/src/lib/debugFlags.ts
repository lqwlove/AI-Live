/** 浏览器控制台过滤：tk-live */
export const DEBUG_WS =
  import.meta.env.DEV ||
  (typeof localStorage !== "undefined" && localStorage.getItem("tk_live_debug_ws") === "1");
