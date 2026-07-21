import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sneaker, LinkSimple, Target, BellRinging, Clock, CheckCircle, XCircle, Fire, ShieldWarning, WifiHigh } from "@phosphor-icons/react";
import api, { fmtPrice, fmtDate } from "../api";

const alertSizes = (alert) => (
  alert?.sizes?.length ? [...new Set(alert.sizes)].join(", ") : alert?.size || "Doğrulanamadı"
);

const DEAL_STYLES = {
  "AL": "bg-primary text-black",
  "ALINABİLİR": "bg-primary/25 text-primary border border-primary/40",
  "BEKLE": "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
  "SADECE ÇOK UCUZSA": "bg-orange-500/20 text-orange-400 border border-orange-500/30",
  "UYGUN DEĞİL": "bg-red-500/20 text-red-400 border border-red-500/30",
  "BELİRSİZ": "bg-zinc-800 text-zinc-400 border border-zinc-700",
};

function MetricCard({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="card p-6 animate-fadeUp">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 font-mono">{label}</div>
          <div className={`text-3xl font-heading font-bold mt-2 ${accent ? "text-primary" : "text-white"}`}>
            {value}
          </div>
          {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
        </div>
        <Icon size={32} weight="duotone" className={accent ? "text-primary" : "text-zinc-600"} />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [deals, setDeals] = useState(null);
  const [storeHealth, setStoreHealth] = useState([]);
  const [storeHealthError, setStoreHealthError] = useState(false);

  useEffect(() => {
    api.get("/dashboard").then((r) => setData(r.data)).catch(() => {});
    api.get("/dashboard/deals").then((r) => setDeals(r.data)).catch(() => setDeals([]));
    api.get("/stores/health")
      .then((r) => {
        setStoreHealth(r.data || []);
        setStoreHealthError(false);
      })
      .catch(() => setStoreHealthError(true));
  }, []);

  if (!data)
    return (
      <div className="text-zinc-500 font-mono text-sm" data-testid="dashboard-loading">
        Panel yükleniyor...
      </div>
    );

  const sch = data.scheduler;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Kontrol Merkezi</div>
        <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">Panel</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard icon={Sneaker} label="İzlenen Ürün" value={data.products} accent />
        <MetricCard icon={LinkSimple} label="Aktif Link" value={data.listings} />
        <MetricCard icon={Target} label="Aktif Kural" value={data.rules} />
        <MetricCard
          icon={BellRinging}
          label="Okunmamış Uyarı"
          value={data.unread_alerts}
          sub={`Toplam ${data.total_alerts} uyarı`}
        />
      </div>

      {deals && deals.length > 0 && (
        <div className="card p-6 border-primary/20" data-testid="daily-deals-section">
          <h3 className="font-heading font-semibold text-lg mb-4 flex items-center gap-2">
            <Fire size={20} weight="duotone" className="text-primary" /> Günün Fırsatları
            <span className="text-xs font-mono text-zinc-500 font-normal ml-2">AI Buy Advisor skoruna göre</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {deals.map((d, i) => (
              <Link
                key={d.product_id}
                to={`/urunler/${d.product_id}`}
                data-testid={`deal-card-${i}`}
                className="flex items-center gap-3 bg-zinc-900/60 border border-zinc-800 rounded-lg p-3 hover:border-primary/40 hover:-translate-y-0.5 transition-all duration-200 animate-fadeUp"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                {d.image && <img src={d.image} alt="" className="w-14 h-14 object-cover rounded shrink-0" />}
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{d.name}</div>
                  <div className="text-xs text-zinc-500 truncate">{d.store} {d.top_reason ? `· ${d.top_reason}` : ""}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${DEAL_STYLES[d.decision] || DEAL_STYLES["BELİRSİZ"]}`}>
                      {d.decision} · {d.score}
                    </span>
                    {d.price != null && <span className="font-mono text-primary text-sm font-bold">{fmtPrice(d.price)}</span>}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="card p-6" data-testid="store-health-panel">
        <h3 className="font-heading font-semibold text-lg mb-4 flex items-center gap-2">
          <WifiHigh size={20} weight="duotone" className="text-primary" /> Mağaza Sağlığı
          <span className="text-xs font-mono text-zinc-500 font-normal ml-2">Son 24 saat</span>
        </h3>
        {storeHealthError ? (
          <div className="text-sm text-red-400 font-mono">Mağaza sağlık verisi şu anda alınamıyor.</div>
        ) : storeHealth.length === 0 ? (
          <div className="text-sm text-zinc-500 font-mono">Son 24 saatte mağaza kontrolü bulunmuyor.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-mono text-zinc-500 uppercase tracking-wider border-b border-zinc-800">
                  <th className="pb-2 pr-4">Mağaza</th>
                  <th className="pb-2 pr-4">Kontrol</th>
                  <th className="pb-2 pr-4">Başarı</th>
                  <th className="pb-2 pr-4">Engellenen</th>
                  <th className="pb-2 pr-4">Ort. gecikme</th>
                  <th className="pb-2">Devre</th>
                </tr>
              </thead>
              <tbody>
                {storeHealth.map((store) => {
                  const rate = store.success_rate_24h == null ? null : Math.round(store.success_rate_24h * 100);
                  return (
                    <tr key={store.store_slug} className="border-b border-zinc-800/50 last:border-0">
                      <td className="py-2.5 pr-4 font-medium">{store.store_slug}</td>
                      <td className="py-2.5 pr-4 font-mono text-zinc-400">{store.checks_24h || 0}</td>
                      <td className="py-2.5 pr-4">
                        {rate == null ? <span className="text-zinc-600">—</span> : (
                          <span className={rate >= 80 ? "text-primary font-mono" : rate >= 50 ? "text-yellow-400 font-mono" : "text-red-400 font-mono"}>
                            %{rate}
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 pr-4">
                        {(store.blocked_count_24h || 0) > 0 ? (
                          <span className="text-orange-400 font-mono flex items-center gap-1">
                            <ShieldWarning size={13} /> {store.blocked_count_24h}
                          </span>
                        ) : <span className="text-zinc-600 font-mono">0</span>}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-zinc-400">
                        {store.average_latency_ms == null ? "—" : `${Math.round(store.average_latency_ms)}ms`}
                      </td>
                      <td className="py-2.5">
                        {store.circuit_open
                          ? <span className="badge-nostock">Açık</span>
                          : <span className="badge-stock">Kapalı</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card p-6 lg:col-span-2">
          <h3 className="font-heading font-semibold text-lg mb-4">Son Uyarılar</h3>
          {data.recent_alerts.length === 0 ? (
            <div className="text-zinc-500 text-sm py-8 text-center font-mono">
              Henüz uyarı yok. Kural ekleyip fiyat düşüşünü bekleyin.
            </div>
          ) : (
            <div className="space-y-2">
              {data.recent_alerts.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between border-b border-zinc-800 py-2 last:border-0"
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{a.product_name}</div>
                    <div className="text-xs text-zinc-500">
                      {a.store} · {a.size_label || "Beden / numara"}: {alertSizes(a)} · {fmtDate(a.created_at)}
                    </div>
                    {a.audience?.length > 0 && (
                      <div className="text-[11px] text-primary">Kimin için: {a.audience.join(", ")}</div>
                    )}
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <div className="text-primary font-mono font-bold">{fmtPrice(a.price)}</div>
                    <div className="text-xs text-zinc-500">
                      {a.previous_price ? "Önceki" : "Hedef"}: {fmtPrice(a.previous_price || a.target_price)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          <Link to="/uyarilar" className="text-primary text-sm mt-4 inline-block hover:underline" data-testid="all-alerts-link">
            Tüm uyarıları gör →
          </Link>
        </div>

        <div className="space-y-6">
          <div className="card p-6">
            <h3 className="font-heading font-semibold text-lg mb-3 flex items-center gap-2">
              <Clock size={20} weight="duotone" className="text-primary" /> Scheduler
            </h3>
            <div className="space-y-2 text-sm font-mono">
              <div className="flex justify-between">
                <span className="text-zinc-500">Durum</span>
                <span className={sch.enabled ? "text-primary" : "text-zinc-400"}>
                  {sch.enabled ? "AKTİF" : "KAPALI"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Aralık</span>
                <span>{sch.interval_minutes} dk</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Sonraki</span>
                <span className="text-xs">{sch.next_run ? fmtDate(sch.next_run) : "—"}</span>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <h3 className="font-heading font-semibold text-lg mb-3">Son Kontrol</h3>
            {data.last_run ? (
              <div className="space-y-2 text-sm font-mono">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Zaman</span>
                  <span className="text-xs">{fmtDate(data.last_run.started_at)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500">Başarılı</span>
                  <span className="text-primary flex items-center gap-1">
                    <CheckCircle size={14} /> {data.last_run.success}/{data.last_run.total}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500">Hatalı</span>
                  <span className="text-red-400 flex items-center gap-1">
                    <XCircle size={14} /> {data.last_run.failed}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Yeni uyarı</span>
                  <span>{data.last_run.alerts_created}</span>
                </div>
              </div>
            ) : (
              <div className="text-zinc-500 text-sm font-mono">Henüz kontrol yapılmadı.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
