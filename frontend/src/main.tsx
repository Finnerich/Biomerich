import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles";
import "./app.css";
import { App } from "./App";
import { useStore } from "./store";
import { callPy, expose, waitReady } from "./bridge";
import { applyAccent, getAccentIndex } from "./data/accents";
import { applyTheme, getCurrentThemeId, loadCustomThemeImage } from "./data/themes";
import { maybeStartTutorial } from "./tutorial";
import { useAgreement, agreementAccepted } from "./agreement";
import { useTesseract } from "./tesseract";
import type { TessProgress, TessDone } from "./tesseract";
import { useUpdateInstall } from "./updateInstall";
import type { UpdProgress, UpdDone } from "./updateInstall";
import { loadReleases } from "./update";
import { showStartErrors } from "./engine";
import type { BackendState } from "./types";
import type { BiomeHealthWarning, RarePingWarning } from "./store";
import { alertDialog } from "./dialog";

applyAccent(getAccentIndex());
applyTheme(getCurrentThemeId(), false);

interface HotkeyResult {
  ok?: boolean;
  errors?: string[];
  uptime?: number;
}

let startupConfigRecovery: BackendState["configRecovery"] = null;

expose((result) => {
  const hotkeyResult = result as HotkeyResult | undefined;
  if (hotkeyResult && hotkeyResult.ok === false) {
    void showStartErrors(hotkeyResult.errors);
    return;
  }
  useStore.getState().setRunning(true, hotkeyResult?.uptime ?? 0);
}, "js_on_hotkey_start");

expose(() => {
  useStore.getState().setRunning(false, 0);
}, "js_on_hotkey_stop");

expose((mode) => {
  useStore.getState().setAutomationMode(String(mode));
}, "js_on_mode_hotkey");

expose((payload) => {
  const sync = (payload || {}) as { running?: boolean; uptime?: number; mode?: string };
  useStore.getState().setRunning(!!sync.running, sync.uptime ?? 0);
  if (sync.mode != null) useStore.getState().setAutomationMode(String(sync.mode));
}, "js_on_engine_sync");

expose((settings) => {
  useStore.getState().patchSettings((settings || {}) as Record<string, unknown>);
}, "js_on_settings_sync");

expose((payload) => {
  const warning = (payload || {}) as RarePingWarning;
  if (!warning.id) return;
  const store = useStore.getState();
  store.pushRarePingWarning({ ...warning, id: String(warning.id) });
  store.setCurrentTab("modules");
}, "js_on_rare_ping_blocked");

expose((pendingId) => {
  useStore.getState().dismissRarePingWarning(String(pendingId));
}, "js_on_rare_ping_resolved");

expose((payload) => {
  const warning = (payload || {}) as BiomeHealthWarning;
  if (!warning.accountId) return;
  const store = useStore.getState();
  store.pushBiomeHealthWarning({
    ...warning,
    id: String(warning.id || `biome-health-${warning.accountId}`),
    account: String(warning.account || "Unknown account"),
    silentMinutes: Number(warning.silentMinutes) || 30,
  });
  store.pushToast({
    icon: "fa-triangle-exclamation",
    title: "Biome detection may be broken",
    detail: `${warning.account || "An account"} has produced no biome signal for ${Number(warning.silentMinutes) || 30} minutes.`,
  });
}, "js_on_biome_health_warning");

expose((accountId) => {
  const id = Number(accountId);
  const store = useStore.getState();
  const warning = store.biomeHealthWarnings.find((item) => item.accountId === id);
  store.dismissBiomeHealthWarning(id);
  if (warning) {
    store.pushToast({
      icon: "fa-circle-check",
      title: "Biome detection recovered",
      detail: `${warning.account} is producing valid biome signals again.`,
    });
  }
}, "js_on_biome_health_resolved");

expose((accId, success) => {
  useStore.getState().handleBindResult(Number(accId), !!success);
}, "onBindResult");

expose((accId, success, info) => {
  void callPy<BackendState>("get_state")
    .then((state) => { if (state) useStore.getState().applyState(state); })
    .catch(() => {});
  window.dispatchEvent(new CustomEvent("solrich:browser-login", {
    detail: { accId: Number(accId), success: !!success, info: String(info ?? "") },
  }));
}, "onBrowserLoginResult");

expose((freedBytes, count) => {
  const freed = Number(freedBytes) || 0;
  const freedMb = freed / 1048576;
  const amountLabel = freedMb >= 1024 ? `${(freedMb / 1024).toFixed(2)} GB` : `${Math.round(freedMb)} MB`;
  const processCount = Number(count) || 0;
  useStore.getState().pushToast({
    icon: "fa-memory",
    title: `RAM trimmed: ${amountLabel} freed`,
    detail: processCount ? `Cleaned ${processCount} processes` : "System memory cleaned",
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
    await Promise.race([waitReady(), new Promise((resolve) => setTimeout(resolve, 1500))]);
    const state = await callPy<BackendState>("get_state").catch(() => null);
    if (state) {
      useStore.getState().applyState(state);
      startupConfigRecovery = state.configRecovery;
      if (state.configRecovery?.status === "backup") {
        useStore.getState().pushToast({
          icon: "fa-shield-heart",
          title: "Your SolRich data was recovered",
          detail: "The main config was damaged or missing, so the automatic backup was restored.",
        });
      }
      applyAccent(getAccentIndex(state.settings?.accentIndex));
      applyTheme(getCurrentThemeId(state.settings?.themeId), false);
      void loadCustomThemeImage();
    }
    
    
    void callPy<{ available?: boolean }>("get_ocr_status")
      .then((ocrStatus) => { if (ocrStatus) useStore.getState().setOcrAvailable(!!ocrStatus.available); })
      .catch(() => {});
    void callPy<{ count: number; previous: number; advanced: boolean }>("tick_streak")
      .then((streak) => { if (streak) useStore.getState().setStreak(streak); })
      .catch(() => {});
    void loadReleases();
    void callPy<Record<string, unknown>>("get_time_tracking")
      .then((timeTracking) => { if (timeTracking) useStore.getState().setTimeTracking(timeTracking); })
      .catch(() => {});
  } catch (err) {
    console.warn("[SolRich] backend not reachable yet:", err);
  } finally {
    
    
    requestAnimationFrame(() => useStore.getState().setLoading(false));
    setTimeout(async () => {
      const store = useStore.getState();
      const settings = store.settings as Record<string, unknown>;
      if (startupConfigRecovery?.status === "unrecoverable") {
        const preserved = startupConfigRecovery.preservedFile
          ? ` A recoverable copy was preserved as ${startupConfigRecovery.preservedFile}.`
          : "";
        await alertDialog(
          "SolRich could not read your config and no valid automatic backup was available. " +
          "The damaged file was not silently deleted or overwritten." + preserved,
          { title: "Config recovery needed" },
        );
        return;
      }
      if (!agreementAccepted(settings)) {
        await useAgreement.getState().show();
      }
      maybeStartTutorial(useStore.getState().settings as Record<string, unknown>, store.version);
    }, 1500);
  }
})();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
