import {
  applyLabelSuggestion,
  applySelectedOcrSuggestion,
  allOcrSelection,
  buildSelectedOcrQuery,
  nativeBarcodeSuggestion,
  parseGs1DigitalLinkUrl,
  nativeOcrSuggestion,
  ocrOverlayStyle,
  recommendedOcrSelection,
  rotationCanvasGeometry,
  scanCoverage,
  storeSlugs,
  togglePreferenceSelection,
  toggleStoreScope,
} from "./ProductRadar";

test("builds the select-all scope in API store order", () => {
  expect(storeSlugs([
    { slug: "adidas", name: "Adidas" },
    { slug: "intersport", name: "Intersport" },
    { slug: "trendyol", name: "Trendyol" },
    { slug: "brooks", name: "Brooks Türkiye" },
    { slug: "columbia", name: "Columbia Türkiye" },
    { slug: "salomon", name: "Salomon Türkiye" },
    { slug: "thenorthface", name: "The North Face Türkiye" },
  ])).toEqual([
    "adidas",
    "intersport",
    "trendyol",
    "brooks",
    "columbia",
    "salomon",
    "thenorthface",
  ]);
});

test("toggles one store without changing the remaining selection order", () => {
  expect(toggleStoreScope(["adidas", "intersport"], "adidas")).toEqual(["intersport"]);
  expect(toggleStoreScope(["intersport"], "trendyol")).toEqual(["intersport", "trendyol"]);
});

test("supports a single outdoor store and an explicitly cleared scope", () => {
  expect(toggleStoreScope([], "columbia")).toEqual(["columbia"]);
  expect(toggleStoreScope(["columbia"], "columbia")).toEqual([]);
});

test("selects multiple family size profiles without dropping previous people", () => {
  expect(togglePreferenceSelection([], "ayse-shoes")).toEqual(["ayse-shoes"]);
  expect(togglePreferenceSelection(["ayse-shoes"], "ali-shoes")).toEqual(["ayse-shoes", "ali-shoes"]);
  expect(togglePreferenceSelection(["ayse-shoes", "ali-shoes"], "ayse-shoes")).toEqual(["ali-shoes"]);
});

test("applies a reviewed label scan without dropping selected stores", () => {
  const current = {
    raw_query: "",
    desired_sizes: "",
    category: "shoes",
    target_price: "",
    store_scope: ["adidas", "trendyol"],
    profile_preference_ids: ["ali-shoes"],
  };
  const next = applyLabelSuggestion(current, {
    suggested_watch: {
      raw_query: "Adidas Adizero Evo SL JH6206",
      desired_sizes: ["44"],
      category: "shoes",
      target_price: 4999,
      brand: "Adidas",
      model: "JH6206",
      source_identifiers: { product_code: "JH6206", barcode: "4067903745960" },
    },
  });
  expect(next.raw_query).toBe("Adidas Adizero Evo SL JH6206");
  expect(next.desired_sizes).toBe("44");
  expect(next.target_price).toBe(4999);
  expect(next.store_scope).toEqual(["adidas", "trendyol"]);
  expect(next.profile_preference_ids).toEqual(["ali-shoes"]);
  expect(next.input_origin).toBe("label_scan");
});

test("clears incompatible family size profiles when scanned category changes", () => {
  const next = applyLabelSuggestion(
    {
      raw_query: "",
      desired_sizes: "",
      category: "shoes",
      target_price: "",
      store_scope: ["adidas"],
      profile_preference_ids: ["ali-shoes"],
    },
    { suggested_watch: { raw_query: "Adidas KC1948", category: "outerwear" } }
  );
  expect(next.category).toBe("outerwear");
  expect(next.profile_preference_ids).toEqual([]);
});

test("lets the user build a radar query from selected OCR lines", () => {
  const result = {
    brand: "Adidas",
    product_codes: ["JR5220"],
    descriptive_lines: ["TRAIL RUNNING"],
    text_blocks: [
      { text: "TRAIL RUNNING", confidence: 0.97 },
      { text: "JR5220", confidence: 0.99 },
      { text: "EU 44", confidence: 0.95 },
    ],
  };
  expect(recommendedOcrSelection(result)).toEqual([0, 1]);
  expect(buildSelectedOcrQuery(result, [0, 1])).toBe("TRAIL RUNNING JR5220");
  expect(buildSelectedOcrQuery(result, [1])).toBe("JR5220");
  expect(allOcrSelection(result)).toEqual([0, 1, 2]);
});

test("selected OCR evidence does not retain an unselected, possibly wrong identity", () => {
  const current = { category: "shoes", profile_preference_ids: [], store_scope: ["adidas"] };
  const result = {
    brand: "Adidas",
    product_codes: ["JR5220"],
    text_blocks: [
      { text: "Adidas" },
      { text: "TRAIL RUNNING" },
      { text: "JR5220" },
    ],
    suggested_watch: {
      category: "shoes",
      brand: "Adidas",
      model: "JR5220",
      source_identifiers: { product_code: "JR5220", barcode: "4067904494690" },
    },
  };

  expect(applySelectedOcrSuggestion(current, result, [1])).toMatchObject({
    raw_query: "TRAIL RUNNING",
    brand: null,
    model: null,
    source_identifiers: { barcode: "4067904494690" },
    input_origin: "label_scan",
  });
  expect(applySelectedOcrSuggestion(current, result, [0, 1, 2])).toMatchObject({
    raw_query: "Adidas TRAIL RUNNING JR5220",
    brand: "Adidas",
    model: "JR5220",
    source_identifiers: { barcode: "4067904494690", product_code: "JR5220" },
  });
});

test("computes a lossless quarter-turn canvas for direction correction", () => {
  expect(rotationCanvasGeometry(1200, 800, 1)).toEqual({
    width: 800,
    height: 1200,
    radians: Math.PI / 2,
  });
  expect(rotationCanvasGeometry(1200, 800, -1)).toEqual({
    width: 800,
    height: 1200,
    radians: -Math.PI / 2,
  });
});

test("draws a selectable OCR region over the original image", () => {
  expect(ocrOverlayStyle({
    polygon_norm: [[0.2, 0.1], [0.7, 0.1], [0.7, 0.4], [0.2, 0.4]],
  })).toEqual({ left: "20%", top: "10%", width: "50%", height: "30%" });
  expect(ocrOverlayStyle({ text: "JR5220" })).toBeNull();
});

test("turns a native Android barcode into exact Radar identity evidence", () => {
  expect(nativeBarcodeSuggestion({ value: "4067904494690" })).toEqual({
    raw_query: "4067904494690",
    model: null,
    input_origin: "label_scan",
    source_identifiers: { barcode: "4067904494690" },
  });
  expect(nativeBarcodeSuggestion({ value: "JR5220" }).source_identifiers).toEqual({ product_code: "JR5220" });
});

test("turns a GS1 Digital Link QR into GTIN-first Radar evidence", () => {
  const url = "https://id.gs1.org/01/09506000134352/10/LOT7/21/SER42?17=271231";
  expect(parseGs1DigitalLinkUrl(url)).toMatchObject({
    gtin: "09506000134352",
    batch_lot: "LOT7",
    serial: "SER42",
    expiry_yymmdd: "271231",
  });
  expect(nativeBarcodeSuggestion({ value: url })).toMatchObject({
    raw_query: "09506000134352",
    model: null,
    source_identifiers: {
      qr: url,
      gtin: "09506000134352",
      batch_lot: "LOT7",
      serial: "SER42",
    },
  });
});

test("turns user-selected native OCR text into reviewed Radar evidence", () => {
  expect(nativeOcrSuggestion({
    selected_text: "Adidas TRAIL RUNNING JR5220",
    brand: "Adidas",
    product_codes: ["JR5220", "WRONG1"],
  })).toEqual({
    raw_query: "Adidas TRAIL RUNNING JR5220",
    brand: "Adidas",
    model: "JR5220",
    input_origin: "label_scan",
    source_identifiers: { product_code: "JR5220" },
  });
  expect(nativeOcrSuggestion({ selected_text: "TRAIL RUNNING" })).toMatchObject({
    raw_query: "TRAIL RUNNING",
    brand: null,
    model: null,
    source_identifiers: {},
  });
  expect(nativeOcrSuggestion({ text_blocks: [] })).toBeNull();
});

test("reports partial store coverage instead of hiding deferred stores", () => {
  expect(scanCoverage({
    stores: [
      { status: "ok" },
      { status: "ok" },
      ...Array.from({ length: 25 }, () => ({ status: "deferred" })),
    ],
  })).toEqual({
    selected: 27,
    searched: 2,
    deferred: 25,
    failed: 0,
    blocked: 0,
    timedOut: 0,
    parserFail: 0,
    otherError: 0,
  });
});
