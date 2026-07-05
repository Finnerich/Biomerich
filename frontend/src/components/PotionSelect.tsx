import { useEffect, useRef, useState } from "react";
import { POTIONS, POTION_TIERS, potionTier, potionBuffs, BUFF_META, type Buff } from "../data/potions";

export function BuffBadges({ buffs }: { buffs: Buff[] }) {
  if (!buffs.length) return null;
  return (
    <span className="ps-buffs">
      {buffs.map((b, i) => {
        const m = BUFF_META[b.kind];
        return (
          <span key={i} className="ps-buff" style={{ ["--bg-grad" as string]: m.grad }} title={`${m.label}${b.amount ? " " + b.amount : ""} buff`}>
            <i className={`fa-solid ${m.icon}`}></i>{b.amount || m.label}
          </span>
        );
      })}
    </span>
  );
}

export function PotionSelect({ value, onChange, disabled, className }: {
  value: string;
  onChange: (name: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    const t = window.setTimeout(() => inputRef.current?.focus(), 10);
    const onDocMouseDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => { window.clearTimeout(t); document.removeEventListener("mousedown", onDocMouseDown); };
  }, [open]);

  const selTier = value ? potionTier(value) : null;
  const q = query.trim().toLowerCase();
  const matches = (name: string) => !q || name.toLowerCase().includes(q);
  const anyMatch = POTIONS.some((p) => matches(p.name));

  return (
    <div
      ref={wrapRef}
      className={`cs-wrap potion-select${open ? " open" : ""}${disabled ? " disabled" : ""}${className ? " " + className : ""}`}
    >
      <div
        className="cs-trigger"
        tabIndex={0}
        onMouseDown={(e) => { e.preventDefault(); if (!disabled) setOpen((v) => !v); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!disabled) setOpen((v) => !v); }
          if (e.key === "Escape") setOpen(false);
        }}
      >
        {value ? (
          <span className="ps-val">
            <span className="ps-dot" style={{ background: selTier?.color || "transparent" }}></span>
            <span className="ps-oname">{value}</span>
            <BuffBadges buffs={potionBuffs(value)} />
          </span>
        ) : (
          <span className="cs-label placeholder">Select a potion…</span>
        )}
        <i className="fa-solid fa-chevron-down cs-arrow"></i>
      </div>

      <div className="cs-dropdown ps-dropdown">
        <div className="ps-search">
          <i className="fa-solid fa-magnifying-glass"></i>
          <input
            ref={inputRef}
            value={query}
            placeholder="Search potions…"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
          />
        </div>
        <div className="ps-scroll">
          {POTION_TIERS.map((tier) => {
            const items = POTIONS.filter((p) => p.tier === tier.key && matches(p.name));
            if (!items.length) return null;
            return (
              <div key={tier.key} className="ps-group">
                <div className="ps-group-head" style={{ color: tier.color }}>
                  <span className="ps-dot" style={{ background: tier.color }}></span>{tier.label}
                </div>
                {items.map((p) => (
                  <div
                    key={p.name}
                    className={`cs-option ps-option${p.name === value ? " selected" : ""}`}
                    onMouseDown={(e) => { e.preventDefault(); onChange(p.name); setOpen(false); }}
                  >
                    <span className="ps-dot" style={{ background: tier.color }}></span>
                    <span className="ps-oname">{p.name}</span>
                    <BuffBadges buffs={p.buffs} />
                  </div>
                ))}
              </div>
            );
          })}
          {!anyMatch && <div className="ps-empty">No potions match “{query}”.</div>}
        </div>
      </div>
    </div>
  );
}
