import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { BellRinging, Check, Trash, PaperPlaneTilt } from "@phosphor-icons/react";
import api, { fmtPrice, fmtDate } from "../api";

const ALERT_TYPE_LABELS = {
  new_listing: "Yeni ürün",
  new_variant: "Yeni renk / varyant",
  restock: "Yeniden stokta",
  size_restock: "Beden yeniden stokta",
  discounted_restock: "Düşük fiyattan geri geldi",
  single_variant_restock: "Tek renk / tek beden geri geldi",
  last_size_deal: "Son beden fırsatı",
  tracked_size_price_drop: "Fiyat düştü, bedenin mevcut",
  price_drop: "Fiyat düştü",
  cart_price: "Sepette fiyat",
  cart_price_continues: "Sepette fiyat devam ediyor",
  critical_stock: "Stok kritik",
  period_low: "Dönem dibi",
  target_price: "Hedef fiyat",
  near_target: "Hedefe yakın",
};

export function alertSizeText(alert) {
  const sizes = alert?.sizes?.length ? alert.sizes : (alert?.size ? [alert.size] : []);
  return sizes.length ? [...new Set(sizes)].join(", ") : "Doğrulanamadı";
}

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () =>
    api.get("/alerts").then((r) => {
      setAlerts(r.data);
      setLoading(false);
    });

  useEffect(() => {
    load();
  }, []);

  const markRead = async (id) => {
    await api.patch(`/alerts/${id}/read`);
    load();
  };

  const markAllRead = async () => {
    await api.post("/alerts/read-all");
    toast.success("Tümü okundu olarak işaretlendi");
    load();
  };

  const remove = async (id) => {
    await api.delete(`/alerts/${id}`);
    load();
  };

  return (
    <div className="space-y-6" data-testid="alerts-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Fırsat Radarı</div>
          <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">Fiyat Uyarıları</h1>
        </div>
        {alerts.some((a) => !a.is_read) && (
          <button data-testid="mark-all-read-button" className="btn-secondary flex items-center gap-2" onClick={markAllRead}>
            <Check size={16} /> Tümünü Okundu İşaretle
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-zinc-500 font-mono text-sm">Yükleniyor...</div>
      ) : alerts.length === 0 ? (
        <div className="card p-12 text-center">
          <BellRinging size={40} weight="duotone" className="text-zinc-600 mx-auto mb-3" />
          <div className="text-zinc-400 font-heading text-lg">Henüz uyarı yok</div>
          <div className="text-zinc-500 text-sm mt-2">Ürün detay sayfasından hedef fiyat kuralı ekleyin. Koşul sağlanınca burada ve Telegram'da görünür.</div>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((a, i) => (
            <div
              key={a.id}
              data-testid={`alert-row-${a.id}`}
              className={`card p-5 flex items-center justify-between gap-4 animate-fadeUp ${!a.is_read ? "border-primary/40" : ""}`}
              style={{ animationDelay: `${i * 40}ms` }}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium">{a.product_name}</span>
                  {!a.is_read && <span className="badge-discount">YENİ</span>}
                  <span className="text-[10px] font-mono border border-zinc-700 rounded px-2 py-0.5 text-zinc-300">
                    {ALERT_TYPE_LABELS[a.alert_type] || a.title || "Bildirim"}
                  </span>
                  {a.telegram_sent ? (
                    <span className="badge-stock flex items-center gap-1"><PaperPlaneTilt size={11} /> Telegram gönderildi</span>
                  ) : (
                    <span className="badge-nostock">Telegram gönderilemedi</span>
                  )}
                </div>
                <div className="text-sm text-zinc-500 mt-1">
                  {a.store} · {a.size_label || "Beden / numara"}: <span className="text-zinc-300">{alertSizeText(a)}</span>
                  {a.price_type ? ` · ${a.price_type}` : ""} · {fmtDate(a.created_at)}
                </div>
                {a.audience?.length > 0 && (
                  <div className="text-xs text-primary mt-1">Kimin için: {a.audience.join(", ")}</div>
                )}
                {a.ai_comment && (
                  <div className="text-xs text-primary/80 mt-1 font-mono">🤖 AI: {a.ai_comment}</div>
                )}
                <div className="text-xs text-zinc-600 mt-0.5 italic">Stok durumu bildirim anında stokta görünüyordu.</div>
                {a.feedback && (
                  <div className="mt-1.5 flex items-center gap-1.5">
                    <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${
                      a.feedback === "bought"
                        ? "bg-green-500/10 text-green-400 border-green-500/30"
                        : a.feedback === "no_size"
                        ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/30"
                        : "bg-red-500/10 text-red-400 border-red-500/30"
                    }`}>
                      {a.feedback_label || a.feedback}
                    </span>
                    <span className="text-[10px] text-zinc-600 font-mono">Telegram geri bildirimi</span>
                  </div>
                )}
              </div>
              <div className="text-right shrink-0">
                <div className="text-primary font-mono font-bold text-xl tabular-nums">{fmtPrice(a.price)}</div>
                <div className="text-xs text-zinc-500">
                  {a.previous_price ? "Önceki" : "Hedef"}: {fmtPrice(a.previous_price || a.target_price)}
                </div>
                <div className="flex gap-2 mt-2 justify-end">
                  {a.url && (
                    <a href={a.url} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline" data-testid={`alert-link-${a.id}`}>
                      Ürüne Git →
                    </a>
                  )}
                  {!a.is_read && (
                    <button onClick={() => markRead(a.id)} className="text-xs text-zinc-400 hover:text-white" data-testid={`alert-read-${a.id}`}>
                      Okundu
                    </button>
                  )}
                  <button onClick={() => remove(a.id)} className="text-zinc-500 hover:text-red-400" data-testid={`alert-delete-${a.id}`}>
                    <Trash size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
