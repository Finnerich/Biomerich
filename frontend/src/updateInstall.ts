import { create } from "zustand";
import { callPy } from "./bridge";

export type UpdPhase = "idle" | "downloading" | "launching" | "done" | "error";

export interface UpdProgress {
  stage?: string;
  downloaded?: number;
  total?: number;
  percent?: number;
}
export interface UpdDone {
  ok?: boolean;
  error?: string;
  path?: string;
}

interface UpdInstallState {
  phase: UpdPhase;
  downloaded: number;
  total: number;
  percent: number;
  error: string | null;

  start: (url: string, name: string) => Promise<void>;
  reset: () => void;
  onProgress: (p: UpdProgress) => void;
  onDone: (r: UpdDone) => void;
}

export const useUpdateInstall = create<UpdInstallState>((set) => ({
  phase: "idle",
  downloaded: 0,
  total: 0,
  percent: 0,
  error: null,

  reset: () => set({ phase: "idle", downloaded: 0, total: 0, percent: 0, error: null }),

  start: async (url, name) => {
    set({ phase: "downloading", downloaded: 0, total: 0, percent: 0, error: null });
    const res = await callPy<{ ok?: boolean; started?: boolean; error?: string }>(
      "download_and_install_update", url, name,
    ).catch(() => null);
    if (!res || res.ok === false) {
      set({ phase: "error", error: res?.error || "Could not start the download." });
    }
  },

  onProgress: (p) => {
    if (p.stage === "launch" || p.stage === "done") {
      set({ phase: "launching" });
      return;
    }
    set({
      phase: "downloading",
      downloaded: p.downloaded ?? 0,
      total: p.total ?? 0,
      percent: typeof p.percent === "number" ? p.percent : 0,
    });
  },

  onDone: (r) => {
    if (r.ok) {
      set({ phase: "done", percent: 100 });
      setTimeout(() => { void callPy("close_app_window").catch(() => {}); }, 1200);
    } else {
      set({ phase: "error", error: r.error || "Update failed. Try again or use the GitHub link." });
    }
  },
}));
