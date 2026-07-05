import { describe, it, expect } from "vitest";
import { useStore } from "./store";
import type { Account } from "./types";

describe("store", () => {
  it("applyState loads running + accounts + webhooks", () => {
    useStore.getState().applyState({
      running: true,
      accounts: [{ id: 1, name: "Alpha" }] as Account[],
      webhooks: [{ id: 9, url: "http://x", active: true }],
    });
    const s = useStore.getState();
    expect(s.running).toBe(true);
    expect(s.accounts).toHaveLength(1);
    expect(s.accounts[0].name).toBe("Alpha");
    expect(s.webhooks[0].url).toBe("http://x");
  });

  it("applyStatus merges live account states (online/window) by id", () => {
    useStore.getState().applyState({ accounts: [{ id: 1, name: "Alpha" }] as Account[] });
    useStore.getState().applyStatus({
      accountStates: [{ id: 1, online: true, window: "Roblox #1", currentBiome: "glitched" }],
    });
    const acc = useStore.getState().accounts[0];
    expect(acc.online).toBe(true);
    expect(acc.window).toBe("Roblox #1");
    expect(acc.currentBiome).toBe("glitched");
  });

  it("preserveAccountLiveFields keeps live window across a config refresh", () => {
    useStore.getState().applyState({ accounts: [{ id: 1, name: "Alpha" }] as Account[] });
    useStore.getState().applyStatus({ accountStates: [{ id: 1, online: true, window: "Roblox #1" }] });
    useStore.getState().applyState({ accounts: [{ id: 1, name: "Alpha (renamed)" }] as Account[] });
    const acc = useStore.getState().accounts[0];
    expect(acc.name).toBe("Alpha (renamed)");
    expect(acc.window).toBe("Roblox #1");
    expect(acc.online).toBe(true);
  });

  it("setAutomationMode updates only the mode", () => {
    useStore.getState().applyState({ automation: { mode: "idle" } });
    useStore.getState().setAutomationMode("eden");
    expect(useStore.getState().automation.mode).toBe("eden");
  });
});
