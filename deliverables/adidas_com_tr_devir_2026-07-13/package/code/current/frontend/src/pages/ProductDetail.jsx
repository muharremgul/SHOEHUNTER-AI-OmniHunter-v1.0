import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { ArrowLeft, ArrowsClockwise, Trash, Plus, CircleNotch, Target, Brain, CheckCircle, Warning, PencilSimple, Palette } from "@phosphor-icons/react";
import api, { fmtPrice, fmtDate } from "../api";

const DECISION_STYLES = {
  "AL": "bg-primary text-black",
  "ALINABİLİR": "bg-primary/25 text-primary border border-primary/40",
  "BEKLE": "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
  "SADECE ÇOK UCUZSA": "bg-orange-500/20 text-orange-400 border border-orange-500/30",
  "UYGUN DEĞİL": "bg-red-500/20 text-red-400 border border-red-500/30",
  "BELİRSİZ": "bg-zinc-800 text-zinc-400 border border-zinc-700",
};

const stockLabel = (status, inStock) => {
  const key = status || (inStock ? "in_stock" : "unknown");
  if (key === "in_stock") return { text: "Stokta", cls: "badge-stock" };
  if (key === "out_of_stock") return { text: "Stok yok", cls: "badge-nostock" };
  if (key === "blocked") return { text: "Engelli", cls: "badge-nostock" };
  if (key === "not_found") return { text: "Yayında yok", cls: "badge-nostock" };
  if (key === "error") return { text: "Hata", cls: "badge-nostock" };
  return { text: "Belirsiz", cls: "bg-yellow-500/15 text-yellow-300 border border-yellow-500/25 text-[10px] font-mono px-2 py-0.5 rounded" };
};

function BuyAdviceCard({ advice }) {
  if (!advice) return null;
  const style = DECISION_STYLES[advice.decision] || DECISION_STYLES["BELİRSİZ"];
  const bd = advice.breakdown || {};
  return (
    <div className="card p-6 border-primary/20" data-testid="buy-advice-card">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="font-heading font-semibold text-lg flex items-center gap-2">
          <Brain size={20} weight="duotone" className="text-primary" /> Şimdi Alınır mı?
        </h3>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-bold px-3 py-1 rounded-full ${style}`} data-testid="buy-advice-decision">
            {advice.decision}
          </span>
          <span className="font-mono text-2xl font-bold text-white tabular-nums">{advice.score}<span className="text-zinc-500 text-sm">/100</span></span>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-2 mt-4">
        {[["Fiyat", bd.fiyat, 40], ["Stok", bd.stok, 20], ["Profil", bd.profil, 25], ["Güven", bd.guven, 15]].map(([label, val, max]) => (
          <div key={label}>
            <div className="flex justify-between text-[10px] font-mono text-zinc-500 uppercase tracking-wider mb-1">
              <span>{label}</span><span>{val}/{max}</span>
            </div>
            <div className="h-1.5 bg-zinc-800 rounded overflow-hidden">
              <div className="h-full bg-primary rounded transition-all duration-500" style={{ width: `${(val / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-sm">
        {advice.reasons?.length > 0 && (
          <div className="space-y-1.5">
            {advice.reasons.map((r, i) => (
              <div key={i} className="flex items-start gap-2 text-zinc-300">
                <CheckCircle size={15} weight="fill" className="text-primary mt-0.5 shrink-0" /> {r}
              </div>
            ))}
          </div>
        )}
        {advice.risks?.length > 0 && (
          <div className="space-y-1.5">
            {advice.risks.map((r, i) => (
              <div key={i} className="flex items-start gap-2 text-zinc-400">
                <Warning size={15} weight="fill" className="text-yellow-500 mt-0.5 shrink-0" /> {r}
              </div>
            ))}
          </div>
        )}
      </div>
      {advice.insight?.min_30d && (
        <div className="mt-4 pt-3 border-t border-zinc-800 flex flex-wrap gap-x-6 gap-y-1 text-xs font-mono text-zinc-500">
          <span>30g min: <span className="text-zinc-300">{fmtPrice(advice.insight.min_30d)}</span></span>
          {advice.insight.avg_30d && <span>30g ort: <span className="text-zinc-300">{fmtPrice(advice.insight.avg_30d)}</span></span>}
          {advice.insight.min_90d && <span>90g min: <span className="text-zinc-300">{fmtPrice(advice.insight.min_90d)}</span></span>}
          {advice.listing_store && <span>Kaynak: <span className="text-zinc-300">{advice.listing_store}</span></span>}
        </div>
      )}
    </div>
  );
}

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [advice, setAdvice] = useState(null);
  const [newUrl, setNewUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkingId, setCheckingId] = useState(null);
  const [rule, setRule] = useState({ target_price: "", size: "", spectrum_mode: false, cooldown_hours: 24 });

  const load = useCallback(() => {
    api.get(`/products/${id}`).then((r) => setData(r.data)).catch(() => navigate("/urunler"));
    api.get(`/products/${id}/buy-advice`).then((r) => setAdvice(r.data)).catch(() => {});
  }, [id, navigate]);

  useEffect(() => {
    load();
  }, [load]);

  if (!data) return <div className="text-zinc-500 font-mono text-sm">Yükleniyor...</div>;

  const { product, listings, rules, alerts, history, family } = data;

  const chartData = history.map((h) => ({
    time: fmtDate(h.checked_at),
    fiyat: h.price,
    store: h.store,
  }));

  const addListing = async () => {
    if (!newUrl.trim()) return;
    setBusy(true);
    try {
      await api.post(`/products/${id}/listings`, { url: newUrl.trim() });
      toast.success("Link eklendi ve tarandı");
      setNewUrl("");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Link eklenemedi");
    } finally {
      setBusy(false);
    }
  };

  const checkListing = async (lid) => {
    setCheckingId(lid);
    try {
      const { data: res } = await api.post(`/listings/${lid}/check`);
      if (res.result.status === "ok") toast.success(`Fiyat: ${fmtPrice(res.result.price)}`);
      else if (res.result.status === "no_price") toast.warning("Fiyat okunamadı (bot koruması olabilir)");
      else toast.error(`Hata: ${res.result.error}`);
      if (res.alerts_created > 0) toast.success(`${res.alerts_created} yeni uyarı oluştu!`);
      load();
    } finally {
      setCheckingId(null);
    }
  };

  const deleteListing = async (lid) => {
    if (!window.confirm("Link silinsin mi?")) return;
    await api.delete(`/listings/${lid}`);
    load();
  };

  const enterManualPrice = async (lid) => {
    const val = window.prompt("Güncel fiyatı girin (TL):\n(Bot korumalı mağazalar için sitede gördüğünüz fiyatı yazın)");
    if (!val) return;
    const price = parseFloat(val.replace(".", "").replace(",", "."));
    if (!price || price <= 0) return toast.error("Geçerli bir fiyat girin");
    try {
      const { data: res } = await api.post(`/listings/${lid}/manual-price`, { price });
      toast.success(`Fiyat güncellendi: ${fmtPrice(price)}`);
      if (res.alerts_created > 0) toast.success(`${res.alerts_created} yeni uyarı oluştu!`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fiyat güncellenemedi");
    }
  };

  const addRule = async () => {
    if (!rule.target_price) return toast.error("Hedef fiyat gerekli");
    try {
      const { data: res } = await api.post("/rules", {
        product_id: id,
        target_price: parseFloat(rule.target_price),
        size: rule.size || null,
        spectrum_mode: rule.spectrum_mode,
        cooldown_hours: parseFloat(rule.cooldown_hours) || 24,
      });
      toast.success(res.alerts_created > 0 ? `Kural eklendi — koşul ZATEN sağlanıyor, ${res.alerts_created} uyarı gönderildi!` : "Kural eklendi");
      setRule({ target_price: "", size: "", spectrum_mode: false, cooldown_hours: 24 });
      load();
    } catch (e) {
      toast.error("Kural eklenemedi");
    }
  };

  const toggleRule = async (r) => {
    await api.patch(`/rules/${r.id}`, { enabled: !r.enabled });
    load();
  };

  const deleteRule = async (rid) => {
    await api.delete(`/rules/${rid}`);
    load();
  };

  return (
    <div className="space-y-6" data-testid="product-detail-page">
      <button onClick={() => navigate("/urunler")} className="text-zinc-400 hover:text-white text-sm flex items-center gap-2 transition-colors" data-testid="back-button">
        <ArrowLeft size={16} /> Ürünlere Dön
      </button>

      <div className="flex items-start gap-6 flex-wrap">
        {product.image && (
          <img src={product.image} alt={product.name} className="w-32 h-32 object-cover rounded-lg border border-zinc-800" />
        )}
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">{product.brand || "Ürün"}</div>
          <h1 className="text-3xl font-heading font-bold tracking-tighter mt-1">{product.name}</h1>
          <div className="text-zinc-500 text-sm mt-1">{listings.length} mağaza linki · {rules.length} kural · {alerts.length} uyarı</div>
        </div>
      </div>

      <BuyAdviceCard advice={advice} />

      {family?.length > 0 && (
        <div className="card p-6" data-testid="product-family-section">
          <h3 className="font-heading font-semibold text-lg mb-1 flex items-center gap-2">
            <Palette size={20} weight="duotone" className="text-primary" /> Ürün Ailesi — Diğer Renkler/Varyantlar
          </h3>
          <p className="text-xs text-zinc-500 mb-4 font-mono">
            Spektrum modlu kurallar bu ailedeki TÜM ürünleri tarar ve en ucuz stoklu olanı bildirir.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {family.map((f, i) => {
              const stock = stockLabel(f.stock_status, f.in_stock);
              return (
              <button
                key={f.id}
                data-testid={`family-item-${i}`}
                onClick={() => navigate(`/urunler/${f.id}`)}
                className="flex items-center gap-3 bg-zinc-900/60 border border-zinc-800 rounded-lg p-3 text-left hover:border-primary/40 transition-colors"
              >
                {f.image && <img src={f.image} alt="" className="w-12 h-12 object-cover rounded shrink-0" />}
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{f.name}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="font-mono text-primary text-sm font-bold">{fmtPrice(f.best_price)}</span>
                    <span className={stock.cls}>{stock.text}</span>
                  </div>
                </div>
              </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Listings */}
      <div className="card p-6">
        <h3 className="font-heading font-semibold text-lg mb-4">Mağaza Linkleri</h3>
        <div className="flex gap-3 mb-4">
          <input data-testid="add-listing-input" className="input-dark" placeholder="Yeni mağaza linki ekle..." value={newUrl} onChange={(e) => setNewUrl(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addListing()} />
          <button data-testid="add-listing-submit" className="btn-primary shrink-0 flex items-center gap-2" onClick={addListing} disabled={busy}>
            {busy ? <CircleNotch size={16} className="animate-spin" /> : <Plus size={16} />} Ekle
          </button>
        </div>
        {listings.length === 0 ? (
          <div className="text-zinc-500 text-sm font-mono py-4">Henüz link yok.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-zinc-500 text-xs uppercase tracking-wider border-b border-zinc-800">
                  <th className="py-2 pr-4">Mağaza</th>
                  <th className="py-2 pr-4">Fiyat</th>
                  <th className="py-2 pr-4">Eski</th>
                  <th className="py-2 pr-4">Kaynak</th>
                  <th className="py-2 pr-4">Stok</th>
                  <th className="py-2 pr-4">Son Kontrol</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {listings.map((l) => {
                  const stock = stockLabel(l.last_stock_status, l.last_in_stock);
                  return (
                  <tr key={l.id} className="border-b border-zinc-800 hover:bg-zinc-900/50 last:border-0" data-testid={`listing-row-${l.id}`}>
                    <td className="py-3 pr-4">
                      <a href={l.url} target="_blank" rel="noreferrer" className="text-white hover:text-primary transition-colors font-medium">{l.store}</a>
                      {l.last_error && <div className="text-xs text-red-400 mt-0.5 max-w-[200px] truncate">{l.last_error}</div>}
                    </td>
                    <td className="py-3 pr-4 font-mono font-bold text-primary tabular-nums">{fmtPrice(l.last_price)}
                      {l.last_cart_price && <span className="badge-discount ml-2">Sepette</span>}
                    </td>
                    <td className="py-3 pr-4 font-mono text-zinc-500 line-through tabular-nums">{l.last_old_price ? fmtPrice(l.last_old_price) : ""}</td>
                    <td className="py-3 pr-4 font-mono text-xs text-zinc-400">{l.last_price_source || "—"}</td>
                    <td className="py-3 pr-4">
                      <span className={l.last_sizes?.length ? (l.last_stock_count > 0 ? "badge-stock" : "badge-nostock") : stock.cls}>
                        {l.last_sizes?.length ? `${l.last_stock_count}/${l.last_sizes.length} beden` : stock.text}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs text-zinc-500 font-mono">{fmtDate(l.last_checked_at)}</td>
                    <td className="py-3 text-right whitespace-nowrap">
                      <button data-testid={`check-listing-${l.id}`} onClick={() => checkListing(l.id)} disabled={checkingId === l.id} className="text-zinc-400 hover:text-primary p-1.5 transition-colors" title="Şimdi kontrol et">
                        {checkingId === l.id ? <CircleNotch size={16} className="animate-spin" /> : <ArrowsClockwise size={16} />}
                      </button>
                      <button data-testid={`manual-price-${l.id}`} onClick={() => enterManualPrice(l.id)} className="text-zinc-400 hover:text-primary p-1.5 transition-colors" title="Elle fiyat gir (bot korumalı mağazalar için)">
                        <PencilSimple size={16} />
                      </button>
                      <button data-testid={`delete-listing-${l.id}`} onClick={() => deleteListing(l.id)} className="text-zinc-400 hover:text-red-400 p-1.5 transition-colors" title="Sil">
                        <Trash size={16} />
                      </button>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Sizes */}
        {listings.some((l) => l.last_sizes?.length > 0) && (
          <div className="mt-6">
            <h4 className="text-sm font-medium text-zinc-400 mb-3">Canlı Beden / Stok Durumu</h4>
            {listings.filter((l) => l.last_sizes?.length).map((l) => (
              <div key={l.id} className="mb-3">
                <div className="text-xs text-zinc-500 font-mono mb-1.5">{l.store}</div>
                <div className="flex flex-wrap gap-2">
                  {l.last_sizes.map((s, i) => (
                    <span key={i} className={s.in_stock ? "badge-stock" : "badge-nostock"} title={s.sku ? `SKU: ${s.sku}` : ""}>
                      {s.name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Price chart */}
        <div className="card p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Fiyat Geçmişi</h3>
          {chartData.length < 2 ? (
            <div className="text-zinc-500 text-sm font-mono py-8 text-center">Grafik için en az 2 fiyat kaydı gerekli.</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="#27272A" strokeDasharray="3 3" />
                <XAxis dataKey="time" stroke="#52525B" fontSize={10} />
                <YAxis stroke="#52525B" fontSize={11} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#18181B", border: "1px solid #3F3F46", borderRadius: 8, fontSize: 12 }} />
                <Line type="monotone" dataKey="fiyat" stroke="#CCFF00" strokeWidth={2.5} dot={{ r: 3, fill: "#CCFF00" }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Rules */}
        <div className="card p-6">
          <h3 className="font-heading font-semibold text-lg mb-4 flex items-center gap-2">
            <Target size={20} weight="duotone" className="text-primary" /> Fiyat Kuralları
          </h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <input data-testid="rule-price-input" type="number" className="input-dark" placeholder="Hedef fiyat (TL) *" value={rule.target_price} onChange={(e) => setRule({ ...rule, target_price: e.target.value })} />
            <input data-testid="rule-size-input" className="input-dark" placeholder="Beden (örn: 44, boş=herhangi)" value={rule.size} onChange={(e) => setRule({ ...rule, size: e.target.value })} />
            <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer">
              <input data-testid="rule-spectrum-checkbox" type="checkbox" checked={rule.spectrum_mode} onChange={(e) => setRule({ ...rule, spectrum_mode: e.target.checked })} className="accent-[#CCFF00]" />
              Spektrum Modu (en ucuzu bildir)
            </label>
            <button data-testid="rule-submit" className="btn-primary" onClick={addRule}>Kural Ekle</button>
          </div>
          {rules.length === 0 ? (
            <div className="text-zinc-500 text-sm font-mono py-4">Kural yok. Hedef fiyat girin, koşul sağlanınca Telegram bildirimi gelsin.</div>
          ) : (
            <div className="space-y-2">
              {rules.map((r) => (
                <div key={r.id} className="flex items-center justify-between bg-zinc-900/60 rounded-lg px-4 py-2.5 border border-zinc-800" data-testid={`rule-row-${r.id}`}>
                  <div className="text-sm font-mono">
                    <span className="text-primary font-bold">≤ {fmtPrice(r.target_price)}</span>
                    <span className="text-zinc-400 ml-3">Beden: {r.size || "Herhangi"}</span>
                    {r.spectrum_mode && <span className="badge-discount ml-2">Spektrum</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <button data-testid={`toggle-rule-${r.id}`} onClick={() => toggleRule(r)} className={`text-xs px-2 py-1 rounded transition-colors ${r.enabled ? "bg-primary/20 text-primary" : "bg-zinc-800 text-zinc-500"}`}>
                      {r.enabled ? "AKTİF" : "PASİF"}
                    </button>
                    <button data-testid={`delete-rule-${r.id}`} onClick={() => deleteRule(r.id)} className="text-zinc-500 hover:text-red-400 transition-colors"><Trash size={15} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Alerts for this product */}
      {alerts.length > 0 && (
        <div className="card p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Bu Ürünün Uyarıları</h3>
          <div className="space-y-2">
            {alerts.map((a) => (
              <div key={a.id} className="flex items-center justify-between border-b border-zinc-800 py-2 last:border-0 text-sm">
                <div>
                  <span className="text-zinc-400">{fmtDate(a.created_at)}</span>
                  <span className="ml-3">{a.store} · Beden: {a.size} · {a.price_type}</span>
                  {a.telegram_sent && <span className="badge-stock ml-2">Telegram ✓</span>}
                </div>
                <div className="font-mono text-primary font-bold">{fmtPrice(a.price)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
