import React, { useState } from "react";
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
} from "@phosphor-icons/react";
import api from "../api";

const NAV = [
  { to: "/", label: "Panel", icon: SquaresFour },
  { to: "/urunler", label: "Ürünler", icon: Sneaker },
  { to: "/uyarilar", label: "Uyarılar", icon: BellRinging },
  { to: "/ai-arama", label: "AI Arama", icon: MagnifyingGlass },
  { to: "/ai-koc", label: "AI Koç", icon: ChatCircleDots },
  { to: "/ayarlar", label: "Ayarlar", icon: GearSix },
  { to: "/debug", label: "Debug Lab", icon: Terminal },
  { to: "/profil", label: "Profil", icon: UserCircle },
];

export default function Layout({ children }) {
  const [checking, setChecking] = useState(false);
  const navigate = useNavigate();

  const runBatchCheck = async () => {
    setChecking(true);
    toast.info("Toplu kontrol başlatıldı...");
    try {
      const { data } = await api.post("/check/all");
      const r = data.run;
      toast.success(
        `Kontrol tamamlandı: ${r.success}/${r.total} başarılı, ${r.alerts_created} yeni uyarı`
      );
      navigate("/");
    } catch (e) {
      toast.error("Toplu kontrol başarısız: " + (e.response?.data?.detail || e.message));
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex">
      <aside className="w-60 shrink-0 border-r border-zinc-800 bg-[#0c0c0f] flex flex-col fixed h-screen z-20">
        <div className="p-5 border-b border-zinc-800">
          <div className="font-heading font-800 text-lg tracking-tighter font-bold">
            <span className="text-primary">SHOE</span>HUNTER
          </div>
          <div className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 mt-0.5 font-mono">
            AI · OmniHunter v1.0
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
        </div>
      </aside>
      <main className="flex-1 ml-60 p-6 lg:p-8 max-w-[1600px]">{children}</main>
    </div>
  );
}
