import { create } from "zustand";
import { callPy } from "./bridge";
import { useStore } from "./store";

export type TessPhase = "idle" | "downloading" | "extracting" | "done" | "error";

export interface TessProgress {
  stage?: string;
  downloaded?: number;
  total?: number;
  percent?: number;
}
export interface TessDone {
  ok?: boolean;
  error?: string;
  available?: boolean;
}

interface TesseractState {
  modalOpen: boolean;
  prompt: boolean;
  phase: TessPhase;
  downloaded: number;
  total: number;
  percent: number;
  error: string | null;

  openPrompt: () => void;
  openInstall: () => void;
  close: () => void;
  later: () => void;
  install: () => Promise<void>;
  demo: () => void;
  onProgress: (p: TessProgress) => void;
  onDone: (r: TessDone) => void;
}

function busy(phase: TessPhase): boolean {
  return phase === "downloading" || phase === "extracting";
}

export async function refreshOcr(): Promise<void> {
  const st = await callPy<{ available?: boolean }>("get_ocr_status").catch(() => null);
  if (st) useStore.getState().setOcrAvailable(!!st.available);
}

export const useTesseract = create<TesseractState>((set, get) => ({
  modalOpen: false,
  prompt: false,
  phase: "idle",
  downloaded: 0,
  total: 0,
  percent: 0,
  error: null,

  openPrompt: () => set({ modalOpen: true, prompt: true, phase: "idle", error: null }),
  openInstall: () => set({ modalOpen: true, prompt: false, phase: "idle", error: null }),

  close: () => {
    if (busy(get().phase)) return;
    set({ modalOpen: false });
  },

  later: () => {
    useStore.getState().patchSettings({ tesseractPromptDismissed: true });
    void callPy("set_setting", "tesseractPromptDismissed", true);
    set({ modalOpen: false, prompt: false });
  },

  install: async () => {
    set({ modalOpen: true, prompt: false, phase: "downloading", downloaded: 0, total: 0, percent: 0, error: null });
    const res = await callPy<{ ok?: boolean; error?: string }>("install_tesseract").catch(() => null);
    if (res && res.ok === false) {
      if (res.error === "already_installed") {
        useStore.getState().setOcrAvailable(true);
        void refreshOcr();
        set({ phase: "done" });
      } else if (res.error !== "already_installing") {
        set({ phase: "error", error: res.error || "install_failed" });
      }
    }
  },

  demo: () => {
    const total = 50 * 1048576;
    set({ modalOpen: true, prompt: false, phase: "downloading", downloaded: 0, total, percent: 0, error: null });
    const stepBase = total / 45;
    const iv = setInterval(() => {
      if (!useTesseract.getState().modalOpen) {
        clearInterval(iv);
        return;
      }
      const cur = useTesseract.getState().downloaded;
      const next = Math.min(total, cur + stepBase * (0.5 + Math.random()));
      const pct = Math.floor((next * 100) / total);
      set({ downloaded: next, total, percent: pct, phase: "downloading" });
      if (next >= total) {
        clearInterval(iv);
        set({ phase: "extracting" });
        setTimeout(() => set({ phase: "done" }), 1400);
      }
    }, 80);
  },

  onProgress: (p) => {
    if (p.stage === "extract") {
      set({ phase: "extracting" });
    } else if (p.stage === "done") {
      set({ phase: "extracting" });
    } else {
      set({
        phase: "downloading",
        downloaded: p.downloaded ?? 0,
        total: p.total ?? 0,
        percent: typeof p.percent === "number" ? p.percent : 0,
      });
    }
  },

  onDone: (r) => {
    if (r.ok && r.available) {
      useStore.getState().setOcrAvailable(true);
      set({ phase: "done" });
    } else {
      set({ phase: "error", error: r.error || "Install failed. Check your connection and try again." });
    }
  },
}));

export function maybePromptTesseract(): void {
  const st = useStore.getState();
  if (st.ocrAvailable !== false) return;
  if (st.settings?.tesseractPromptDismissed) return;
  useTesseract.getState().openPrompt();
}
