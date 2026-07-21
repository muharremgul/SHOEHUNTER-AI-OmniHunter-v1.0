import { resolveBackendUrl } from "./api";

test("uses the configured localhost backend on a localhost page", () => {
  expect(resolveBackendUrl({
    host: "localhost",
    protocol: "http:",
    configured: "http://localhost:8000",
  })).toBe("http://localhost:8000");
});

test("keeps the page host when localhost and 127.0.0.1 differ", () => {
  expect(resolveBackendUrl({
    host: "127.0.0.1",
    protocol: "http:",
    configured: "http://localhost:8000",
  })).toBe("http://127.0.0.1:8000");
});

test("uses the LAN address instead of a localhost build setting", () => {
  expect(resolveBackendUrl({
    host: "192.168.1.34",
    protocol: "http:",
    configured: "http://localhost:8000",
  })).toBe("http://192.168.1.34:8000");
});

test("honors an explicit production API origin", () => {
  expect(resolveBackendUrl({
    host: "shoehunter.example.com",
    protocol: "https:",
    configured: "https://api.example.com",
  })).toBe("https://api.example.com");
});

test("saved operator setting has the highest priority", () => {
  expect(resolveBackendUrl({
    saved: "https://custom.example.com",
    host: "localhost",
    protocol: "http:",
    configured: "http://localhost:8000",
  })).toBe("https://custom.example.com");
});
