import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { PaperPlaneTilt, CircleNotch, Clock, TelegramLogo } from "@phosphor-icons/react";
import api, { fmtDate } from "../api";

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [stores, setStores] = useState([]);
  const [busy, setBusy] = useState(false);
  const [testBusy, setTestBusy] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => setSettings(r.data));
    api.get("/stores").then((r) => setStores(r.data));
  }, []);

  if (!settings) return <div className="text-zinc-500 font-mono text-sm">Yükleniyor...</div>;

  const saveTelegram = async () => {
    setBusy(true);
    try {
      const { data } = await api.put("/settings/telegram", settings.telegram);
      setSettings(data);
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
        interval_minutes: parseInt(settings.scheduler.interval_minutes) || 30,
      });
      setSettings(data);
      toast.success(data.scheduler.enabled ? `Scheduler aktif: her ${data.scheduler.interval_minutes} dk` : "Scheduler kapatıldı");
    } finally {
      setBusy(false);
    }
  };

  const testTelegram = async () => {
    setTestBusy(true);
    try {
      const { data } = await api.post("/telegram/test");
      if (data.sent) toast.success("Test mesajı Telegram'a gönderildi! Kontrol edin.");
      else toast.error("Gönderilemedi: " + (data.error || data.reason));
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
              onChange={(e) => setSettings({ ...settings, telegram: { ...settings.telegram, enabled: e.target.checked } })}
            />
            <span className="text-sm">Telegram bildirimleri aktif</span>
          </label>
          <div>
            <label className="text-xs text-zinc-500 uppercase tracking-wider">Bot Token</label>
            <input
              data-testid="telegram-token-input"
              className="input-dark mt-1 font-mono"
              type="password"
              value={settings.telegram.bot_token}
              onChange={(e) => setSettings({ ...settings, telegram: { ...settings.telegram, bot_token: e.target.value } })}
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500 uppercase tracking-wider">Chat ID</label>
            <input
              data-testid="telegram-chatid-input"
              className="input-dark mt-1 font-mono"
              value={settings.telegram.chat_id}
              onChange={(e) => setSettings({ ...settings, telegram: { ...settings.telegram, chat_id: e.target.value } })}
            />
          </div>
          <div className="flex gap-3">
            <button data-testid="telegram-save-button" className="btn-primary" onClick={saveTelegram} disabled={busy}>Kaydet</button>
            <button data-testid="telegram-test-button" className="btn-secondary flex items-center gap-2" onClick={testTelegram} disabled={testBusy}>
              {testBusy ? <CircleNotch size={16} className="animate-spin" /> : <PaperPlaneTilt size={16} />} Test Mesajı Gönder
            </button>
          </div>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="font-heading font-semibold text-lg mb-4 flex items-center gap-2">
          <Clock size={20} weight="duotone" className="text-primary" /> Otomatik Kontrol (Scheduler)
        </h3>
        <div className="space-y-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              data-testid="scheduler-enabled-checkbox"
              type="checkbox"
              className="accent-[#CCFF00] w-4 h-4"
              checked={settings.scheduler.enabled}
              onChange={(e) => setSettings({ ...settings, scheduler: { ...settings.scheduler, enabled: e.target.checked } })}
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
              onChange={(e) => setSettings({ ...settings, scheduler: { ...settings.scheduler, interval_minutes: e.target.value } })}
            />
            <div className="text-xs text-zinc-500 mt-1.5">
              Gerçek kullanımda 30 dk veya üzeri önerilir. Test için 1 dk kullanılabilir. Aşırı sık kontrol siteler tarafından engellenmenize yol açabilir.
            </div>
          </div>
          <button data-testid="scheduler-save-button" className="btn-primary" onClick={saveScheduler} disabled={busy}>Kaydet</button>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="font-heading font-semibold text-lg mb-4">Desteklenen Mağazalar ({stores.length})</h3>
        <div className="flex flex-wrap gap-2">
          {stores.map((s) => (
            <span key={s.slug} className="text-xs font-mono px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800">
              {s.name}
              {s.searchable && <span className="text-primary ml-1.5">• arama</span>}
            </span>
          ))}
        </div>
        <div className="text-xs text-zinc-500 mt-3">
          Tanınmayan mağaza linkleri için genel JSON-LD motoru devreye girer. Bazı siteler bot koruması nedeniyle veri vermeyebilir — sistem bu durumda sahte alarm üretmez, belirsizliği açıkça gösterir.
        </div>
      </div>
    </div>
  );
}
