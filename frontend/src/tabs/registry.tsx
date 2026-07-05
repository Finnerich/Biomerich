import { lazy, type ComponentType, type ReactElement } from "react";
import { Placeholder } from "./Placeholder";

const L = <T extends Record<string, ComponentType>>(load: () => Promise<T>, key: keyof T) =>
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
  home: L(() => import("./Home"), "Home"),
  stats: L(() => import("./Stats"), "Stats"),
  modules: L(() => import("./ModuleBuilder"), "ModuleBuilder"),
  safety: L(() => import("./Safety"), "Safety"),
  accounts: L(() => import("./Accounts"), "Accounts"),
  webhooks: L(() => import("./Webhooks"), "Webhooks"),
  calibration: L(() => import("./Calibration"), "Calibration"),
  performance: L(() => import("./Performance"), "Performance"),
  creator: L(() => import("./Creator"), "Creator"),
  patchlog: L(() => import("./Patchlog"), "Patchlog"),
  settings: L(() => import("./Settings"), "Settings"),
};

export function renderTab(tab: string): ReactElement {
  const Comp = TABS[tab];
  return Comp ? <Comp /> : <Placeholder tab={tab} />;
}
