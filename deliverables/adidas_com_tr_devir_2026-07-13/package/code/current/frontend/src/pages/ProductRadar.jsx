import React, { useEffect, useMemo, useState } from "react";
import {
  Check,
  CircleNotch,
  Crosshair,
  Pause,
  Play,
  Plus,
  Trash,
  X,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import api, { fmtDate, fmtPrice } from "../api";


const EMPTY_FORM = {
  raw_query: "",
  desired_sizes: "",
  target_price: "",
  minimum_drop_percent: "",
  minimum_drop_amount: "",
  gender: "",
  color_policy: "any",
  allowed_colors: "",
  excluded_colors: "",
  required_tokens: "",
  excluded_tokens: "",
  discovery_frequency_hours: 12,
  refresh_frequency_minutes: 360,
  store_scope: [],
};

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function candidateCount(watch, status) {
  return (watch.candidate_counts || []).find((item) => item._id === status)?.count || 0;
}

export default function ProductRadar() {
  const [watches, setWatches] = useState([]);
  const [stores, setStores] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [activeAction, setActiveAction] = useState(null);
  const [detail, setDetail] = useState(null);

  const load = async () => {
    const [{ data: watchRows }, { data: storeRows }] = await Promise.all([api.get("/watches"), api.get("/stores")]);
    setWatches(watchRows);
    setStores(storeRows.filter((store) => store.searchable));
  };

  useEffect(() => {
    load().catch((error) => toast.error(error.response?.data?.detail || "Ürün radarları yüklenemedi"));
  }, []);

  const selectedStores = useMemo(() => new Set(form.store_scope), [form.store_scope]);

  const toggleStore = (slug) => {
    const next = new Set(selectedStores);
    if (next.has(slug)) next.delete(slug);
    else next.add(slug);
    setForm({ ...form, store_scope: [...next] });
  };

  const create = async (event) => {
    event.preventDefault();
    if (!form.raw_query.trim()) return;
    setBusy(true);
    try {
      await api.post("/watches", {
        ...form,
        raw_query: form.raw_query.trim(),
        desired_sizes: splitList(form.desired_sizes),
        allowed_colors: splitList(form.allowed_colors),
        excluded_colors: splitList(form.excluded_colors),
        required_tokens: splitList(form.required_tokens),
        excluded_tokens: splitList(form.excluded_tokens),
        target_price: form.target_price ? Number(form.target_price) : null,
        minimum_drop_percent: form.minimum_drop_percent ? Number(form.minimum_drop_percent) : 0,
        minimum_drop_amount: form.minimum_drop_amount ? Number(form.minimum_drop_amount) : 0,
        gender: form.gender || null,
        discovery_frequency_hours: Number(form.discovery_frequency_hours),
        refresh_frequency_minutes: Number(form.refresh_frequency_minutes),
      });
      toast.success("Ürün radarı oluşturuldu; ilk keşif sıraya alındı");
      setForm(EMPTY_FORM);
      setShowForm(false);
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ürün radarı oluşturulamadı");
    } finally {
      setBusy(false);
    }
  };

  const run = async (watch) => {
    setActiveAction(`run-${watch.id}`);
    try {
      await api.post(`/watches/${watch.id}/run`);
      toast.success("Keşif işi sıraya alındı");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Keşif başlatılamadı");
    } finally {
      setActiveAction(null);
    }
  };

  const toggle = async (watch) => {
    setActiveAction(`toggle-${watch.id}`);
    try {
      await api.patch(`/watches/${watch.id}`, { active: !watch.active });
      await load();
    } finally {
      setActiveAction(null);
    }
  };

  const remove = async (watch) => {
    if (!window.confirm(`"${watch.raw_query}" radarı silinsin mi?`)) return;
    await api.delete(`/watches/${watch.id}`);
    if (detail?.watch?.id === watch.id) setDetail(null);
    await load();
    toast.success("Ürün radarı silindi");
  };

  const openDetail = async (watch) => {
    setActiveAction(`detail-${watch.id}`);
    try {
      const { data } = await api.get(`/watches/${watch.id}`);
      setDetail(data);
    } finally {
      setActiveAction(null);
    }
  };

  const review = async (candidate, decision) => {
    setActiveAction(`review-${candidate.id}`);
    try {
      await api.post(`/candidates/${candidate.id}/review`, { decision });
      const { data } = await api.get(`/watches/${candidate.watch_id}`);
      setDetail(data);
      await load();
      const messages = {
        approve: "Aday ürüne bağlandı",
        variant: "Aday farklı varyant olarak bağlandı",
        same_family: "Aday aynı aile olarak işaretlendi",
        reject: "Aday reddedildi",
      };
      toast.success(messages[decision]);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Aday güncellenemedi");
    } finally {
      setActiveAction(null);
    }
  };

  return (
    <div className="space-y-6" data-testid="product-radar-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Otonom Keşif</div>
          <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">Ürün Radarı</h1>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowForm((value) => !value)}>
          <Plus size={16} /> Yeni Radar
        </button>
      </div>

      {showForm && (
        <form onSubmit={create} className="border-y border-zinc-800 py-5 space-y-4 animate-fadeUp">
          <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr_1fr] gap-3">
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Ürün</label>
              <input
                className="input-dark mt-1"
                placeholder="Adidas Adizero Evo SL"
                value={form.raw_query}
                onChange={(event) => setForm({ ...form, raw_query: event.target.value })}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Bedenler</label>
              <input
                className="input-dark mt-1"
                placeholder="43 1/3, 44"
                value={form.desired_sizes}
                onChange={(event) => setForm({ ...form, desired_sizes: event.target.value })}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Hedef fiyat</label>
              <input
                className="input-dark mt-1"
                type="number"
                min="1"
                placeholder="5500"
                value={form.target_price}
                onChange={(event) => setForm({ ...form, target_price: event.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Cinsiyet</label>
              <select className="input-dark mt-1" value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value })}>
                <option value="">Belirtilmedi</option>
                <option value="men">Erkek</option>
                <option value="women">Kadın</option>
                <option value="unisex">Unisex</option>
                <option value="kids">Çocuk</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Renk</label>
              <select className="input-dark mt-1" value={form.color_policy} onChange={(event) => setForm({ ...form, color_policy: event.target.value })}>
                <option value="any">Fark etmez</option>
                <option value="dark">Sadece koyu renkler</option>
                <option value="specific">Belirli renkler</option>
                <option value="exclude">Belirli renkler hariç</option>
              </select>
              {form.color_policy === "specific" && (
                <input
                  className="input-dark mt-2"
                  placeholder="Siyah, lacivert"
                  value={form.allowed_colors}
                  onChange={(event) => setForm({ ...form, allowed_colors: event.target.value })}
                />
              )}
              {form.color_policy === "exclude" && (
                <input
                  className="input-dark mt-2"
                  placeholder="Beyaz, pembe"
                  value={form.excluded_colors}
                  onChange={(event) => setForm({ ...form, excluded_colors: event.target.value })}
                />
              )}
            </div>
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Keşif sıklığı</label>
              <select
                className="input-dark mt-1"
                value={form.discovery_frequency_hours}
                onChange={(event) => setForm({ ...form, discovery_frequency_hours: Number(event.target.value) })}
              >
                <option value={6}>6 saatte bir</option>
                <option value={12}>12 saatte bir</option>
                <option value={24}>Günde bir</option>
                <option value={48}>2 günde bir</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Asgari indirim (%)</label>
              <input
                className="input-dark mt-1"
                type="number"
                min="0"
                max="100"
                value={form.minimum_drop_percent}
                onChange={(event) => setForm({ ...form, minimum_drop_percent: event.target.value })}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Asgari indirim (TL)</label>
              <input
                className="input-dark mt-1"
                type="number"
                min="0"
                value={form.minimum_drop_amount}
                onChange={(event) => setForm({ ...form, minimum_drop_amount: event.target.value })}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">İlan yenileme sıklığı</label>
              <select
                className="input-dark mt-1"
                value={form.refresh_frequency_minutes}
                onChange={(event) => setForm({ ...form, refresh_frequency_minutes: Number(event.target.value) })}
              >
                <option value={30}>30 dakikada bir</option>
                <option value={60}>Saatte bir</option>
                <option value={180}>3 saatte bir</option>
                <option value={360}>6 saatte bir</option>
                <option value={720}>12 saatte bir</option>
                <option value={1440}>Günde bir</option>
              </select>
            </div>
          </div>

          <details className="border-y border-zinc-800 py-3">
            <summary className="cursor-pointer text-xs text-zinc-400 uppercase tracking-wider">Eşleştirme koşulları</summary>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
              <div>
                <label className="text-xs text-zinc-500 uppercase tracking-wider">Zorunlu belirteçler</label>
                <input
                  className="input-dark mt-1"
                  placeholder="GTX, GTS, v14"
                  value={form.required_tokens}
                  onChange={(event) => setForm({ ...form, required_tokens: event.target.value })}
                />
              </div>
              <div>
                <label className="text-xs text-zinc-500 uppercase tracking-wider">İstenmeyen belirteçler</label>
                <input
                  className="input-dark mt-1"
                  placeholder="Kids, Wide, Max"
                  value={form.excluded_tokens}
                  onChange={(event) => setForm({ ...form, excluded_tokens: event.target.value })}
                />
              </div>
            </div>
          </details>

          <div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Mağazalar</div>
            <div className="flex flex-wrap gap-2">
              {stores.map((store) => (
                <label key={store.slug} className="flex items-center gap-2 border border-zinc-800 rounded px-2.5 py-1.5 text-xs cursor-pointer">
                  <input type="checkbox" checked={selectedStores.has(store.slug)} onChange={() => toggleStore(store.slug)} />
                  {store.name}
                </label>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Vazgeç</button>
            <button className="btn-primary flex items-center gap-2" disabled={busy || !form.raw_query.trim()}>
              {busy && <CircleNotch size={16} className="animate-spin" />} Radarı Başlat
            </button>
          </div>
        </form>
      )}

      {watches.length === 0 ? (
        <div className="border-y border-zinc-800 py-16 text-center text-zinc-500">
          <Crosshair size={32} className="mx-auto mb-3" />
          Henüz ürün radarı yok.
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {watches.map((watch) => {
            const listingCount = watch.listing_count_rows?.[0]?.count || 0;
            return (
              <div key={watch.id} className="card p-5 space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <button className="text-left min-w-0" onClick={() => openDetail(watch)}>
                    <div className="font-heading font-semibold truncate">{watch.raw_query}</div>
                    <div className="text-xs text-zinc-500 mt-1">
                      {watch.desired_sizes?.length ? `Beden ${watch.desired_sizes.join(", ")}` : "Tüm bedenler"}
                      {watch.target_price ? ` · Hedef ${fmtPrice(watch.target_price)}` : ""}
                    </div>
                  </button>
                  <span className={watch.active ? "badge-stock" : "badge-nostock"}>{watch.active ? "Aktif" : "Duraklatıldı"}</span>
                </div>

                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="border-y border-zinc-800 py-2">
                    <div className="font-mono text-primary">{listingCount}</div>
                    <div className="text-[10px] text-zinc-500 uppercase">Bağlı ilan</div>
                  </div>
                  <div className="border-y border-zinc-800 py-2">
                    <div className="font-mono text-yellow-300">{candidateCount(watch, "review")}</div>
                    <div className="text-[10px] text-zinc-500 uppercase">İnceleme</div>
                  </div>
                  <div className="border-y border-zinc-800 py-2">
                    <div className="font-mono">{candidateCount(watch, "rejected")}</div>
                    <div className="text-[10px] text-zinc-500 uppercase">Reddedilen</div>
                  </div>
                </div>

                <div className="text-xs text-zinc-500">Son keşif: {fmtDate(watch.last_discovery_at)} · Sıradaki: {fmtDate(watch.next_discovery_at)}</div>
                <div className="flex gap-2">
                  <button className="btn-secondary flex-1 flex items-center justify-center gap-2" onClick={() => run(watch)} disabled={activeAction === `run-${watch.id}`}>
                    {activeAction === `run-${watch.id}` ? <CircleNotch size={15} className="animate-spin" /> : <Play size={15} />} Şimdi Tara
                  </button>
                  <button className="h-9 w-9 border border-zinc-800 rounded flex items-center justify-center" onClick={() => toggle(watch)} title={watch.active ? "Duraklat" : "Etkinleştir"}>
                    {watch.active ? <Pause size={15} /> : <Play size={15} />}
                  </button>
                  <button className="h-9 w-9 border border-zinc-800 rounded flex items-center justify-center text-zinc-500 hover:text-red-400" onClick={() => remove(watch)} title="Sil">
                    <Trash size={15} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {detail && (
        <div className="border-t border-zinc-800 pt-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-primary uppercase tracking-wider font-mono">Eşleşme İncelemesi</div>
              <h2 className="font-heading font-semibold text-xl mt-1">{detail.watch.raw_query}</h2>
            </div>
            <button className="h-9 w-9 border border-zinc-800 rounded flex items-center justify-center" onClick={() => setDetail(null)} title="Kapat"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {detail.candidates.filter((candidate) => candidate.status === "review").map((candidate) => (
              <div key={candidate.id} className="card p-4 flex gap-3">
                {candidate.image && <img src={candidate.image} alt="" className="h-20 w-20 object-cover rounded" />}
                <div className="min-w-0 flex-1">
                  <a href={candidate.url} target="_blank" rel="noreferrer" className="text-sm font-medium line-clamp-2 hover:text-primary">{candidate.title}</a>
                  <div className="text-xs text-zinc-500 mt-1">{candidate.store} · %{Math.round((candidate.confidence || 0) * 100)} güven</div>
                  <div className="flex flex-wrap gap-2 mt-3">
                    <button className="btn-primary !py-1.5 flex items-center gap-1" onClick={() => review(candidate, "approve")} disabled={activeAction === `review-${candidate.id}`}><Check size={14} /> Doğru</button>
                    <button className="btn-secondary !py-1.5" onClick={() => review(candidate, "variant")} disabled={activeAction === `review-${candidate.id}`}>Farklı varyant</button>
                    <button className="btn-secondary !py-1.5" onClick={() => review(candidate, "same_family")} disabled={activeAction === `review-${candidate.id}`}>Aynı aile</button>
                    <button className="btn-secondary !py-1.5 flex items-center gap-1" onClick={() => review(candidate, "reject")} disabled={activeAction === `review-${candidate.id}`}><X size={14} /> Yanlış</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {detail.candidates.every((candidate) => candidate.status !== "review") && (
            <div className="text-sm text-zinc-500 border-y border-zinc-800 py-6">İncelenecek orta güvenli eşleşme yok.</div>
          )}
        </div>
      )}
    </div>
  );
}
