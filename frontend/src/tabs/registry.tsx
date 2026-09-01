import { lazy, type ComponentType, type ReactElement } from "react";
import { Placeholder } from "./Placeholder";

const lazyTab = <T extends Record<string, ComponentType>>(load: () => Promise<T>, key: keyof T) =>
  lazy(() =>
    load().then((m) => ({ default: m[key] })).catch((err) => {


      const KEY = "chunkReloadAt";
      const last = Number(sessionStorage.getItem(KEY) || 0);
      if (Date.now() - last > 10_000) {
        sessionStorage.setItem(KEY, String(Date.now()));
        location.reload();
      }
      throw err;
    }),
  );

const TABS: Record<string, ComponentType> = {
  home: lazyTab(() => import("./Home"), "Home"),
  stats: lazyTab(() => import("./Stats"), "Stats"),
  monitor: lazyTab(() => import("./Monitor"), "Monitor"),
  timeline: lazyTab(() => import("./Timeline"), "Timeline"),
  modules: lazyTab(() => import("./ModuleBuilder"), "ModuleBuilder"),
  safety: lazyTab(() => import("./Safety"), "Safety"),
  accounts: lazyTab(() => import("./Accounts"), "Accounts"),
  webhooks: lazyTab(() => import("./Webhooks"), "Webhooks"),
  calibration: lazyTab(() => import("./Calibration"), "Calibration"),
  performance: lazyTab(() => import("./Performance"), "Performance"),
  creator: lazyTab(() => import("./Creator"), "Creator"),
  patchlog: lazyTab(() => import("./Patchlog"), "Patchlog"),
  settings: lazyTab(() => import("./Settings"), "Settings"),
};

export function renderTab(tab: string): ReactElement {
  const Comp = TABS[tab];
  return Comp ? <Comp /> : <Placeholder tab={tab} />;
}
