import type { ReactNode } from "react";

export function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <div className={`fx-collapse${open ? " open" : ""}`} aria-hidden={!open}>
      <div className="fx-collapse-inner">{children}</div>
    </div>
  );
}
