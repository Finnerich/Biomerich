import { create } from "zustand";
import { callPy } from "./bridge";
import { useStore } from "./store";

interface AgreementState {
  open: boolean;
  _resolve: (() => void) | null;
  show: () => Promise<void>;
  accept: () => void;
}

export const useAgreement = create<AgreementState>((set, get) => ({
  open: false,
  _resolve: null,
  show: () => new Promise<void>((resolve) => set({ open: true, _resolve: resolve })),
  accept: () => {
    localStorage.setItem("agreementAccepted", "1");
    useStore.getState().patchSettings({ agreementAccepted: true });
    void callPy("set_setting", "agreementAccepted", true);
    const resolve = get()._resolve;
    set({ open: false, _resolve: null });
    resolve?.();
  },
}));

export function agreementAccepted(settings: { agreementAccepted?: unknown }): boolean {
  return settings.agreementAccepted === true || localStorage.getItem("agreementAccepted") === "1";
}
