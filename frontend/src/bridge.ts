type Pending = { resolve: (v: unknown) => void; reject: (e: unknown) => void };
type ExposedFn = (...args: unknown[]) => void;

const exposed: Record<string, ExposedFn> = {};
const pending: Record<number, Pending> = {};
let seq = 0;
let ws: WebSocket | null = null;
let ready = false;
let queue: string[] = [];

let readyResolve: (() => void) | null = null;
const readyPromise = new Promise<void>((r) => {
  readyResolve = r;
});

function connect(): void {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    ready = true;
    if (readyResolve) {
      readyResolve();
      readyResolve = null;
    }
    queue.forEach((m) => ws!.send(m));
    queue = [];
  };

  ws.onmessage = (ev) => {
    let data: { type?: string; id?: number; error?: string; result?: unknown; name?: string; args?: unknown[] };
    try {
      data = JSON.parse(ev.data);
    } catch {
      return;
    }

    if (data.type === "rpc_result" && data.id != null) {
      const p = pending[data.id];
      if (p) {
        delete pending[data.id];
        if (data.error) p.reject(new Error(data.error));
        else p.resolve(data.result);
      }
    } else if (data.type === "call" && data.name) {
      const fn = exposed[data.name];
      if (typeof fn === "function") {
        try {
          fn(...(data.args || []));
        } catch (e) {
          console.error(`[bridge] JS fn '${data.name}' threw:`, e);
        }
      }
    }
  };

  ws.onclose = () => {
    ready = false;
    for (const id of Object.keys(pending)) {
      const p = pending[+id];
      delete pending[+id];
      p.reject(new Error("RPC aborted: bridge disconnected"));
    }
    setTimeout(connect, 1000);
  };

  ws.onerror = () => {
    try {
      ws?.close();
    } catch {
    }
  };
}

function send(obj: unknown): void {
  const msg = JSON.stringify(obj);
  if (ready && ws && ws.readyState === 1) ws.send(msg);
  else queue.push(msg);
}

export function callPyWithTimeout<T = unknown>(timeoutMs: number, name: string, ...args: unknown[]): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const id = ++seq;
    pending[id] = { resolve: resolve as (v: unknown) => void, reject };
    send({ type: "rpc", id, name, args });
    setTimeout(() => {
      if (pending[id]) {
        delete pending[id];
        reject(new Error(`RPC timeout: ${name}`));
      }
    }, Math.max(1000, timeoutMs));
  });
}

export function callPy<T = unknown>(name: string, ...args: unknown[]): Promise<T> {
  return callPyWithTimeout<T>(30000, name, ...args);
}

export function expose(fn: ExposedFn, name?: string): void {
  exposed[name || fn.name] = fn;
}

export function waitReady(): Promise<void> {
  return readyPromise;
}

connect();
