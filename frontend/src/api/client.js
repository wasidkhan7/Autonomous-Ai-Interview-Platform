import axios from "axios";

// Vite only exposes env vars prefixed with VITE_, and inlines them at BUILD
// time - so Vercel needs this set before it builds, not at runtime.
// Trailing slash stripped so `${API_BASE_URL}/voice/...` never doubles up.
export const API_BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

// http -> ws, https -> wss. Browsers refuse ws:// from an https:// page.
export const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});
// Attach the mentor key to every outgoing request. Candidate endpoints ignore
// it; mentor endpoints require it. Doing it here means no page has to remember.
apiClient.interceptors.request.use((config) => {
  const key = localStorage.getItem("mentorKey");
  if (key) config.headers["X-Mentor-Key"] = key;
  return config;
});

export default apiClient;
