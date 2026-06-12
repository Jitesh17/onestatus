// Vitest setup: jest-dom matchers (toBeInTheDocument, etc.) for all test files.
import "@testing-library/jest-dom/vitest";

// Node's built-in localStorage (which needs --localstorage-file) shadows jsdom's
// and arrives as a method-less stub. Replace it with a working in-memory store.
class MemoryStorage {
  #store = new Map();
  getItem(key) { return this.#store.has(key) ? this.#store.get(key) : null; }
  setItem(key, value) { this.#store.set(String(key), String(value)); }
  removeItem(key) { this.#store.delete(key); }
  clear() { this.#store.clear(); }
  key(i) { return [...this.#store.keys()][i] ?? null; }
  get length() { return this.#store.size; }
}
const memoryStorage = new MemoryStorage();
for (const target of [globalThis, typeof window !== "undefined" ? window : null]) {
  if (target) {
    Object.defineProperty(target, "localStorage", {
      value: memoryStorage,
      writable: true,
      configurable: true,
    });
  }
}
