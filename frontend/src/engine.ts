import { useStore } from "./store";
import { callPy } from "./bridge";
import { alertDialog, confirmDialog } from "./dialog";
import { tabForStartError } from "./readiness";
import type { BackendState } from "./types";

interface StartResult {
  ok?: boolean;
  errors?: string[];
  uptime?: number;
}


export async function showStartErrors(errors: string[] | undefined): Promise<void> {
  const errs = errors && errors.length ? errors : ["Unknown error."];
  const msg = "• " + errs.join("\n• ");
  const target = tabForStartError(errs[0]);
  if (!target) {
    await alertDialog(msg, { title: "Macro could not be started" });
    return;
  }
  const go = await confirmDialog(msg, {
    title: "Almost there: one thing missing",
    confirmLabel: target.label,
    cancelLabel: "Not now",
  });
  if (go) useStore.getState().setCurrentTab(target.tab);
}

export async function toggleMacro(): Promise<void> {
  const { running } = useStore.getState();
  if (!running) {
    const res = await callPy<StartResult>("start_macro").catch(() => null);
    if (res && res.ok === false) {
      await showStartErrors(res.errors);
      return;
    }
    useStore.getState().setRunning(true, res?.uptime ?? 0);
  } else {
    await callPy("stop_macro").catch(() => {});
    useStore.getState().setRunning(false, 0);
  }
}

export async function setMode(mode: string): Promise<void> {
  const next = mode === "automation" || mode === "eden" ? mode : "idle";
  const cur = (useStore.getState().automation.mode as string) || "idle";
  if (next === cur) return;
  useStore.getState().setAutomationMode(next);
  const st = await callPy<BackendState>("set_automation_mode", next).catch(() => null);
  if (st) useStore.getState().applyState(st);
}
