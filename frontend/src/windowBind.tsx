import { useEffect } from "react";
import { useStore } from "./store";
import { callPy } from "./bridge";

export interface BindableAccount {
  id: number;
  window?: string | null;
  online?: boolean;
  enabled?: boolean;
}

export async function toggleWindowBind(accId: number): Promise<void> {
  const { bindingAccId, bindStates, setBind, setBindingAccId } = useStore.getState();

  if (bindingAccId === accId) {
    setBind(accId, null);
    setBindingAccId(null);
    await callPy("cancel_bind_window");
    return;
  }
  if (bindingAccId !== null) {
    setBind(bindingAccId, null);
    setBindingAccId(null);
    await callPy("cancel_bind_window");
  }
  if (bindStates[accId] === "bound") {
    setBind(accId, null);
    await callPy("clear_bind_window", accId);
    return;
  }

  setBind(accId, "waiting");
  setBindingAccId(accId);
  let res: { ok?: boolean } | null = null;
  try {
    res = await callPy<{ ok?: boolean }>("start_bind_window", accId);
  } catch {
    res = null;
  }
  if (!res?.ok && useStore.getState().bindingAccId === accId) {
    setBindingAccId(null);
    setBind(accId, null);
  }
}

export function useWindowBindPoll(): void {
  const running = useStore((s) => s.running);
  useEffect(() => {
    if (running) return;
    let alive = true;
    async function poll() {
      const states = await callPy<Array<Record<string, unknown>>>("get_account_windows").catch(() => null);
      if (!alive || !states) return;
      const st = useStore.getState();
      st.applyAccountWindows(states);
      const bound = new Set(states.filter((s) => s.window).map((s) => s.id));
      const bs = st.bindStates;
      Object.keys(bs).forEach((k) => {
        const id = Number(k);
        if (bs[id] === "bound" && !bound.has(id)) st.setBind(id, null);
      });
    }
    void poll();
    const id = setInterval(poll, 2500);
    return () => { alive = false; clearInterval(id); };
  }, [running]);
}

export function bindStatus(acc: BindableAccount, bindState: "waiting" | "bound" | undefined) {
  return {
    waiting: bindState === "waiting",
    bound: !!acc.window || bindState === "bound",
  };
}

export function BindButton(props: {
  acc: BindableAccount;
  disabled?: boolean;
  baseClass?: string;
  activeClass?: string;
  boundIcon?: string;
  labels?: { bind?: string; bound?: string; waiting?: string };
  onAfter?: () => void;
}) {
  const bindState = useStore((s) => s.bindStates[props.acc.id]);
  const { waiting, bound } = bindStatus(props.acc, bindState);

  const base = props.baseClass ?? "prio-chip prio-chip-bind";
  const active = props.activeClass ?? "on";
  const cls = `${base}${waiting ? " waiting" : bound ? " " + active : ""}`;
  const icon = waiting ? "fa-xmark" : bound ? (props.boundIcon ?? "fa-check") : "fa-link";
  const label = waiting
    ? (props.labels?.waiting ?? "Cancel")
    : bound
      ? (props.labels?.bound ?? "Bound")
      : (props.labels?.bind ?? "Bind Window");

  return (
    <button
      className={cls}
      disabled={props.disabled}
      onClick={() => void toggleWindowBind(props.acc.id).then(() => props.onAfter?.())}
    >
      <i className={`fa-solid ${icon}`}></i>
      <span className="bind-label">{label}</span>
    </button>
  );
}
