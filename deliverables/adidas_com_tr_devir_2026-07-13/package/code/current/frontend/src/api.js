import axios from "axios";

export function resolveBackendUrl({ saved, host, protocol, configured }) {
  if (saved) return saved;
  if (configured) {
    try {
      const configuredHost = new URL(configured).hostname;
      const configuredIsLoopback = ["localhost", "127.0.0.1"].includes(configuredHost);
      if (!configuredIsLoopback || configuredHost === host) return configured;
    } catch (_error) {
      // Invalid build-time configuration falls back to the page host below.
    }
  }
  if (host) {
    const backendProtocol = protocol === "https:" ? "https:" : "http:";
    return `${backendProtocol}//${host}:8000`;
  }
  return configured || "http://localhost:8000";
}

function defaultBackendUrl() {
  if (typeof window === "undefined") return "http://localhost:8000";

  return resolveBackendUrl({
    saved: window.localStorage.getItem("shoehunter_backend_url"),
    host: window.location.hostname,
    protocol: window.location.protocol,
    configured: process.env.REACT_APP_BACKEND_URL,
  });
}

export const BACKEND_URL = defaultBackendUrl();
export const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API, withCredentials: true });

function readCookie(name) {
  if (typeof document === "undefined") return "";
  const prefix = `${name}=`;
  const row = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  return row ? decodeURIComponent(row.slice(prefix.length)) : "";
}

api.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (!["get", "head", "options"].includes(method)) {
    const csrf = readCookie("shoehunter_csrf");
    if (csrf) config.headers["X-CSRF-Token"] = csrf;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if ([401, 428].includes(error.response?.status)) {
      window.dispatchEvent(new Event("shoehunter-auth-required"));
    }
    return Promise.reject(error);
  }
);

export default api;

export function fmtPrice(v) {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " TL";
}

export function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}
