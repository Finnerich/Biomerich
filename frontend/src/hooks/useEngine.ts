import { useEffect } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import type { ActivityEntry, StatusPayload } from "../types";
import type { EngineSignal } from "../store";

export function useEngine(): void {
  const running = useStore((s) => s.running);

  useEffect(() => {
    document.body.classList.toggle("locked", running);
    if (!running) {
      useStore.getState().setEngineSignal(null);
      return;
    }

    const tick = setInterval(() => {
      const st = useStore.getState();
      st.setUptime(st.uptime + 1);
      st.tickTimeTracking();
    }, 1000);

    const poll = setInterval(async () => {
      const s = await callPy<StatusPayload>("get_status").catch(() => null);
      if (!s) return;
      useStore.getState().applyStatus(s);
      if (typeof s.uptime === "number") useStore.getState().setUptime(s.uptime);
      if (s.running === false) useStore.getState().setRunning(false, 0);
    }, 3000);

    const signalPoll = setInterval(async () => {
      const sig = await callPy<EngineSignal>("get_engine_signal").catch(() => null);
      if (sig) useStore.getState().setEngineSignal(sig);
    }, 1000);

    
    
    useStore.getState().clearActivity();
    let activityCursor = 0;
    const activityPoll = setInterval(async () => {
      const res = await callPy<{ entries?: ActivityEntry[]; last?: number }>(
        "get_activity_log", activityCursor,
      ).catch(() => null);
      if (!res) return;
      if (typeof res.last === "number") activityCursor = res.last;
      if (res.entries?.length) useStore.getState().appendActivity(res.entries);
    }, 2000);

    return () => {
      clearInterval(tick);
      clearInterval(poll);
      clearInterval(signalPoll);
      clearInterval(activityPoll);
    };
  }, [running]);
}
