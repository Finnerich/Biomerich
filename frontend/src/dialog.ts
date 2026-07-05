import { create } from "zustand";

type Kind = "alert" | "confirm" | "prompt";

interface DialogState {
  open: boolean;
  kind: Kind;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  danger: boolean;
  defaultValue: string;
  placeholder: string;
  resolve: ((v: boolean | string | null) => void) | null;
  close: (v: boolean | string | null) => void;
}

export const useDialog = create<DialogState>((set, get) => ({
  open: false,
  kind: "alert",
  title: "",
  message: "",
  confirmLabel: "OK",
  cancelLabel: "Cancel",
  danger: false,
  defaultValue: "",
  placeholder: "",
  resolve: null,
  close: (v) => {
    const r = get().resolve;
    set({ open: false, resolve: null });
    r?.(v);
  },
}));

interface BaseOpts {
  title?: string;
  confirmLabel?: string;
}
interface ConfirmOpts extends BaseOpts {
  cancelLabel?: string;
  danger?: boolean;
}
interface PromptOpts extends ConfirmOpts {
  defaultValue?: string;
  placeholder?: string;
}

function show(cfg: Partial<DialogState> & { kind: Kind; message: string }): Promise<boolean | string | null> {
  return new Promise((resolve) => {
    useDialog.setState({
      open: true,
      kind: cfg.kind,
      title: cfg.title ?? "",
      message: cfg.message,
      confirmLabel: cfg.confirmLabel ?? (cfg.kind === "alert" ? "OK" : "Confirm"),
      cancelLabel: cfg.cancelLabel ?? "Cancel",
      danger: cfg.danger ?? false,
      defaultValue: cfg.defaultValue ?? "",
      placeholder: cfg.placeholder ?? "",
      resolve,
    });
  });
}

export function alertDialog(message: string, opts: BaseOpts = {}): Promise<void> {
  return show({ kind: "alert", message, ...opts }).then(() => undefined);
}

export function confirmDialog(message: string, opts: ConfirmOpts = {}): Promise<boolean> {
  return show({ kind: "confirm", message, ...opts }).then((v) => v === true);
}

export function promptDialog(message: string, opts: PromptOpts = {}): Promise<string | null> {
  return show({ kind: "prompt", message, ...opts }).then((v) => (typeof v === "string" ? v : null));
}
