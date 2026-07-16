import { useStore } from "../store";
import { callPy } from "../bridge";
import type { AppSettings } from "../types";

export type MacroMode = "normal" | "multi";

export function getMacroMode(settings: AppSettings): MacroMode {
  return settings.macroMode === "normal" ? "normal" : "multi";
}

export function getNormalAccountId(settings: AppSettings): number | null {
  const v = settings.normalAccountId;
  return typeof v === "number" ? v : null;
}


export function getMacroAccounts<T extends { id: number; enabled?: boolean }>(
  accounts: T[],
  settings: AppSettings,
): T[] {
  if (getMacroMode(settings) === "normal") {
    const selectedId = getNormalAccountId(settings);
    const selected = selectedId == null ? undefined : accounts.find((account) => account.id === selectedId);
    return selected ? [selected] : accounts.slice(0, 1);
  }
  return accounts.filter((account) => account.enabled !== false);
}

export async function setMacroMode(mode: MacroMode): Promise<void> {
  useStore.getState().patchSettings({ macroMode: mode });
  await callPy("set_setting", "macroMode", mode);
}

export async function setNormalAccount(accId: number): Promise<void> {
  useStore.getState().patchSettings({ normalAccountId: accId });
  await callPy("set_setting", "normalAccountId", accId);
}
