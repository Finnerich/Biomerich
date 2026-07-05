import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles";
import "./app.css";
import { App } from "./App";
import { useStore } from "./store";
import { callPy, expose, waitReady } from "./bridge";
import { applyAccent, getAccentIndex } from "./data/accents";
import { applyTheme, getCurrentThemeId } from "./data/themes";
import { maybeStartTutorial } from "./tutorial";
import { useAgreement, agreementAccepted } from "./agreement";
import { useTesseract } from "./tesseract";
import type { TessProgress, TessDone } from "./tesseract";
import { useUpdateInstall } from "./updateInstall";
import type { UpdProgress, UpdDone } from "./updateInstall";
import { loadReleases } from "./update";
import { showStartErrors } from "./engine";
import type { BackendState } from "./types";

applyAccent(getAccentIndex());
applyTheme(getCurrentThemeId(), false);

interface HotkeyResult {
  ok?: boolean;
  errors?: string[];
  uptime?: number;
}

expose((result) => {
  const r = result as HotkeyResult | undefined;
  if (r && r.ok === false) {
    void showStartErrors(r.errors);
    return;
  }
  useStore.getState().setRunning(true, r?.uptime ?? 0);
}, "js_on_hotkey_start");

expose(() => {
  useStore.getState().setRunning(false, 0);
}, "js_on_hotkey_stop");

expose((mode) => {
  useStore.getState().setAutomationMode(String(mode));
}, "js_on_mode_hotkey");

expose((payload) => {
  const p = (payload || {}) as { running?: boolean; uptime?: number; mode?: string };
  useStore.getState().setRunning(!!p.running, p.uptime ?? 0);
  if (p.mode != null) useStore.getState().setAutomationMode(String(p.mode));
}, "js_on_engine_sync");

expose((settings) => {
  useStore.getState().patchSettings((settings || {}) as Record<string, unknown>);
}, "js_on_settings_sync");

expose((accId, success) => {
  useStore.getState().handleBindResult(Number(accId), !!success);
}, "onBindResult");

expose((accId, success, info) => {
  void callPy<BackendState>("get_state")
    .then((s) => { if (s) useStore.getState().applyState(s); })
    .catch(() => {});
  window.dispatchEvent(new CustomEvent("solrich:browser-login", {
    detail: { accId: Number(accId), success: !!success, info: String(info ?? "") },
  }));
}, "onBrowserLoginResult");

expose((freedBytes, count) => {
  const freed = Number(freedBytes) || 0;
  const mb = freed / 1048576;
  const amount = mb >= 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${Math.round(mb)} MB`;
  const procs = Number(count) || 0;
  useStore.getState().pushToast({
    icon: "fa-memory",
    title: `RAM trimmed: ${amount} freed`,
    detail: procs ? `Cleaned ${procs} processes` : "System memory cleaned",
  });
}, "js_on_ram_trimmed");

expose((payload) => {
  useTesseract.getState().onProgress((payload || {}) as TessProgress);
}, "onTesseractProgress");

expose((result) => {
  useTesseract.getState().onDone((result || {}) as TessDone);
}, "onTesseractDone");

expose((payload) => {
  useUpdateInstall.getState().onProgress((payload || {}) as UpdProgress);
}, "onUpdateProgress");

expose((result) => {
  useUpdateInstall.getState().onDone((result || {}) as UpdDone);
}, "onUpdateDone");

(async () => {
  try {
    await Promise.race([waitReady(), new Promise((r) => setTimeout(r, 1500))]);
    const state = await callPy<BackendState>("get_state").catch(() => null);
    if (state) {
      useStore.getState().applyState(state);
      applyAccent(getAccentIndex(state.settings?.accentIndex));
      applyTheme(getCurrentThemeId(state.settings?.themeId), false);
    }
    const ocr = await callPy<{ available?: boolean }>("get_ocr_status").catch(() => null);
    if (ocr) useStore.getState().setOcrAvailable(!!ocr.available);
    const streak = await callPy<{ count: number; previous: number; advanced: boolean }>("tick_streak").catch(() => null);
    if (streak) useStore.getState().setStreak(streak);
    void loadReleases();
    const tt = await callPy<Record<string, unknown>>("get_time_tracking").catch(() => null);
    if (tt) useStore.getState().setTimeTracking(tt);
  } catch (err) {
    console.warn("[SolRich] backend not reachable yet:", err);
  } finally {
    setTimeout(() => useStore.getState().setLoading(false), 650);
    setTimeout(async () => {
      const s = useStore.getState();
      const settings = s.settings as Record<string, unknown>;
      if (!agreementAccepted(settings)) {
        await useAgreement.getState().show();
      }
      maybeStartTutorial(useStore.getState().settings as Record<string, unknown>, s.version);
    }, 1500);
  }
})();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
