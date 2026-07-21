import { alertSizeText } from "./Alerts";


test("every alert has an explicit size message", () => {
  expect(alertSizeText({ sizes: ["42", "43"] })).toBe("42, 43");
  expect(alertSizeText({ size: "M" })).toBe("M");
  expect(alertSizeText({})).toBe("Doğrulanamadı");
});
