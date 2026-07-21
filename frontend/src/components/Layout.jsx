import React, { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  SquaresFour,
  Sneaker,
  BellRinging,
  MagnifyingGlass,
  ChatCircleDots,
  GearSix,
  Terminal,
  UserCircle,
  Lightning,
  CircleNotch,
  List,
  Crosshair,
  SignOut,
} from "@phosphor-icons/react";
import api from "../api";
import { useAuth } from "./AuthGate";

const NAV = [
  { to: "/", label: "Panel", icon: SquaresFour },
  { to: "/urunler", label: "Ürünler", icon: Sneaker },
  { to: "/radar", label: "Ürün Radarı", icon: Crosshair },
  { to: "/uyarilar", label: "Uyarılar", icon: BellRinging },
  { to: "/ai-arama", label: "AI Arama", icon: MagnifyingGlass },
  { to: "/ai-koc", label: "AI Koç", icon: ChatCircleDots },
  { to: "/ayarlar", label: "Ayarlar", icon: GearSix },
  { to: "/debug", label: "Debug Lab", icon: Terminal },
  { to: "/profil", label: "Profil", icon: UserCircle },
];

export default function Layout({ children }) {
  const [checking, setChecking] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [version, setVersion] = useState("0.6.0");
  const navigate = useNavigate();
  const { logout } = useAuth();

  useEffect(() => {
    api.get("/").then(({ data }) => data.version && setVersion(data.version)).catch(() => {});
  }, []);

  const runBatchCheck = async () => {
    setChecking(true);
    toast.info("Toplu kontrol başlatıldı...");
    try {
      const { data } = await api.post("/check/all");
      toast.success(`Kontrol sıraya alındı: ${data.job_id.slice(0, 8)}`);
      navigate("/");
    } catch (e) {
      toast.error("Toplu kontrol başarısız: " + (e.response?.data?.detail || e.message));
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex">
      <aside className="hidden md:flex w-60 shrink-0 border-r border-zinc-800 bg-[#0c0c0f] flex-col fixed h-screen z-20">
        <div className="p-5 border-b border-zinc-800">
          <div className="font-heading font-800 text-lg tracking-tighter font-bold">
            <span className="text-primary">SHOE</span>HUNTER
          </div>
          <div className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 mt-0.5 font-mono">
            AI · OmniHunter v{version}
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              data-testid={`nav-${label.toLowerCase().replace(/\s|ü/g, (c) => (c === "ü" ? "u" : "-"))}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors duration-200 ${
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/20"
                    : "text-zinc-400 hover:text-white hover:bg-zinc-900 border border-transparent"
                }`
              }
            >
              <Icon size={18} weight="duotone" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-zinc-800">
          <button
            data-testid="batch-check-button"
            onClick={runBatchCheck}
            disabled={checking}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {checking ? (
              <CircleNotch size={16} className="animate-spin" />
            ) : (
              <Lightning size={16} weight="fill" />
            )}
            {checking ? "Kontrol ediliyor..." : "Tüm Linkleri Kontrol Et"}
          </button>
          <button
            type="button"
            onClick={logout}
            className="mt-2 h-9 w-full flex items-center justify-center gap-2 text-xs text-zinc-500 hover:text-white"
            title="Oturumu kapat"
          >
            <SignOut size={15} /> Çıkış
          </button>
        </div>
      </aside>
      <header className="md:hidden fixed top-0 inset-x-0 z-30 h-14 border-b border-zinc-800 bg-[#0c0c0f]/95 backdrop-blur flex items-center justify-between px-4">
        <button
          type="button"
          onClick={() => setMobileOpen((v) => !v)}
          className="h-10 w-10 rounded-lg border border-zinc-800 flex items-center justify-center text-zinc-200"
          aria-label="Menüyü aç"
        >
          <List size={22} />
        </button>
        <div className="text-center">
          <div className="font-heading font-bold text-sm">
            <span className="text-primary">SHOE</span>HUNTER
          </div>
          <div className="text-[9px] uppercase tracking-[0.18em] text-zinc-500">OmniHunter</div>
        </div>
        <button
          type="button"
          onClick={runBatchCheck}
          disabled={checking}
          className="h-10 w-10 rounded-lg bg-primary text-black flex items-center justify-center disabled:opacity-50"
          aria-label="Tüm linkleri kontrol et"
        >
          {checking ? <CircleNotch size={18} className="animate-spin" /> : <Lightning size={18} weight="fill" />}
        </button>
      </header>

      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/70" onClick={() => setMobileOpen(false)}>
          <nav
            className="absolute left-3 right-3 top-16 rounded-lg border border-zinc-800 bg-[#0c0c0f] p-3 grid grid-cols-2 gap-2"
            onClick={(e) => e.stopPropagation()}
          >
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3 py-3 rounded-lg text-sm border ${
                    isActive
                      ? "bg-primary/10 text-primary border-primary/20"
                      : "text-zinc-300 bg-zinc-950 border-zinc-800"
                  }`
                }
              >
                <Icon size={18} weight="duotone" />
                {label}
              </NavLink>
            ))}
            <button
              type="button"
              onClick={logout}
              className="flex items-center gap-2 px-3 py-3 rounded-lg text-sm border text-zinc-300 bg-zinc-950 border-zinc-800"
            >
              <SignOut size={18} /> Çıkış
            </button>
          </nav>
        </div>
      )}

      <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 border-t border-zinc-800 bg-[#0c0c0f]/95 backdrop-blur grid grid-cols-5 px-2 pb-[max(env(safe-area-inset-bottom),8px)] pt-2">
        {NAV.slice(0, 5).map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `h-12 rounded-lg flex flex-col items-center justify-center gap-0.5 text-[10px] ${
                isActive ? "text-primary bg-primary/10" : "text-zinc-400"
              }`
            }
          >
            <Icon size={19} weight="duotone" />
            <span className="truncate max-w-full px-1">{label}</span>
          </NavLink>
        ))}
      </nav>

      <main className="flex-1 md:ml-60 pt-20 md:pt-6 lg:pt-8 px-4 md:px-6 lg:px-8 pb-24 md:pb-8 max-w-[1600px] min-w-0">
        {children}
      </main>
    </div>
  );
}
