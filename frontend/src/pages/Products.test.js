import { productClassification } from "./Products";


test("marks radar products and exposes category plus all tracking origins", () => {
  expect(productClassification({
    category: "shoes",
    tracking_origins: ["radar", "ai_search"],
    radar_watch_count: 1,
  })).toEqual({
    category: "Ayakkabı",
    origins: ["Radar", "AI Arama"],
    radar: true,
  });
});

test("keeps older products visible as unclassified legacy records", () => {
  expect(productClassification({})).toEqual({
    category: "Sınıflandırılmadı",
    origins: ["Eski kayıt"],
    radar: false,
  });
});
