import type { Account, AppSettings, Automation, TimeTracking, Webhook } from "./types";

export interface SetupStep {
  key: "account" | "window" | "module" | "webhook" | "start";
  title: string;
  desc: string;
  done: boolean;
  optional?: boolean;
  tab: string;
  actionLabel: string;
}

interface StoreSlice {
  accounts: Account[];
  webhooks: Webhook[];
  settings: AppSettings;
  automation: Automation;
  running: boolean;
  timeTracking: TimeTracking | null;
}

export function computeSetupSteps(s: StoreSlice): SetupStep[] {
  const hasAccount = s.accounts.length > 0;
  const hasWindow = s.accounts.some((a) => !!a.window || !!a.hwndKnown);
  const anyModule =
    !!s.settings.biomeLogging ||
    !!s.automation.cycle?.enabled ||
    !!s.settings.antiAfkEnabled ||
    s.accounts.some((a) => Object.values(a.modules || {}).some(Boolean)) ||
    Object.values(s.automation.autopop?.accounts || {}).some((e) => !!e?.enabled);
  const enabledIds = new Set(s.accounts.filter((a) => a.enabled !== false).map((a) => a.id));
  const hasWebhook = s.webhooks.some(
    (w) => ((w.url as string) || "").trim() && (w.active ?? true)
      && ((w.routedAccounts as number[]) || []).some((id) => enabledIds.has(id)),
  );
  const started = s.running || (Number(s.timeTracking?.sessions) || 0) > 0;

  return [
    {
      key: "account", done: hasAccount, tab: "accounts", actionLabel: "Open Accounts",
      title: "Add your Roblox account",
      desc: "Give it a name and your private-server link so the macro knows which game to run.",
    },
    {
      key: "window", done: hasWindow, tab: "accounts", actionLabel: "Open Accounts",
      title: "Launch your Roblox account",
      desc: "Launch the account from the Accounts tab. The macro finds and controls its Roblox window automatically.",
    },
    {
      key: "module", done: anyModule, tab: "modules", actionLabel: "Open Macro",
      title: "Turn on a module",
      desc: "Pick what the macro should do: Biome Logging, Fishing, Auto Pop, Anti-AFK… Locked modules tell you which calibration they still need.",
    },
    {
      key: "webhook", done: hasWebhook, tab: "webhooks", actionLabel: "Open Webhooks",
      title: "Connect a Discord webhook",
      desc: "Biome Logging is always on, so you need an active webhook routed to an account. Add one in the Webhooks tab.",
    },
    {
      key: "start", done: started, tab: "home", actionLabel: "Start",
      title: "Press Start",
      desc: "Hit the Start button (or your hotkey) and the macro takes over.",
    },
  ];
}


export function tabForStartError(error: string): { tab: string; label: string } | null {
  const e = error.toLowerCase();
  if (e.includes("calibration") || e.includes("contract region")) return { tab: "calibration", label: "Open Calibration" };
  if (e.includes("bind") && e.includes("window")) return { tab: "modules", label: "Bind Windows" };
  if (e.includes("window")) return { tab: "accounts", label: "Open Accounts" };
  if (e.includes("webhook")) return { tab: "webhooks", label: "Open Webhooks" };
  if (e.includes("account") || e.includes("server link")) return { tab: "accounts", label: "Open Accounts" };
  if (e.includes("module") || e.includes("auto pop") || e.includes("eden")) return { tab: "modules", label: "Open Macro" };
  return null;
}
