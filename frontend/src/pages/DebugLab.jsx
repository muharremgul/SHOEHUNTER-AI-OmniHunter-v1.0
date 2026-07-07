import React, { useEffect, useState } from "react";
import { Terminal } from "@phosphor-icons/react";
import api, { fmtDate } from "../api";

export default function DebugLab() {
  const [listings, setListings] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [runs, setRuns] = useState([]);

  useEffect(() => {
    api.get("/listings").then((r) => setListings(r.data));
    api.get("/check/runs").then((r) => setRuns(r.data));
  }, []);

  const select = async (id) => {
    setSelected(id);
    const { data } = await api.get(`/listings/${id}/debug`);
    setDetail(data);
  };

  return (
    <div className="space-y-6" data-testid="debug-page">
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Parser İç Görünüm</div>
        <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">Debug Lab</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card p-4 max-h-[500px] overflow-y-auto">
          <h3 className="font-mono text-sm text-zinc-400 mb-3 flex items-center gap-2">
            <Terminal size={16} className="text-primary" /> LİNKLER
          </h3>
          {listings.length === 0 ? (
            <div className="text-zinc-600 text-xs font-mono">Link yok.</div>
          ) : (
            <div className="space-y-1">
              {listings.map((l) => (
                <button
                  key={l.id}
                  data-testid={`debug-listing-${l.id}`}
                  onClick={() => select(l.id)}
                  className={`w-full text-left px-3 py-2 rounded text-xs font-mono transition-colors ${
                    selected === l.id ? "bg-primary/10 text-primary border border-primary/30" : "text-zinc-400 hover:bg-zinc-900 border border-transparent"
                  }`}
                >
                  <div className="font-bold">{l.store}</div>
                  <div className="truncate text-zinc-500">{l.title || l.url}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card p-4 lg:col-span-2 max-h-[500px] overflow-auto">
          <h3 className="font-mono text-sm text-zinc-400 mb-3">HAM VERİ</h3>
          {detail ? (
            <pre className="text-xs font-mono text-primary/90 whitespace-pre-wrap leading-relaxed" data-testid="debug-json">
              {JSON.stringify(
                {
                  store: detail.store,
                  url: detail.url,
                  last_price: detail.last_price,
                  last_old_price: detail.last_old_price,
                  last_cart_price: detail.last_cart_price,
                  last_price_source: detail.last_price_source,
                  last_confidence: detail.last_confidence,
                  last_stock_count: detail.last_stock_count,
                  last_in_stock: detail.last_in_stock,
                  last_error: detail.last_error,
                  last_checked_at: detail.last_checked_at,
                  last_sizes: detail.last_sizes,
                  last_raw: detail.last_raw,
                },
                null,
                2
              )}
            </pre>
          ) : (
            <div className="text-zinc-600 text-xs font-mono">← Bir link seçin</div>
          )}
        </div>
      </div>

      <div className="card p-6">
        <h3 className="font-heading font-semibold text-lg mb-4">Kontrol Geçmişi</h3>
        {runs.length === 0 ? (
          <div className="text-zinc-500 text-sm font-mono">Henüz kontrol çalıştırılmadı.</div>
        ) : (
          <table className="w-full text-sm font-mono">
            <thead>
              <tr className="text-left text-zinc-500 text-xs uppercase border-b border-zinc-800">
                <th className="py-2">Zaman</th>
                <th className="py-2">Tetikleyici</th>
                <th className="py-2 text-right">Toplam</th>
                <th className="py-2 text-right">Başarılı</th>
                <th className="py-2 text-right">Hata</th>
                <th className="py-2 text-right">Uyarı</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-b border-zinc-800 last:border-0 hover:bg-zinc-900/50">
                  <td className="py-2 text-xs">{fmtDate(r.started_at)}</td>
                  <td className="py-2 text-xs">{r.trigger === "manual" ? "Manuel" : "Scheduler"}</td>
                  <td className="py-2 text-right tabular-nums">{r.total}</td>
                  <td className="py-2 text-right text-primary tabular-nums">{r.success}</td>
                  <td className="py-2 text-right text-red-400 tabular-nums">{r.failed}</td>
                  <td className="py-2 text-right tabular-nums">{r.alerts_created}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
