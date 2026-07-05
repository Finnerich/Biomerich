import { describe, it, expect, beforeEach } from "vitest";
import { ACCENTS, applyAccent, applyAccentObject, getAccentIndex } from "./accents";

describe("accents", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("style");
  });

  it("applyAccentObject sets the accent + derived rgb CSS vars on :root", () => {
    applyAccentObject(ACCENTS[0]);
    const root = document.documentElement.style;
    expect(root.getPropertyValue("--accent")).toBe(ACCENTS[0].c);
    const n = parseInt(ACCENTS[0].c.slice(1), 16);
    expect(root.getPropertyValue("--ar")).toBe(String((n >> 16) & 255));
    expect(root.getPropertyValue("--ag")).toBe(String((n >> 8) & 255));
    expect(root.getPropertyValue("--ab")).toBe(String(n & 255));
    expect(root.getPropertyValue("--bg-0")).toBe(ACCENTS[0].bg0);
    expect(root.getPropertyValue("--glass")).toBe(ACCENTS[0].glass);
  });

  it("applyAccent(index) applies the matching palette", () => {
    applyAccent(1);
    expect(document.documentElement.style.getPropertyValue("--accent")).toBe(ACCENTS[1].c);
  });

  it("getAccentIndex prefers a valid settings index", () => {
    expect(getAccentIndex(2)).toBe(2);
  });

  it("getAccentIndex falls back to localStorage then 0", () => {
    localStorage.setItem("accentIndex", "3");
    expect(getAccentIndex(undefined)).toBe(3);
    localStorage.clear();
    expect(getAccentIndex(undefined)).toBe(0);
    expect(getAccentIndex(999)).toBe(0);
  });
});
