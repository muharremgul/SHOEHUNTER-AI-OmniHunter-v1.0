import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Barcode,
  Camera,
  Check,
  CircleNotch,
  Crosshair,
  ArrowCounterClockwise,
  ArrowClockwise,
  Pause,
  Play,
  Plus,
  Trash,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import api, { fmtDate, fmtPrice } from "../api";


const EMPTY_FORM = {
  raw_query: "",
  desired_sizes: "",
  category: "shoes",
  profile_preference_ids: [],
  target_price: "",
  minimum_drop_percent: "",
  minimum_drop_amount: "",
  gender: "",
  color_policy: "any",
  allowed_colors: "",
  excluded_colors: "",
  required_tokens: "",
  excluded_tokens: "",
  discovery_frequency_hours: 6,
  refresh_frequency_minutes: 360,
  store_scope: [],
  brand: null,
  model: null,
  input_origin: "manual",
  source_identifiers: {},
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

export function storeSlugs(storeRows) {
  return (storeRows || []).map((store) => store.slug);
}

export function toggleStoreScope(scope, slug) {
  const next = new Set(scope || []);
  if (next.has(slug)) next.delete(slug);
  else next.add(slug);
  return [...next];
}

export function togglePreferenceSelection(selection, preferenceId) {
  const next = new Set(selection || []);
  if (next.has(preferenceId)) next.delete(preferenceId);
  else next.add(preferenceId);
  return [...next];
}

export function applyLabelSuggestion(current, result) {
  const suggestion = result?.suggested_watch || {};
  const nextCategory = suggestion.category || current.category;
  return {
    ...current,
    raw_query: suggestion.raw_query || current.raw_query,
    desired_sizes: (suggestion.desired_sizes || []).join(", "),
    category: nextCategory,
    target_price: suggestion.target_price || "",
    brand: suggestion.brand || null,
    model: suggestion.model || null,
    input_origin: "label_scan",
    source_identifiers: suggestion.source_identifiers || {},
    profile_preference_ids: nextCategory === current.category ? current.profile_preference_ids : [],
  };
}

function normalizedOcrText(value) {
  return String(value || "").trim().replace(/\s+/g, " ");
}

export function recommendedOcrSelection(result) {
  const evidence = [
    result?.brand,
    ...(result?.product_codes || []),
    ...(result?.descriptive_lines || []),
  ].map((item) => normalizedOcrText(item).toLocaleLowerCase("tr-TR")).filter(Boolean);
  return (result?.text_blocks || [])
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => {
      const text = normalizedOcrText(item?.text).toLocaleLowerCase("tr-TR");
      return text && evidence.some((value) => text.includes(value) || value.includes(text));
    })
    .map(({ index }) => index);
}

export function buildSelectedOcrQuery(result, selectedIndexes) {
  const selected = new Set(selectedIndexes || []);
  const seen = new Set();
  const parts = [];
  (result?.text_blocks || []).forEach((item, index) => {
    if (!selected.has(index)) return;
    const text = normalizedOcrText(item?.text);
    const key = text.toLocaleLowerCase("tr-TR");
    if (!text || seen.has(key)) return;
    seen.add(key);
    parts.push(text);
  });
  return parts.join(" ").slice(0, 300).trim();
}

export function allOcrSelection(result) {
  return (result?.text_blocks || [])
    .map((item, index) => (normalizedOcrText(item?.text) ? index : null))
    .filter((index) => index !== null);
}

function queryContainsEvidence(query, value) {
  const normalizedQuery = normalizedOcrText(query).toLocaleLowerCase("tr-TR");
  const normalizedValue = normalizedOcrText(value).toLocaleLowerCase("tr-TR");
  return Boolean(normalizedValue && normalizedQuery.includes(normalizedValue));
}

export function applySelectedOcrSuggestion(current, result, selectedIndexes) {
  const query = buildSelectedOcrQuery(result, selectedIndexes);
  if (!query) return current;

  const suggestion = result?.suggested_watch || {};
  // Always pick the first recognized product code — even if the user's OCR box
  // selection does not literally contain the code text.  The label scanner
  // already confirmed it structurally; losing it silently was the root bug.
  const selectedProductCode = (result?.product_codes || []).find((code) => queryContainsEvidence(query, code));
  const anyProductCode = selectedProductCode || (result?.product_codes || [])[0] || null;
  // Brand is always kept when the scanner found one.  Requiring it to appear
  // inside the concatenated query text dropped it for multi-box selections.
  const brand = result?.brand || null;
  const sourceIdentifiers = {};

  // A decoder-confirmed barcode/QR remains trustworthy even when the user is
  // choosing only the OCR words.
  if (suggestion.source_identifiers?.barcode) {
    sourceIdentifiers.barcode = suggestion.source_identifiers.barcode;
  }
  if (suggestion.source_identifiers?.qr) {
    sourceIdentifiers.qr = suggestion.source_identifiers.qr;
  }
  if (anyProductCode) sourceIdentifiers.product_code = anyProductCode;
  // Carry over any GTIN the scanner extracted so the search plan can use it.
  if (suggestion.source_identifiers?.gtin) {
    sourceIdentifiers.gtin = suggestion.source_identifiers.gtin;
  }
  if (suggestion.source_identifiers?.style_code) {
    sourceIdentifiers.style_code = suggestion.source_identifiers.style_code;
  }

  return {
    ...applyLabelSuggestion(current, result),
    raw_query: query,
    brand,
    model: anyProductCode,
    input_origin: "label_scan",
    source_identifiers: sourceIdentifiers,
  };
}

export function rotationCanvasGeometry(width, height, direction) {
  const sourceWidth = Math.max(1, Number(width) || 1);
  const sourceHeight = Math.max(1, Number(height) || 1);
  const quarterTurn = direction < 0 ? -1 : 1;
  return {
    width: sourceHeight,
    height: sourceWidth,
    radians: quarterTurn * Math.PI / 2,
  };
}

function rotateImageFile(file, direction) {
  return new Promise((resolve, reject) => {
    const sourceUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      try {
        const geometry = rotationCanvasGeometry(image.naturalWidth, image.naturalHeight, direction);
        const canvas = document.createElement("canvas");
        canvas.width = geometry.width;
        canvas.height = geometry.height;
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Canvas kullanilamiyor");
        context.translate(canvas.width / 2, canvas.height / 2);
        context.rotate(geometry.radians);
        context.drawImage(image, -image.naturalWidth / 2, -image.naturalHeight / 2);
        canvas.toBlob((blob) => {
          URL.revokeObjectURL(sourceUrl);
          if (!blob) {
            reject(new Error("Dondurulen fotograf olusturulamadi"));
            return;
          }
          resolve(new File([blob], file.name, { type: blob.type || file.type, lastModified: Date.now() }));
        }, file.type === "image/png" ? "image/png" : "image/jpeg", 0.94);
      } catch (error) {
        URL.revokeObjectURL(sourceUrl);
        reject(error);
      }
    };
    image.onerror = () => {
      URL.revokeObjectURL(sourceUrl);
      reject(new Error("Fotograf dondurmek icin acilamadi"));
    };
    image.src = sourceUrl;
  });
}

export function ocrOverlayStyle(block) {
  const polygon = block?.polygon_norm;
  if (!Array.isArray(polygon) || polygon.length < 3) return null;
  const xs = polygon.map((point) => Number(point?.[0])).filter(Number.isFinite);
  const ys = polygon.map((point) => Number(point?.[1])).filter(Number.isFinite);
  if (xs.length < 3 || ys.length < 3) return null;
  const left = Math.max(0, Math.min(...xs));
  const top = Math.max(0, Math.min(...ys));
  const right = Math.min(1, Math.max(...xs));
  const bottom = Math.min(1, Math.max(...ys));
  if (right <= left || bottom <= top) return null;
  const percent = (value) => `${Math.round(value * 10000) / 100}%`;
  return {
    left: percent(left),
    top: percent(top),
    width: percent(right - left),
    height: percent(bottom - top),
  };
}

export function nativeBarcodeSuggestion(payload) {
  const value = normalizedOcrText(payload?.value);
  if (!value) return null;
  const isBarcode = /^\d{8}$|^\d{12,14}$/.test(value);
  const isUrl = /^https?:\/\//i.test(value);
  const identifiers = isBarcode
    ? { barcode: value }
    : isUrl
      ? { qr: value }
      : { product_code: value };
  return {
    raw_query: value,
    model: isBarcode || isUrl ? null : value,
    input_origin: "label_scan",
    source_identifiers: identifiers,
  };
}

export function nativeOcrSuggestion(payload) {
  const selectedText = normalizedOcrText(
    payload?.selected_text
      || payload?.query
      || payload?.raw_query
      || (payload?.text_blocks || []).map((item) => item?.text).filter(Boolean).join(" ")
  ).slice(0, 160);
  if (!selectedText) return null;

  const productCode = (payload?.product_codes || []).find((code) => (
    queryContainsEvidence(selectedText, code)
  ));
  const brand = payload?.brand && queryContainsEvidence(selectedText, payload.brand)
    ? payload.brand
    : null;
  return {
    raw_query: selectedText,
    brand,
    model: productCode || null,
    input_origin: "label_scan",
    source_identifiers: productCode ? { product_code: productCode } : {},
  };
}

export function scanCoverage(summary) {
  const selected = Number(summary?.selected_store_count || summary?.stores?.length || 0);
  const storeList = summary?.stores || [];
  const deferred = Number(
    summary?.deferred_store_count
      ?? storeList.filter((item) => item.status === "deferred").length
  );
  const blocked = storeList.filter((item) => item.status === "blocked").length;
  const timedOut = storeList.filter((item) => item.status === "timeout").length;
  const parserFail = storeList.filter((item) => item.status === "parser_failure").length;
  const otherError = storeList.filter((item) => item.status === "error").length;
  const failed = Number(
    summary?.failed_store_count
      ?? (blocked + timedOut + parserFail + otherError)
  );
  const searched = Number(summary?.searched_store_count ?? Math.max(0, selected - deferred));
  return { selected, searched, deferred, failed, blocked, timedOut, parserFail, otherError };
}

export default function ProductRadar() {
  const [watches, setWatches] = useState([]);
  const [stores, setStores] = useState([]);
  const [profile, setProfile] = useState({ household_members: [] });
  const [form, setForm] = useState(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [activeAction, setActiveAction] = useState(null);
  const [detail, setDetail] = useState(null);
  const [storeSelectionInitialized, setStoreSelectionInitialized] = useState(false);
  const [scanBusy, setScanBusy] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [scanPreview, setScanPreview] = useState(null);
  const [selectedOcrBlocks, setSelectedOcrBlocks] = useState([]);
  const scanInputRef = useRef(null);
  const scanFileRef = useRef(null);

  const load = async () => {
    const [{ data: watchRows }, { data: storeRows }, { data: profileData }] = await Promise.all([
      api.get("/watches"),
      api.get("/stores"),
      api.get("/profile"),
    ]);
    setWatches(watchRows);
    setStores(storeRows.filter((store) => store.searchable));
    setProfile(profileData || { household_members: [] });
  };

  useEffect(() => {
    load().catch((error) => toast.error(error.response?.data?.detail || "Ürün radarları yüklenemedi"));
  }, []);

  useEffect(() => {
    const receiveNativeScan = (event) => {
      const suggestion = nativeBarcodeSuggestion(event?.detail);
      if (!suggestion) return;
      setShowForm(true);
      setForm((current) => ({ ...current, ...suggestion }));
      toast.success("Barkod okundu; Radar mağaza taramasına hazır");
    };
    window.addEventListener("shoehunter:native-scan", receiveNativeScan);
    try {
      const stored = window.sessionStorage.getItem("shoehunterNativeScan");
      if (stored) {
        window.sessionStorage.removeItem("shoehunterNativeScan");
        receiveNativeScan({ detail: JSON.parse(stored) });
      }
    } catch {
      window.sessionStorage.removeItem("shoehunterNativeScan");
    }
    return () => window.removeEventListener("shoehunter:native-scan", receiveNativeScan);
  }, []);

  useEffect(() => {
    const receiveNativeOcr = (event) => {
      const suggestion = nativeOcrSuggestion(event?.detail);
      if (!suggestion) return;
      setShowForm(true);
      setForm((current) => ({ ...current, ...suggestion }));
      toast.success("Seçtiğiniz kamera yazıları Radar sorgusuna aktarıldı");
    };
    window.addEventListener("shoehunter:native-ocr", receiveNativeOcr);
    try {
      const stored = window.sessionStorage.getItem("shoehunterNativeOcr");
      if (stored) {
        window.sessionStorage.removeItem("shoehunterNativeOcr");
        receiveNativeOcr({ detail: JSON.parse(stored) });
      }
    } catch {
      window.sessionStorage.removeItem("shoehunterNativeOcr");
    }
    return () => window.removeEventListener("shoehunter:native-ocr", receiveNativeOcr);
  }, []);

  const allStoreSlugs = useMemo(() => storeSlugs(stores), [stores]);
  const selectedStores = useMemo(() => new Set(form.store_scope), [form.store_scope]);
  const selectedStoreCount = useMemo(
    () => allStoreSlugs.filter((slug) => selectedStores.has(slug)).length,
    [allStoreSlugs, selectedStores]
  );
  const allStoresSelected = stores.length > 0 && selectedStoreCount === stores.length;
  const profilePreferences = useMemo(() => (
    (profile.household_members || []).flatMap((member) => (
      (member.preferences || []).map((preference) => ({ ...preference, member }))
    ))
  ), [profile]);
  const categoryPreferences = useMemo(
    () => profilePreferences.filter((preference) => preference.category === form.category),
    [profilePreferences, form.category]
  );
  const detailLatestRun = detail?.runs?.[0] || detail?.watch?.last_run_summary || null;
  const detailCoverage = scanCoverage(detailLatestRun);

  useEffect(() => {
    if (storeSelectionInitialized || allStoreSlugs.length === 0) return;
    setForm((current) => ({
      ...current,
      store_scope: current.store_scope.length > 0 ? current.store_scope : [...allStoreSlugs],
    }));
    setStoreSelectionInitialized(true);
  }, [allStoreSlugs, storeSelectionInitialized]);

  const toggleStore = (slug) => {
    setForm((current) => ({
      ...current,
      store_scope: toggleStoreScope(current.store_scope, slug),
    }));
  };

  const selectAllStores = () => {
    setForm((current) => ({ ...current, store_scope: [...allStoreSlugs] }));
  };

  const clearStores = () => {
    setForm((current) => ({ ...current, store_scope: [] }));
  };

  const togglePreference = (preferenceId) => {
    setForm((current) => ({
      ...current,
      profile_preference_ids: togglePreferenceSelection(current.profile_preference_ids, preferenceId),
    }));
  };

  const clearScan = () => {
    if (scanPreview) URL.revokeObjectURL(scanPreview);
    setScanPreview(null);
    setScanResult(null);
    setSelectedOcrBlocks([]);
    scanFileRef.current = null;
    if (scanInputRef.current) scanInputRef.current.value = "";
  };

  const submitLabelFile = async (file, successMessage) => {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) {
      toast.error("Fotoğraf en fazla 12 MB olabilir");
      return;
    }
    if (scanPreview) URL.revokeObjectURL(scanPreview);
    scanFileRef.current = file;
    setScanPreview(URL.createObjectURL(file));
    setScanResult(null);
    setSelectedOcrBlocks([]);
    setShowForm(true);
    setScanBusy(true);
    try {
      const payload = new FormData();
      payload.append("image", file);
      const { data } = await api.post("/radar/scan-label", payload);
      setScanResult(data);
      setSelectedOcrBlocks(recommendedOcrSelection(data));
      toast.success(successMessage || "Etiket okundu; bilgileri kontrol edip Radar alanlarına aktarın");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Fotoğraf okunamadı");
    } finally {
      setScanBusy(false);
    }
  };

  const scanLabel = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await submitLabelFile(file);
    event.target.value = "";
  };

  const rotateScan = async (direction) => {
    if (!scanFileRef.current || scanBusy) return;
    setScanBusy(true);
    try {
      const rotated = await rotateImageFile(scanFileRef.current, direction);
      await submitLabelFile(rotated, "Fotoğrafın yönü düzeltildi ve metin yeniden okundu");
    } catch {
      toast.error("Fotoğrafın yönü düzeltilemedi");
    } finally {
      setScanBusy(false);
    }
  };

  const useScanResult = () => {
    setForm((current) => applyLabelSuggestion(current, scanResult));
    toast.success("Okunan bilgiler Radar formuna aktarıldı");
  };

  const toggleOcrBlock = (index) => {
    setSelectedOcrBlocks((current) => (
      current.includes(index) ? current.filter((item) => item !== index) : [...current, index]
    ));
  };

  const useSelectedOcr = () => {
    const query = buildSelectedOcrQuery(scanResult, selectedOcrBlocks);
    if (!query) {
      toast.error("Arama için en az bir OCR satırı seçin");
      return;
    }
    setForm((current) => applySelectedOcrSuggestion(current, scanResult, selectedOcrBlocks));
    toast.success("Seçtiğiniz yazılar Radar sorgusu olarak aktarıldı");
  };

  const create = async (event) => {
    event.preventDefault();
    if (!form.raw_query.trim() || (stores.length > 0 && selectedStoreCount === 0)) return;
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
      setForm({ ...EMPTY_FORM, store_scope: [...allStoreSlugs] });
      clearScan();
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
        <div className="flex flex-wrap gap-2">
          <input
            ref={scanInputRef}
            className="hidden"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            onChange={scanLabel}
            data-testid="label-scan-input"
          />
          <button
            type="button"
            className="btn-secondary flex items-center gap-2"
            onClick={() => scanInputRef.current?.click()}
            disabled={scanBusy}
            data-testid="label-scan-button"
          >
            {scanBusy ? <CircleNotch size={16} className="animate-spin" /> : <Camera size={16} />}
            Etiketi / Barkodu Oku
          </button>
          <button className="btn-primary flex items-center gap-2" onClick={() => setShowForm((value) => !value)}>
            <Plus size={16} /> Yeni Radar
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={create} className="border-y border-zinc-800 py-5 space-y-4 animate-fadeUp">
          {(scanPreview || scanBusy || scanResult) && (
            <section className="rounded border border-primary/30 bg-primary/5 p-4" data-testid="label-scan-review">
              <div className="flex flex-col md:flex-row gap-4">
                {scanPreview && (
                  <div
                    className="relative w-full md:w-72 shrink-0 self-start overflow-hidden rounded border border-zinc-800 bg-black/30"
                    style={{
                      aspectRatio: scanResult?.image?.width && scanResult?.image?.height
                        ? `${scanResult.image.width} / ${scanResult.image.height}`
                        : undefined,
                    }}
                    data-testid="ocr-image-overlay"
                  >
                    <img src={scanPreview} alt="Okunan ürün etiketi; bulunan yazı alanları dokunarak seçilebilir" className="block h-full w-full object-contain" />
                    <div role="group" aria-label="Fotoğraf üzerindeki seçilebilir OCR alanları">
                    {(scanResult?.text_blocks || []).map((block, index) => {
                      const style = ocrOverlayStyle(block);
                      if (!style) return null;
                      const selected = selectedOcrBlocks.includes(index);
                      return (
                        <button
                          key={`overlay-${index}-${block.text}`}
                          type="button"
                          style={style}
                          className={`absolute rounded-sm border-2 transition-colors ${
                            selected
                              ? "border-primary bg-primary/25 shadow-[0_0_0_1px_rgba(0,0,0,0.8)]"
                              : "border-sky-400/80 bg-sky-400/10 hover:bg-sky-400/25"
                          }`}
                          title={`${block.text} · OCR %${Math.round(Number(block.confidence || 0) * 100)}`}
                          aria-label={`${block.text} yazısını ${selected ? "seçimden çıkar" : "seç"}`}
                          aria-pressed={selected}
                          aria-controls="ocr-selection-status radar-product-query"
                          onClick={() => toggleOcrBlock(index)}
                        />
                      );
                    })}
                    </div>
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-2">
                        <Barcode size={16} /> Fotoğraftan ürün tanıma
                      </div>
                      <div className="text-sm text-zinc-300 mt-1">
                        {scanBusy ? "Barkod ve etiket yazısı yerel olarak okunuyor…" : "Sonucu kontrol edin; hiçbir bilgi onayınız olmadan Radar'a eklenmez."}
                      </div>
                    </div>
                    <button type="button" onClick={clearScan} className="text-zinc-500 hover:text-zinc-200" title="Fotoğrafı kaldır" aria-label="Fotoğrafı ve OCR sonucunu kaldır"><X size={17} /></button>
                  </div>

                  {scanBusy && <div className="h-1 bg-zinc-800 rounded overflow-hidden mt-4"><div className="h-full w-2/3 bg-primary animate-pulse" /></div>}

                  {scanPreview && (
                    <div className="flex flex-wrap items-center gap-2 mt-3" aria-label="Fotoğraf yönü düzeltme araçları">
                      <span className="text-[11px] text-zinc-500">Yazı ters veya yan duruyorsa:</span>
                      <button type="button" className="btn-secondary flex items-center gap-1.5" onClick={() => rotateScan(-1)} disabled={scanBusy || !scanFileRef.current} aria-label="Fotoğrafı sola döndür ve OCR'ı yeniden çalıştır">
                        <ArrowCounterClockwise size={15} /> Sola döndür
                      </button>
                      <button type="button" className="btn-secondary flex items-center gap-1.5" onClick={() => rotateScan(1)} disabled={scanBusy || !scanFileRef.current} aria-label="Fotoğrafı sağa döndür ve OCR'ı yeniden çalıştır">
                        <ArrowClockwise size={15} /> Sağa döndür
                      </button>
                    </div>
                  )}

                  {scanResult && (
                    <div className="mt-4 space-y-3">
                      <div className="text-base font-heading font-semibold">{scanResult.suggested_watch?.raw_query || "Ürün adı belirlenemedi"}</div>
                      <div className="flex flex-wrap gap-2 text-[11px]">
                        <span className="border border-zinc-700 rounded px-2 py-1">Güven %{Math.round((scanResult.confidence || 0) * 100)}</span>
                        {scanResult.brand && <span className="border border-zinc-700 rounded px-2 py-1">{scanResult.brand}</span>}
                        {(scanResult.product_codes || []).map((code) => <span key={code} className="border border-primary/40 text-primary rounded px-2 py-1">Kod {code}</span>)}
                        {(scanResult.barcodes || []).slice(0, 2).map((item) => <span key={`${item.format}-${item.value}`} className="border border-zinc-700 rounded px-2 py-1">{item.format}: {item.value}</span>)}
                        {(scanResult.sizes || []).map((size) => <span key={size} className="border border-zinc-700 rounded px-2 py-1">Beden {size}</span>)}
                        {(scanResult.prices || []).map((price) => <span key={price} className="border border-zinc-700 rounded px-2 py-1">{fmtPrice(price)}</span>)}
                      </div>
                      {(scanResult.warnings || []).map((warning) => (
                        <div key={warning} className="text-xs text-amber-300 flex items-start gap-2"><WarningCircle size={15} className="mt-0.5 shrink-0" /> {warning}</div>
                      ))}
                      <div className="flex flex-wrap gap-2">
                        <button type="button" className="btn-primary" onClick={useScanResult} disabled={!scanResult.suggested_watch?.raw_query}>
                          Bilgileri Radar Formuna Aktar
                        </button>
                        <button type="button" className="btn-secondary" onClick={useSelectedOcr} disabled={selectedOcrBlocks.length === 0}>
                          Seçilen Metni Radar'a Aktar
                        </button>
                        <button type="button" className="btn-secondary" onClick={() => scanInputRef.current?.click()}>Başka Fotoğraf Seç</button>
                      </div>
                      {(scanResult.text_blocks || []).length > 0 && (
                        <details className="rounded border border-zinc-800 bg-black/20 p-3" open>
                          <summary className="cursor-pointer text-xs font-medium text-zinc-300">
                            Lens gibi OCR yazısını seç ({selectedOcrBlocks.length} satır seçili)
                          </summary>
                          <div className="flex flex-wrap gap-2 mt-3">
                            <button
                              type="button"
                              className="text-[11px] text-primary hover:text-primary/80"
                              onClick={() => setSelectedOcrBlocks(allOcrSelection(scanResult))}
                              data-testid="ocr-select-all"
                            >
                              Tümünü seç
                            </button>
                            <button
                              type="button"
                              className="text-[11px] text-primary hover:text-primary/80"
                              onClick={() => setSelectedOcrBlocks(recommendedOcrSelection(scanResult))}
                            >
                              Önerilenleri seç
                            </button>
                            <button
                              type="button"
                              className="text-[11px] text-zinc-400 hover:text-zinc-200"
                              onClick={() => setSelectedOcrBlocks([])}
                            >
                              Seçimi temizle
                            </button>
                          </div>
                          <div id="ocr-selection-status" className="text-[11px] text-zinc-400 mt-2" aria-live="polite" aria-atomic="true">
                            {selectedOcrBlocks.length} / {(scanResult.text_blocks || []).length} metin alanı seçili.
                          </div>
                          <fieldset className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3 max-h-56 overflow-auto pr-1" data-testid="ocr-line-selector">
                            <legend className="sr-only">Radar aramasına aktarılacak OCR metinlerini seçin</legend>
                            {scanResult.text_blocks.map((block, index) => (
                              <label
                                key={`${index}-${block.text}`}
                                className={`flex items-start gap-2 rounded border px-2.5 py-2 text-xs cursor-pointer ${
                                  selectedOcrBlocks.includes(index)
                                    ? "border-primary/50 bg-primary/10 text-zinc-100"
                                    : "border-zinc-800 text-zinc-500"
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  className="mt-0.5"
                                  checked={selectedOcrBlocks.includes(index)}
                                  onChange={() => toggleOcrBlock(index)}
                                  aria-label={`${block.text}; OCR güveni yüzde ${Math.round(Number(block.confidence || 0) * 100)}`}
                                />
                                <span className="min-w-0">
                                  <span className="break-words">{block.text}</span>
                                  <span className="block text-[9px] text-zinc-600 mt-0.5">
                                    OCR güveni %{Math.round(Number(block.confidence || 0) * 100)}
                                  </span>
                                </span>
                              </label>
                            ))}
                          </fieldset>
                          <div className="text-[10px] text-zinc-600 mt-2">
                            Ürün adı, marka veya kod satırlarını seçin. Beden ve fiyatı sorgu başlığına eklemek zorunda değilsiniz.
                          </div>
                        </details>
                      )}
                      <details className="text-xs text-zinc-500">
                        <summary className="cursor-pointer">Okunan bütün yazıyı göster</summary>
                        <pre className="mt-2 p-3 bg-black/30 rounded whitespace-pre-wrap break-words max-h-44 overflow-auto">{scanResult.raw_text}</pre>
                      </details>
                      <div className="text-[10px] text-zinc-600">Fotoğraf yalnızca bellekte işlenir, sunucuya kaydedilmez ve ücretli OCR API'sine gönderilmez.</div>
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr_1fr_1fr] gap-3">
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
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Ürün sınıfı</label>
              <select
                className="input-dark mt-1"
                value={form.category}
                onChange={(event) => setForm({
                  ...form,
                  category: event.target.value,
                  profile_preference_ids: [],
                })}
              >
                <option value="shoes">Ayakkabı</option>
                <option value="tops">Tişört / Üst giyim</option>
                <option value="pants">Pantolon</option>
                <option value="outerwear">Dış giyim</option>
                <option value="kids">Çocuk giyim</option>
                <option value="other">Diğer</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">Ek bedenler</label>
              <input
                className="input-dark mt-1"
                placeholder={form.category === "shoes" ? "43 1/3, 44" : form.category === "pants" ? "32/32, 34/32" : "M, L"}
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

          <div className="border-y border-zinc-800 py-3">
            <div className="text-xs text-zinc-500 uppercase tracking-wider">Kim için / kayıtlı beden profilleri</div>
            {categoryPreferences.length === 0 ? (
              <div className="text-xs text-zinc-600 mt-2">
                Bu ürün sınıfı için kayıtlı aile bedeni yok. Profil sayfasından ekleyebilir veya yukarıya bedenleri elle yazabilirsiniz.
              </div>
            ) : (
              <div className="flex flex-wrap gap-2 mt-2" data-testid="radar-profile-preferences">
                {categoryPreferences.map((preference) => {
                  const checked = form.profile_preference_ids.includes(preference.id);
                  return (
                    <label
                      key={preference.id}
                      className={`flex items-center gap-2 border rounded px-3 py-2 text-xs cursor-pointer ${
                        checked ? "border-primary/50 bg-primary/5 text-zinc-200" : "border-zinc-800 text-zinc-500"
                      }`}
                    >
                      <input type="checkbox" checked={checked} onChange={() => togglePreference(preference.id)} />
                      <span>
                        <span className="font-medium">{preference.member.name}</span>
                        <span className="text-zinc-600"> · </span>
                        {(preference.sizes || []).join(", ")} ({preference.size_system})
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
            {form.profile_preference_ids.length > 0 && (
              <div className="text-[11px] text-primary mt-2">
                Seçilen kişilerin tüm alternatif bedenleri Radar tarafından birlikte izlenecek.
              </div>
            )}
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
                  id="radar-product-query"
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
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div>
                <div className="text-xs text-zinc-500 uppercase tracking-wider">Mağazalar</div>
                <div className="text-[11px] text-zinc-600 mt-1">
                  {stores.length > 0 ? `${selectedStoreCount}/${stores.length} mağaza seçili` : "Aranabilir mağaza bulunamadı"}
                </div>
              </div>
              {stores.length > 0 && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="text-xs text-primary hover:text-primary/80 disabled:text-zinc-700 disabled:cursor-not-allowed"
                    onClick={selectAllStores}
                    disabled={allStoresSelected}
                  >
                    Tümünü seç
                  </button>
                  <span className="text-zinc-800" aria-hidden="true">•</span>
                  <button
                    type="button"
                    className="text-xs text-zinc-400 hover:text-zinc-200 disabled:text-zinc-700 disabled:cursor-not-allowed"
                    onClick={clearStores}
                    disabled={selectedStoreCount === 0}
                  >
                    Temizle
                  </button>
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Taranacak mağazalar">
              {stores.map((store) => (
                <label
                  key={store.slug}
                  className={`flex items-center gap-2 border rounded px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
                    selectedStores.has(store.slug)
                      ? "border-primary/50 bg-primary/5 text-zinc-200"
                      : "border-zinc-800 text-zinc-500"
                  }`}
                >
                  <input type="checkbox" checked={selectedStores.has(store.slug)} onChange={() => toggleStore(store.slug)} />
                  {store.name}
                </label>
              ))}
            </div>
            {stores.length > 0 && selectedStoreCount === 0 && (
              <div className="text-xs text-amber-300 mt-2" role="alert">Radarı başlatmak için en az bir mağaza seçin.</div>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => { setShowForm(false); clearScan(); }}>Vazgeç</button>
            <button
              className="btn-primary flex items-center gap-2"
              disabled={busy || !form.raw_query.trim() || (stores.length > 0 && selectedStoreCount === 0)}
            >
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
            const audienceNames = [...new Set((watch.size_preferences || []).map((item) => item.member_name).filter(Boolean))];
            const coverage = scanCoverage(watch.last_run_summary);
            const hasRunCoverage = coverage.selected > 0;
            const incompleteRun = coverage.deferred > 0 || coverage.failed > 0;
            return (
              <div key={watch.id} className="card p-5 space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <button className="text-left min-w-0" onClick={() => openDetail(watch)}>
                    <div className="font-heading font-semibold truncate flex items-center gap-2">
                      <span className="truncate">{watch.raw_query}</span>
                      {watch.input_origin === "label_scan" && <span className="shrink-0 text-[9px] uppercase tracking-wider text-primary border border-primary/30 rounded px-1.5 py-0.5">Etiketten</span>}
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">
                      {watch.desired_sizes?.length ? `Beden ${watch.desired_sizes.join(", ")}` : "Tüm bedenler"}
                      {watch.target_price ? ` · Hedef ${fmtPrice(watch.target_price)}` : ""}
                    </div>
                    {audienceNames.length > 0 && (
                      <div className="text-[11px] text-primary mt-1">Kimin için: {audienceNames.join(", ")}</div>
                    )}
                  </button>
                  <span className={watch.active ? "badge-stock" : "badge-nostock"}>{watch.active ? "Aktif" : "Duraklatıldı"}</span>
                </div>

                {hasRunCoverage && (
                  <div
                    className={`rounded border px-3 py-2 text-xs ${
                      incompleteRun
                        ? "border-amber-500/30 bg-amber-500/5 text-amber-200"
                        : "border-emerald-500/30 bg-emerald-500/5 text-emerald-200"
                    }`}
                    data-testid={`radar-coverage-${watch.id}`}
                  >
                    <div className="font-medium">
                      Son tarama: {coverage.searched}/{coverage.selected} mağaza çalıştı
                    </div>
                    {incompleteRun && (
                      <div className="mt-1 text-[10px] opacity-80">
                        {coverage.deferred > 0 ? `${coverage.deferred} ertelendi · ` : ""}
                        {coverage.blocked > 0 ? `${coverage.blocked} erişim engeli · ` : ""}
                        {coverage.timedOut > 0 ? `${coverage.timedOut} zaman aşımı · ` : ""}
                        {coverage.parserFail > 0 ? `${coverage.parserFail} ayrıştırma hatası · ` : ""}
                        {coverage.otherError > 0 ? `${coverage.otherError} diğer hata` : ""}
                      </div>
                    )}
                  </div>
                )}

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
          {detailLatestRun && (
            <section className="rounded border border-zinc-800 bg-black/20 p-4 space-y-3" data-testid="radar-run-evidence">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="text-xs font-medium text-zinc-200">Son tarama kanıtı</div>
                  <div className="text-[11px] text-zinc-500 mt-1">
                    {detailCoverage.searched}/{detailCoverage.selected} mağaza çalıştı
                    {detailCoverage.deferred ? ` · ${detailCoverage.deferred} ertelendi` : ""}
                    {detailCoverage.failed ? ` · ${detailCoverage.failed} hata` : ""}
                  </div>
                </div>
                <span className={`text-[10px] uppercase tracking-wider rounded border px-2 py-1 ${
                  detailLatestRun.status === "completed"
                    ? "border-emerald-500/30 text-emerald-300"
                    : "border-amber-500/30 text-amber-300"
                }`}>
                  {detailLatestRun.status === "completed" ? "Tam tarama" : detailLatestRun.status === "partial" ? "Kısmi tarama" : "Yeniden denenecek"}
                </span>
              </div>
              {(detailLatestRun.search_plan || []).length > 0 && (
                <div>
                  <div className="text-[10px] text-zinc-600 uppercase tracking-wider">Denenen arama yolları</div>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {detailLatestRun.search_plan.map((item, index) => (
                      <span key={`${item.kind}-${item.query}-${index}`} className="rounded border border-zinc-700 px-2 py-1 text-[10px] text-zinc-300">
                        {item.kind}: {item.query}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {(detailLatestRun.stores || []).length > 0 && (
                <details>
                  <summary className="cursor-pointer text-[11px] text-primary">Mağaza sonuçlarını tek tek göster</summary>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mt-3">
                    {detailLatestRun.stores.map((store) => (
                      <div key={store.slug || store.store} className="rounded border border-zinc-800 px-2.5 py-2 text-[10px]">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-zinc-300 truncate">{store.store}</span>
                          <span className={store.status === "ok" ? "text-emerald-300" : store.status === "deferred" ? "text-amber-300" : "text-red-300"}>
                            {store.status}
                          </span>
                        </div>
                        <div className="text-zinc-600 mt-1">
                          {store.count || 0} sonuç
                          {store.matched_query ? ` · ${store.matched_query}` : ""}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </section>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {detail.candidates.filter((candidate) => candidate.status === "review").map((candidate) => (
              <div key={candidate.id} className="card p-4 flex gap-3">
                {candidate.image && <img src={candidate.image} alt="" className="h-20 w-20 object-cover rounded" />}
                <div className="min-w-0 flex-1">
                  <a href={candidate.url} target="_blank" rel="noreferrer" className="text-sm font-medium line-clamp-2 hover:text-primary">{candidate.title}</a>
                  <div className="text-xs text-zinc-500 mt-1">{candidate.store} · %{Math.round((candidate.confidence || 0) * 100)} güven</div>
                  {candidate.verification_required && (
                    <div className="text-[10px] text-amber-300 mt-1">
                      Resmî ürün-kodu yolu bulundu; sayfa fiyat/stok doğrulaması için bağlantıyı açıp kontrol edin.
                    </div>
                  )}
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
