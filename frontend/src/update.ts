import { useStore, type Releases } from "./store";
import { callPy } from "./bridge";

export function isUpdateAvailable(r: Releases | null): boolean {
  return !!(r && r.available && r.releases && r.releases.length);
}

export function latestUrl(r: Releases | null): string | undefined {
  return r?.releases?.[0]?.url;
}

let loaded = false;

export async function loadReleases(): Promise<void> {
  if (loaded) return;
  loaded = true;
  const r = await callPy<Releases>("get_releases").catch(() => null);
  if (!r) return;
  useStore.getState().setReleases(r);
  if (isUpdateAvailable(r)) {
    useStore.getState().setUpdateModalOpen(true);
  }
}
