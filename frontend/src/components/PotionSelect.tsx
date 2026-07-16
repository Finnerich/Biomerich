import { useEffect, useRef, useState } from "react";
import { POTIONS, POTION_TIERS, potionTier, potionBuffs, BUFF_META, type Buff } from "../data/potions";

export function BuffBadges({ buffs }: { buffs: Buff[] }) {
  if (!buffs.length) return null;
  return (
    <span className="ps-buffs">
      {buffs.map((buff, i) => {
        const meta = BUFF_META[buff.kind];
        return (
          <span key={i} className="ps-buff" style={{ ["--bg-grad" as string]: meta.grad }} title={`${meta.label}${buff.amount ? " " + buff.amount : ""} buff`}>
            <i className={`fa-solid ${meta.icon}`}></i>{buff.amount || meta.label}
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
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 10);
    const onDocMouseDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => { window.clearTimeout(focusTimer); document.removeEventListener("mousedown", onDocMouseDown); };
  }, [open]);

  const selectedTier = value ? potionTier(value) : null;
  const normalizedQuery = query.trim().toLowerCase();
  const matches = (name: string) => !normalizedQuery || name.toLowerCase().includes(normalizedQuery);
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
            <span className="ps-dot" style={{ background: selectedTier?.color || "transparent" }}></span>
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
                {items.map((potion) => (
                  <div
                    key={potion.name}
                    className={`cs-option ps-option${potion.name === value ? " selected" : ""}`}
                    onMouseDown={(e) => { e.preventDefault(); onChange(potion.name); setOpen(false); }}
                  >
                    <span className="ps-dot" style={{ background: tier.color }}></span>
                    <span className="ps-oname">{potion.name}</span>
                    <BuffBadges buffs={potion.buffs} />
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
