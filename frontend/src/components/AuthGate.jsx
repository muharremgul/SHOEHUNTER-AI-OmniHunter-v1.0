import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { CircleNotch, LockKey, ShieldCheck } from "@phosphor-icons/react";
import { toast } from "sonner";
import api from "../api";


const AuthContext = createContext({ user: null, logout: async () => {} });

export function useAuth() {
  return useContext(AuthContext);
}

export default function AuthGate({ children }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ username: "admin", password: "", setup_token: "" });

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/status");
      setStatus(data);
    } catch (error) {
      setStatus({ setup_required: false, authenticated: false, backend_error: true });
    }
  }, []);

  useEffect(() => {
    refresh();
    const handler = () => refresh();
    window.addEventListener("shoehunter-auth-required", handler);
    return () => window.removeEventListener("shoehunter-auth-required", handler);
  }, [refresh]);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const path = status.setup_required ? "/auth/setup" : "/auth/login";
      await api.post(path, form);
      setForm((current) => ({ ...current, password: "", setup_token: "" }));
      await refresh();
      toast.success(status.setup_required ? "Yönetici hesabı oluşturuldu" : "Giriş yapıldı");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Giriş başarısız");
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setStatus((current) => ({ ...(current || {}), authenticated: false }));
    }
  };

  if (!status) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-zinc-500">
        <CircleNotch size={24} className="animate-spin" />
      </div>
    );
  }

  if (!status.authenticated) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <form onSubmit={submit} className="w-full max-w-sm border border-zinc-800 bg-[#0c0c0f] p-6 rounded-lg space-y-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 border border-primary/30 bg-primary/10 text-primary rounded-lg flex items-center justify-center">
              {status.setup_required ? <ShieldCheck size={22} /> : <LockKey size={22} />}
            </div>
            <div>
              <div className="font-heading font-bold text-lg">
                <span className="text-primary">SHOE</span>HUNTER
              </div>
              <div className="text-xs text-zinc-500">
                {status.setup_required ? "İlk yönetici kurulumu" : "Yönetici girişi"}
              </div>
            </div>
          </div>

          {status.backend_error && (
            <div className="text-sm text-red-300 border border-red-500/20 bg-red-500/10 rounded p-3">
              Backend bağlantısı kurulamadı.
            </div>
          )}

          <div>
            <label className="text-xs text-zinc-500 uppercase tracking-wider">Kullanıcı adı</label>
            <input
              className="input-dark mt-1"
              value={form.username}
              autoComplete="username"
              onChange={(event) => setForm({ ...form, username: event.target.value })}
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500 uppercase tracking-wider">Parola</label>
            <input
              className="input-dark mt-1"
              type="password"
              value={form.password}
              autoComplete={status.setup_required ? "new-password" : "current-password"}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
            />
            {status.setup_required && (
              <div className="text-xs text-zinc-500 mt-1.5">En az 12 karakter, büyük-küçük harf ve rakam.</div>
            )}
          </div>
          {status.setup_required && (
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Kurulum anahtarı</label>
              <input
                className="input-dark mt-1"
                type="password"
                value={form.setup_token}
                placeholder="Yalnızca ayarlandıysa gerekli"
                onChange={(event) => setForm({ ...form, setup_token: event.target.value })}
              />
            </div>
          )}
          <button className="btn-primary w-full flex items-center justify-center gap-2" disabled={busy || !form.password}>
            {busy && <CircleNotch size={16} className="animate-spin" />}
            {status.setup_required ? "Hesabı Oluştur" : "Giriş Yap"}
          </button>
        </form>
      </div>
    );
  }

  return <AuthContext.Provider value={{ user: status.username, logout }}>{children}</AuthContext.Provider>;
}
