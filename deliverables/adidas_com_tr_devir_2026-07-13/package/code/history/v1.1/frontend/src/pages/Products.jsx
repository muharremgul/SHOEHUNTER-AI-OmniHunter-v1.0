import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Plus, LinkSimple, CircleNotch, Trash } from "@phosphor-icons/react";
import api, { fmtPrice } from "../api";

const PLACEHOLDER = "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?crop=entropy&cs=srgb&fm=jpg&w=600";

export default function Products() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showQuick, setShowQuick] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [quickUrl, setQuickUrl] = useState("");
  const [manual, setManual] = useState({ name: "", brand: "", model: "", url: "" });
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.get("/products").then((r) => {
      const sorted = r.data
        .filter((p) => p.in_stock)
        .sort((a, b) => {
          const priceA = a.best_price ?? Number.POSITIVE_INFINITY;
          const priceB = b.best_price ?? Number.POSITIVE_INFINITY;
          return priceA - priceB;
        });
      setProducts(sorted);
      setLoading(false);
    });

  useEffect(() => {
    load();
  }, []);

  const addQuick = async () => {
    if (!quickUrl.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.post("/track/quick", { url: quickUrl.trim() });
      toast.success(`Eklendi: ${data.product.name}`);
      setQuickUrl("");
      setShowQuick(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Link okunamadı");
    } finally {
      setBusy(false);
    }
  };

  const addManual = async () => {
    if (!manual.name.trim()) return;
    setBusy(true);
    try {
      await api.post("/products", manual);
      toast.success("Ürün eklendi");
      setManual({ name: "", brand: "", model: "", url: "" });
      setShowManual(false);
      load();
    } catch (e) {
      toast.error("Ürün eklenemedi");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (e, id) => {
    e.preventDefault();
    if (!window.confirm("Bu ürün ve tüm linkleri silinecek. Emin misiniz?")) return;
    await api.delete(`/products/${id}`);
    toast.success("Ürün silindi");
    load();
  };

  return (
    <div className="space-y-6" data-testid="products-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Takip Listesi</div>
          <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">Ürünler</h1>
        </div>
        <div className="flex gap-3">
          <button data-testid="add-quick-button" className="btn-primary flex items-center gap-2" onClick={() => { setShowQuick(!showQuick); setShowManual(false); }}>
            <LinkSimple size={16} /> Link ile Ekle
          </button>
          <button data-testid="add-manual-button" className="btn-secondary flex items-center gap-2" onClick={() => { setShowManual(!showManual); setShowQuick(false); }}>
            <Plus size={16} /> Manuel Ekle
          </button>
        </div>
      </div>

      {showQuick && (
        <div className="card p-5 animate-fadeUp">
          <div className="text-sm text-zinc-400 mb-2">Ürün linkini yapıştırın — mağaza otomatik algılanır, fiyat ve bedenler hemen okunur.</div>
          <div className="flex gap-3">
            <input
              data-testid="quick-url-input"
              className="input-dark"
              placeholder="https://www.intersport.com.tr/brooks-glycerin-22..."
              value={quickUrl}
              onChange={(e) => setQuickUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addQuick()}
            />
            <button data-testid="quick-url-submit" className="btn-primary shrink-0 flex items-center gap-2" onClick={addQuick} disabled={busy}>
              {busy && <CircleNotch size={16} className="animate-spin" />} {busy ? "Okunuyor..." : "Ekle ve Tara"}
            </button>
          </div>
        </div>
      )}

      {showManual && (
        <div className="card p-5 animate-fadeUp space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input data-testid="manual-name-input" className="input-dark" placeholder="Ürün adı * (örn: Brooks Glycerin 22)" value={manual.name} onChange={(e) => setManual({ ...manual, name: e.target.value })} />
            <input data-testid="manual-brand-input" className="input-dark" placeholder="Marka" value={manual.brand} onChange={(e) => setManual({ ...manual, brand: e.target.value })} />
            <input data-testid="manual-model-input" className="input-dark" placeholder="Model" value={manual.model} onChange={(e) => setManual({ ...manual, model: e.target.value })} />
          </div>
          <div className="flex gap-3">
            <input data-testid="manual-url-input" className="input-dark" placeholder="Ürün linki (opsiyonel) — https://www.adidas.com.tr/..." value={manual.url} onChange={(e) => setManual({ ...manual, url: e.target.value })} />
            <button data-testid="manual-submit" className="btn-primary shrink-0 flex items-center gap-2" onClick={addManual} disabled={busy}>
              {busy && <CircleNotch size={16} className="animate-spin" />} {busy ? "Ekleniyor..." : "Kaydet"}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-zinc-500 font-mono text-sm">Yükleniyor...</div>
      ) : products.length === 0 ? (
        <div className="card p-12 text-center">
          <div className="text-zinc-400 font-heading text-lg">Stokta ürün yok</div>
          <div className="text-zinc-500 text-sm mt-2">Takipteki ürünler tekrar stoğa girince burada otomatik görünür.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {products.map((p, i) => (
              <Link
              key={p.id}
              to={`/urunler/${p.id}`}
              data-testid={`product-card-${p.id}`}
              className={`card overflow-hidden hover:border-primary/40 hover:-translate-y-0.5 transition-all duration-200 animate-fadeUp group ${!p.in_stock ? 'opacity-60 grayscale-[40%]' : ''}`}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="h-40 bg-zinc-900 overflow-hidden relative">
                <img src={p.image || PLACEHOLDER} alt={p.name} className="w-full h-full object-cover opacity-90 group-hover:scale-105 transition-transform duration-300" onError={(e) => { e.target.src = PLACEHOLDER; }} />
                <button onClick={(e) => remove(e, p.id)} data-testid={`delete-product-${p.id}`} className="absolute top-2 right-2 bg-black/60 backdrop-blur p-1.5 rounded text-zinc-400 hover:text-red-400 transition-colors">
                  <Trash size={14} />
                </button>
              </div>
              <div className="p-4">
                <div className="font-medium text-sm truncate">{p.name}</div>
                <div className="text-xs text-zinc-500 mt-0.5">{p.brand || "—"} · {p.listing_count} link</div>
                
                {/* Beden Rozetleri */}
                {p.in_stock && p.available_sizes?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2.5">
                    {p.available_sizes.slice(0, 5).map(sz => (
                      <span key={sz} className="text-[10px] bg-zinc-800 text-zinc-300 px-1.5 py-0.5 rounded border border-zinc-700 font-mono">
                        {sz}
                      </span>
                    ))}
                    {p.available_sizes.length > 5 && (
                      <span className="text-[10px] bg-zinc-800/50 text-zinc-500 px-1.5 py-0.5 rounded font-mono border border-zinc-800">
                        +{p.available_sizes.length - 5}
                      </span>
                    )}
                  </div>
                )}

                <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/5">
                  <div>
                    <div className="text-primary font-mono font-bold">{fmtPrice(p.best_price)}</div>
                    {p.target_price && <div className="text-xs text-zinc-500">Hedef: {fmtPrice(p.target_price)}</div>}
                  </div>
                  <span className={p.in_stock ? "badge-stock" : "badge-nostock"}>
                    {p.in_stock ? "Stokta" : "Stok Yok"}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
