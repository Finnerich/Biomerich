
export interface NavItem {
  tab: string;
  icon: string;
  label: string;
}

export interface NavGroupDef {
  id: string;
  label: string;
  icon: string;
  items: NavItem[];
}

const NAV_TAB_ON: Record<string, boolean> = {
};

const RAW_NAV_GROUPS: NavGroupDef[] = [
  {
    id: "overview",
    label: "Overview",
    icon: "fa-chart-simple",
    items: [
      { tab: "home", icon: "fa-house", label: "Home" },
      { tab: "stats", icon: "fa-chart-simple", label: "Stats" },
      { tab: "monitor", icon: "fa-desktop", label: "Monitor" },
      { tab: "timeline", icon: "fa-timeline", label: "Timeline" },
    ],
  },
  {
    id: "macro",
    label: "Macro",
    icon: "fa-cubes",
    items: [
      { tab: "modules", icon: "fa-cubes", label: "Module Builder" },
      { tab: "calibration", icon: "fa-crosshairs", label: "Calibration" },
      { tab: "safety", icon: "fa-shield-halved", label: "Safety" },
      { tab: "performance", icon: "fa-gauge-high", label: "Performance" },
    ],
  },
  {
    id: "setup",
    label: "Setup",
    icon: "fa-database",
    items: [
      { tab: "accounts", icon: "fa-users-gear", label: "Accounts" },
      { tab: "webhooks", icon: "fa-tower-broadcast", label: "Webhooks" },
    ],
  },
  {
    id: "system",
    label: "System",
    icon: "fa-gear",
    items: [
      { tab: "patchlog", icon: "fa-clock-rotate-left", label: "Patchlog" },
      { tab: "settings", icon: "fa-sliders", label: "Settings" },
    ],
  },
];

export const NAV_GROUPS: NavGroupDef[] = RAW_NAV_GROUPS
  .map((group) => ({ ...group, items: group.items.filter((item) => NAV_TAB_ON[item.tab] !== false) }))
  .filter((group) => group.items.length > 0);


const MULTI_ONLY_TABS = new Set<string>([]);

export function navGroupsFor(mode: "normal" | "multi"): NavGroupDef[] {
  if (mode === "multi") return NAV_GROUPS;
  return NAV_GROUPS
    .map((group) => ({
      ...group,
      items: group.items
        .filter((item) => !MULTI_ONLY_TABS.has(item.tab))
        .map((item) => (item.tab === "modules" ? { ...item, label: "Macro", icon: "fa-toggle-on" } : item)),
    }))
    .filter((group) => group.items.length > 0);
}

export function isTabHidden(tab: string, mode: "normal" | "multi"): boolean {
  return mode === "normal" && MULTI_ONLY_TABS.has(tab);
}

export const GROUP_LABELS: Record<string, string> = Object.fromEntries(
  NAV_GROUPS.map((group) => [group.id, group.label]),
);

export function groupOfTab(tab: string): string | null {
  for (const group of NAV_GROUPS) {
    if (group.items.some((item) => item.tab === tab)) return group.id;
  }
  return null;
}

export function labelOfTab(tab: string): string {
  for (const group of NAV_GROUPS) {
    const item = group.items.find((item) => item.tab === tab);
    if (item) return item.label;
  }
  return tab;
}
