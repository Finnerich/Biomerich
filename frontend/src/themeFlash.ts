export function withColorTransition(apply: () => void): void {
  document.body.classList.add("accent-anim");
  apply();
  window.setTimeout(() => document.body.classList.remove("accent-anim"), 550);
}
