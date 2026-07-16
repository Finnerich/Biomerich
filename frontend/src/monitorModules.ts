import type { Account, AppSettings, Automation } from "./types";

export const MONITOR_MODULE_ORDER = [
  "biomeLogging",
  "antiAfk",
  "ramTrim",
  "strangeController",
  "biomeRandomizer",
  "merchantTeleporter",
  "auraDetection",
  "autopop",
  "fishing",
  "eden",
] as const;

const ORDER_INDEX = new Map<string, number>(
  MONITOR_MODULE_ORDER.map((key, index) => [key, index]),
);

export function getEnabledMonitorModules(input: {
  activeModules?: string[];
  settings: AppSettings;
  automation: Automation;
  accounts: Account[];
  currentModuleKey?: string;
}): string[] {
  const enabled = new Set(input.activeModules || []);
  enabled.add("biomeLogging");

  if (input.settings.antiAfkEnabled) enabled.add("antiAfk");
  if (input.settings.ramTrimEnabled) enabled.add("ramTrim");

  for (const account of input.accounts) {
    if (account.enabled === false) continue;
    for (const [moduleKey, isEnabled] of Object.entries(account.modules || {})) {
      if (isEnabled) enabled.add(moduleKey);
    }
  }

  const fishing = input.automation.fishing as
    | { enabled?: boolean; moduleEnabled?: boolean }
    | undefined;
  if (fishing?.enabled || fishing?.moduleEnabled) enabled.add("fishing");

  const autopopAccounts = input.automation.autopop?.accounts || {};
  const enabledAccountIds = new Set(
    input.accounts.filter((account) => account.enabled !== false).map((account) => String(account.id)),
  );
  if (Object.entries(autopopAccounts).some(
    ([accountId, entry]) => enabledAccountIds.has(accountId) && !!entry.enabled,
  )) {
    enabled.add("autopop");
  }

  if (input.automation.mode === "eden") enabled.add("eden");
  if (input.currentModuleKey && ORDER_INDEX.has(input.currentModuleKey)) {
    enabled.add(input.currentModuleKey);
  }

  return [...enabled].sort((left, right) => {
    const leftIndex = ORDER_INDEX.get(left) ?? Number.MAX_SAFE_INTEGER;
    const rightIndex = ORDER_INDEX.get(right) ?? Number.MAX_SAFE_INTEGER;
    return leftIndex - rightIndex || left.localeCompare(right);
  });
}
