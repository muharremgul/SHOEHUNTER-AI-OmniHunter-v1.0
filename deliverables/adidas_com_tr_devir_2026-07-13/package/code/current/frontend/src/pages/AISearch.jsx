import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { MagnifyingGlass, CircleNotch, Plus, WarningCircle, CheckCircle, Prohibit } from "@phosphor-icons/react";
import api, { fmtPrice } from "../api";

const PLACEHOLDER = "https://images.unsplash.com/photo-1552346154-21d32810aba3?crop=entropy&cs=srgb&fm=jpg&w=400";

const STATUS_LABELS = {
  ok: { label: "OK", cls: "text-primary", icon: CheckCircle },
  blocked: { label: "Bot koruması", cls: "text-red-400", icon: Prohibit },
  not_found: { label: "Bulunamadı", cls: "text-yellow-400", icon: WarningCircle },
  error: { label: "Hata", cls: "text-red-400", icon: WarningCircle },
  timeout: { label: "Zaman aşımı", cls: "text-yellow-400", icon: WarningCircle },
};

export default function AISearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [trackingUrl, setTrackingUrl] = useState(null);
  const [searchParams] = useSearchParams();

  const search = useCallback(async (q) => {
    const term = (q || "").trim();
    if (!term) return;
    setLoading(true);
    setResult(null);
    try {
      const { data } = await api.post("/search", { query: term, use_ai: true });
      setResult(data);
      if (data.total_results === 0) toast.warning("Hiçbir mağazadan sonuç alınamadı. Çoğu site bot koruması kullanıyor olabilir.");
    } catch (e) {
      toast.error("Arama başarısız: " + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setQuery(q);
      toast.info(`AI Koç önerisi aranıyor: ${q}`);
      search(q);
    }
  }, []);

  const track = async (candidate) => {
    setTrackingUrl(candidate.url);
    try {
      await api.post("/search/track", candidate);
      toast.success(`Takibe alındı: ${candidate.title}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Takibe alınamadı");
    } finally {
      setTrackingUrl(null);
    }
  };

  return (
    <div className="space-y-6" data-testid="ai-search-page">
      <div className="text-center pt-8 pb-4">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Zero-Link Tracking</div>
        <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">AI Arama</h1>
        <p className="text-zinc-500 text-sm mt-2 max-w-lg mx-auto">
          Link girmeden ürün adı yazın. AI sorguyu normalize eder, Türkiye mağazalarında paralel arama yapar.
        </p>
      </div>

      <div className="max-w-2xl mx-auto">
        <div className="relative">
          <MagnifyingGlass size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            data-testid="ai-search-input"
            className="input-dark !pl-12 !py-4 !text-base"
            placeholder="Brooks Glycerin 22, ASICS Novablast 5, Puma Velocity Nitro..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search(query)}
          />
          <button
            data-testid="ai-search-submit"
            className="btn-primary absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2"
            onClick={() => search(query)}
            disabled={loading}
          >
            {loading ? <CircleNotch size={16} className="animate-spin" /> : <MagnifyingGlass size={16} />}
            {loading ? "Aranıyor..." : "Ara"}
          </button>
        </div>
        {loading && (
          <div className="mt-4 h-1 bg-zinc-900 rounded overflow-hidden">
            <div className="h-full w-1/4 bg-primary animate-scanline" />
          </div>
        )}
      </div>

      {result && (
        <div className="space-y-6 max-w-5xl mx-auto">
          {result.analysis?.normalized_query && result.analysis.normalized_query !== result.query && (
            <div className="text-center text-sm text-zinc-500 font-mono">
              AI normalize: <span className="text-primary">{result.analysis.normalized_query}</span>
              {result.analysis.brand && ` · Marka: ${result.analysis.brand}`}
            </div>
          )}

          <div className="flex flex-wrap gap-2 justify-center">
            {result.stores.map((s) => {
              const st = STATUS_LABELS[s.status] || STATUS_LABELS.error;
              const Icon = st.icon;
              return (
                <span key={s.store} className="text-xs font-mono px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 flex items-center gap-1.5">
                  <Icon size={12} className={st.cls} />
                  {s.store}: <span className={st.cls}>{s.status === "ok" ? `${s.results.length} sonuç` : st.label}</span>
                </span>
              );
            })}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {result.stores
              .flatMap((s) => s.results)
              .sort((a, b) => b.score - a.score)
              .map((c, i) => (
                <div key={c.url} className="card overflow-hidden hover:border-primary/40 transition-colors animate-fadeUp flex flex-col" style={{ animationDelay: `${i * 40}ms` }} data-testid={`search-result-${i}`}>
                  <div className="h-36 bg-zinc-900 overflow-hidden">
                    <img
                      src={c.image || PLACEHOLDER}
                      alt={c.title}
                      className="w-full h-full object-cover"
                      onError={(e) => { e.target.src = PLACEHOLDER; }}
                      loading="lazy"
                    />
                  </div>
                  <div className="p-4 flex flex-col flex-1">
                    <div className="text-xs font-mono text-primary">{c.store} · %{c.score} eşleşme</div>
                    <a href={c.url} target="_blank" rel="noreferrer" className="text-sm font-medium mt-1 block hover:text-primary transition-colors line-clamp-2">
                      {c.title}
                    </a>
                    {c.price != null && (
                      <div className="mt-2 font-mono font-bold text-primary tabular-nums">
                        {fmtPrice(c.price)}
                        {c.old_price != null && c.old_price > c.price && (
                          <span className="text-zinc-500 line-through text-xs ml-2">{fmtPrice(c.old_price)}</span>
                        )}
                      </div>
                    )}
                    {c.sizes_in_stock?.length > 0 && (
                      <div className="mt-2">
                        <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono mb-1">Stoktaki numaralar</div>
                        <div className="flex flex-wrap gap-1">
                          {c.sizes_in_stock.slice(0, 10).map((s, j) => (
                            <span key={j} className="badge-stock !px-1.5 !py-0">{s}</span>
                          ))}
                          {c.sizes_in_stock.length > 10 && (
                            <span className="text-xs text-zinc-500">+{c.sizes_in_stock.length - 10}</span>
                          )}
                        </div>
                      </div>
                    )}
                    {c.enriched && c.sizes_total > 0 && c.sizes_in_stock?.length === 0 && (
                      <div className="mt-2 text-xs text-red-400 font-mono">Hiçbir numara stokta görünmüyor</div>
                    )}
                    <button
                      data-testid={`track-result-${i}`}
                      className="btn-secondary w-full mt-auto pt-1.5 !py-1.5 flex items-center justify-center gap-2"
                      style={{ marginTop: "auto" }}
                      onClick={() => track(c)}
                      disabled={trackingUrl === c.url}
                    >
                      {trackingUrl === c.url ? <CircleNotch size={14} className="animate-spin" /> : <Plus size={14} />}
                      Takibe Al
                    </button>
                  </div>
                </div>
              ))}
          </div>

          {result.total_results === 0 && (
            <div className="card p-8 text-center text-zinc-500 text-sm">
              Sonuç bulunamadı. Mağazaların çoğu bot koruması kullanıyor olabilir — ürün linkini doğrudan "Ürünler → Link ile Ekle" üzerinden ekleyebilirsiniz.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
