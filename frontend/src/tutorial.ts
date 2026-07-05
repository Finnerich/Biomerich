import { create } from "zustand";
import { useStore } from "./store";
import { callPy } from "./bridge";
import { TUTORIALS, type TutDef, type TutStep } from "./data/tutorials";
import { maybePromptTesseract } from "./tesseract";

interface TutorialState {
  active: boolean;
  def: TutDef | null;
  i: number;
  onDone: ((skipped: boolean) => void) | null;
  start: (def: TutDef | null, onDone?: (skipped: boolean) => void) => void;
  goto: (n: number) => void;
  next: () => void;
  back: () => void;
  end: (skipped: boolean) => void;
  applyStepView: (step: TutStep) => void;
}

export const useTutorial = create<TutorialState>((set, get) => ({
  active: false,
  def: null,
  i: 0,
  onDone: null,
  start: (def, onDone) => {
    if (!def || !def.steps.length) {
      onDone?.(true);
      return;
    }
    set({ active: true, def, i: 0, onDone: onDone ?? null });
    if (def.steps[0].tab) useStore.getState().setCurrentTab(def.steps[0].tab);
  },
  goto: (n) => {
    const { def } = get();
    if (!def) return;
    const i = Math.max(0, Math.min(def.steps.length - 1, n));
    set({ i });
    if (def.steps[i].tab) useStore.getState().setCurrentTab(def.steps[i].tab);
  },
  next: () => {
    const { def, i } = get();
    if (!def) return;
    if (i >= def.steps.length - 1) get().end(false);
    else get().goto(i + 1);
  },
  back: () => get().goto(get().i - 1),
  end: (skipped) => {
    const { onDone } = get();
    useStore.getState().setTutorialDrawer(null);
    set({ active: false, def: null, i: 0, onDone: null });
    onDone?.(skipped);
  },
  applyStepView: (step) => {
    const main = useStore.getState();
    if (!step.openDrawer) {
      main.setTutorialDrawer(null);
      return;
    }
    let accId: number | undefined;
    if (step.openDrawer.account) {
      const accs = (main.accounts || []) as Array<{ id: number; enabled?: boolean }>;
      const first = accs.find((a) => a.enabled !== false) ?? accs[0];
      accId = first?.id;
      
      if (accId == null) {
        main.setTutorialDrawer(null);
        return;
      }
    }
    main.setTutorialDrawer({ kind: step.openDrawer.kind, accId });
  },
}));

export function maybeStartTutorial(settings: Record<string, unknown> | undefined, version: string): void {
  if (!settings) return;
  if (!settings.firstStartDone) {
    useTutorial.getState().start(TUTORIALS.firstStart, () => {
      void callPy("set_tutorial_seen", "firstStart");
      if (version) void callPy("set_tutorial_seen", "update", version);
      maybePromptTesseract();
    });
    return;
  }
  if (!version || settings.tutorialVersion === version) return;
  const def = TUTORIALS.updates[version];
  if (def) {
    useTutorial.getState().start(def, () => void callPy("set_tutorial_seen", "update", version));
  } else {
    void callPy("set_tutorial_seen", "update", version);
  }
}
