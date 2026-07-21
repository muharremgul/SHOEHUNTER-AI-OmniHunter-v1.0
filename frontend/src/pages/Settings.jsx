import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  CircleNotch,
  Clock,
  Database,
  DownloadSimple,
  PaperPlaneTilt,
  TelegramLogo,
} from "@phosphor-icons/react";
import api from "../api";

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [stores, setStores] = useState([]);
  const [busy, setBusy] = useState(false);
  const [testBusy, setTestBusy] = useState(false);

  useEffect(() => {
    api.get("/settings").then((response) => setSettings({
      ...response.data,
      telegram: { ...response.data.telegram, bot_token: "" },
    }));
    api.get("/stores").then((response) => setStores(response.data));
  }, []);

  if (!settings) return <div className="text-zinc-500 font-mono text-sm">Yükleniyor...</div>;

  const saveTelegram = async () => {
    setBusy(true);
    try {
      const { data } = await api.put("/settings/telegram", settings.telegram);
      setSettings({ ...data, telegram: { ...data.telegram, bot_token: "" } });
      toast.success("Telegram ayarları kaydedildi");
    } finally {
      setBusy(false);
    }
  };

  const saveScheduler = async () => {
    setBusy(true);
    try {
      const { data } = await api.put("/settings/scheduler", {
        enabled: settings.scheduler.enabled,
        interval_minutes: parseInt(settings.scheduler.interval_minutes, 10) || 30,
        discovery_interval_hours: parseInt(settings.scheduler.discovery_interval_hours, 10) || 6,
      });
      setSettings({ ...data, telegram: { ...data.telegram, bot_token: "" } });
      toast.success(data.scheduler.enabled
        ? `Otomatik kontrol aktif: her ${data.scheduler.interval_minutes} dakika`
        : "Otomatik kontrol kapatıldı");
    } finally {
      setBusy(false);
    }
  };

  const exportFile = async (path, filename) => {
    const response = await api.get(path, { responseType: "blob" });
    const href = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(href);
  };

  const requestBackup = async () => {
    const { data } = await api.post("/backups");
    toast.success(`Yedekleme sıraya alındı: ${data.job_id.slice(0, 8)}`);
  };

  const testTelegram = async () => {
    setTestBusy(true);
    try {
      const { data } = await api.post("/telegram/test");
      if (data.sent) toast.success("Test mesajı Telegram'a gönderildi");
      else toast.error(`Gönderilemedi: ${data.error || data.reason}`);
    } finally {
      setTestBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl" data-testid="settings-page">
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Yapılandırma</div>
        <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">Ayarlar</h1>
      </div>

      <div className="card p-6">
        <h3 className="font-heading font-semibold text-lg mb-4 flex items-center gap-2">
          <TelegramLogo size={20} weight="duotone" className="text-primary" /> Telegram Bildirimleri
        </h3>
        <div className="space-y-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              data-testid="telegram-enabled-checkbox"
              type="checkbox"
              className="accent-[#CCFF00] w-4 h-4"
              checked={settings.telegram.enabled}
              onChange={(event) => setSettings({
                ...settings,
                telegram: { ...settings.telegram, enabled: event.target.checked },
              })}
            />
            <span className="text-sm">Telegram bildirimleri aktif</span>
          </label>
          <div>
            <label className="text-xs text-zinc-500 uppercase tracking-wider">Bot Token</label>
            <input
              data-testid="telegram-token-input"
              className="input-dark mt-1 font-mono"
              type="password"
              value={settings.telegram.bot_token || ""}
              placeholder={settings.telegram.configured
                ? "Yeni token girilmezse mevcut token korunur"
                : "BotFather tokeni"}
              onChange={(event) => setSettings({
                ...settings,
                telegram: { ...settings.telegram, bot_token: event.target.value },
              })}
            />
          </div>
          {settings.telegram.configured && (
            <div className="text-xs text-primary font-mono">Token güvenli kasada yapılandırılmış</div>
          )}
          <div>
            <label className="text-xs text-zinc-500 uppercase tracking-wider">Chat ID</label>
            <input
              data-testid="telegram-chatid-input"
              className="input-dark mt-1 font-mono"
              value={settings.telegram.chat_id}
              onChange={(event) => setSettings({
                ...settings,
                telegram: { ...settings.telegram, chat_id: event.target.value },
              })}
            />
          </div>
          <div className="flex gap-3">
            <button data-testid="telegram-save-button" className="btn-primary" onClick={saveTelegram} disabled={busy}>
              Kaydet
            </button>
            <button
              data-testid="telegram-test-button"
              className="btn-secondary flex items-center gap-2"
              onClick={testTelegram}
              disabled={testBusy}
            >
              {testBusy ? <CircleNotch size={16} className="animate-spin" /> : <PaperPlaneTilt size={16} />}
              Test Mesajı Gönder
            </button>
          </div>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="font-heading font-semibold text-lg mb-4 flex items-center gap-2">
          <Clock size={20} weight="duotone" className="text-primary" /> Otomatik Kontrol
        </h3>
        <div className="space-y-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              data-testid="scheduler-enabled-checkbox"
              type="checkbox"
              className="accent-[#CCFF00] w-4 h-4"
              checked={settings.scheduler.enabled}
              onChange={(event) => setSettings({
                ...settings,
                scheduler: { ...settings.scheduler, enabled: event.target.checked },
              })}
            />
            <span className="text-sm">Otomatik kontrol aktif</span>
          </label>
          <div>
            <label className="text-xs text-zinc-500 uppercase tracking-wider">Kontrol aralığı (dakika)</label>
            <input
              data-testid="scheduler-interval-input"
              className="input-dark mt-1 max-w-[160px] font-mono"
              type="number"
              min="1"
              value={settings.scheduler.interval_minutes}
              onChange={(event) => setSettings({
                ...settings,
                scheduler: { ...settings.scheduler, interval_minutes: event.target.value },
              })}
            />
            <div className="text-xs text-zinc-500 mt-1.5">
              Gerçek kullanımda 30 dakika veya üzeri önerilir. Çok sık kontrol, mağazaların geçici olarak erişimi sınırlamasına yol açabilir.
            </div>
          </div>
          <div>
            <label className="text-xs text-zinc-500 uppercase tracking-wider">Yeni ilan keşfi (saat)</label>
            <input
              className="input-dark mt-1 max-w-[160px] font-mono"
              type="number"
              min="6"
              value={settings.scheduler.discovery_interval_hours || 6}
              onChange={(event) => setSettings({
                ...settings,
                scheduler: { ...settings.scheduler, discovery_interval_hours: event.target.value },
              })}
            />
          </div>
          <button data-testid="scheduler-save-button" className="btn-primary" onClick={saveScheduler} disabled={busy}>
            Kaydet
          </button>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="font-heading font-semibold text-lg mb-4 flex items-center gap-2">
          <Database size={20} weight="duotone" className="text-primary" /> Yedek ve Dışa Aktarma
        </h3>
        <div className="flex flex-wrap gap-3">
          <button className="btn-primary flex items-center gap-2" onClick={requestBackup}>
            <Database size={16} /> JSON Yedeği Oluştur
          </button>
          <button className="btn-secondary flex items-center gap-2" onClick={() => exportFile("/export/products.json", "shoehunter-products.json")}>
            <DownloadSimple size={16} /> Ürünleri Dışa Aktar
          </button>
          <button className="btn-secondary flex items-center gap-2" onClick={() => exportFile("/export/price-history.csv", "shoehunter-price-history.csv")}>
            <DownloadSimple size={16} /> Fiyat Geçmişi CSV
          </button>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="font-heading font-semibold text-lg mb-4">Desteklenen Mağazalar ({stores.length})</h3>
        <div className="flex flex-wrap gap-2">
          {stores.map((store) => (
            <span key={store.slug} className="text-xs font-mono px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800">
              {store.name}
              {store.searchable && <span className="text-primary ml-1.5">• arama</span>}
              {store.health?.circuit_state === "open" && <span className="text-red-400 ml-1.5">• beklemede</span>}
              {store.health?.success_rate_24h != null && (
                <span className="text-zinc-500 ml-1.5">
                  • 24s %{Math.round(store.health.success_rate_24h * 100)}
                </span>
              )}
            </span>
          ))}
        </div>
        <div className="text-xs text-zinc-500 mt-3">
          Yalnızca izin verilen mağaza alan adları işlenir. Bir mağaza veri vermediğinde sistem yanlış stok alarmı üretmez; sonucu belirsiz olarak kaydeder ve mağaza sağlığında gösterir.
        </div>
      </div>
    </div>
  );
}
