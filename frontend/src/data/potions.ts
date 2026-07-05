export interface PotionTier {
  key: string;
  label: string;
  color: string;
}

export const POTION_TIERS: PotionTier[] = [
  { key: "54_xyz", label: "54_xyz", color: "#1e40af" },
  { key: "hallow", label: "Hallow", color: "#f97316" },
  { key: "oblivion", label: "Oblivion", color: "#5b21b6" },
  { key: "mythical", label: "Mythical", color: "#ef4444" },
  { key: "legendary", label: "Legendary", color: "#f5c518" },
  { key: "epic", label: "Epic", color: "#a855f7" },
  { key: "rare", label: "Rare", color: "#3b82f6" },
  { key: "uncommon", label: "Uncommon", color: "#22c55e" },
  { key: "common", label: "Common", color: "#9ca3af" },
];

export type BuffKind = "luck" | "multi" | "instant" | "speed" | "warp" | "random";
export interface Buff {
  kind: BuffKind;
  amount?: string;
}

export const BUFF_META: Record<BuffKind, { label: string; grad: string; icon: string }> = {
  luck: { label: "Luck", grad: "linear-gradient(135deg,#4ade80,#16a34a)", icon: "fa-clover" },
  multi: { label: "Luck ×", grad: "linear-gradient(135deg,#3b82f6,#1e3a8a)", icon: "fa-clover" },
  instant: { label: "Instant Luck", grad: "linear-gradient(135deg,#fb7185,#dc2626)", icon: "fa-bolt" },
  speed: { label: "Speed", grad: "linear-gradient(135deg,#67e8f9,#06b6d4)", icon: "fa-gauge-high" },
  warp: { label: "Warp", grad: "linear-gradient(135deg,#7dd3fc,#38bdf8)", icon: "fa-shuffle" },
  random: { label: "Random", grad: "linear-gradient(135deg,#cbd5e1,#64748b)", icon: "fa-dice" },
};

export interface Potion {
  name: string;
  tier: string;
  buffs: Buff[];
}

export const POTIONS: Potion[] = [
  { name: "???", tier: "54_xyz", buffs: [{ kind: "multi", amount: "2×" }] },
  { name: "Pump King's Blood", tier: "hallow", buffs: [{ kind: "instant", amount: "+700K" }] },
  { name: "Oblivion Potion", tier: "oblivion", buffs: [{ kind: "instant", amount: "+600K" }] },
  { name: "Godlike Potion", tier: "mythical", buffs: [{ kind: "instant", amount: "+400K" }] },
  { name: "Transcendent Potion", tier: "mythical", buffs: [{ kind: "warp" }] },
  { name: "Heavenly Potion", tier: "legendary", buffs: [{ kind: "instant", amount: "+150K" }] },
  { name: "Warp Potion", tier: "legendary", buffs: [{ kind: "warp" }] },
  { name: "Potion of Bound", tier: "epic", buffs: [{ kind: "instant", amount: "+50K" }] },
  { name: "Santa Potion", tier: "epic", buffs: [{ kind: "luck" }, { kind: "speed" }] },
  { name: "Hwachae", tier: "epic", buffs: [{ kind: "luck" }, { kind: "speed" }] },
  { name: "Zombie Potion", tier: "rare", buffs: [{ kind: "luck" }] },
  { name: "Jewelry Potion", tier: "rare", buffs: [{ kind: "luck" }] },
  { name: "Gladiator Potion", tier: "rare", buffs: [{ kind: "luck" }] },
  { name: "Diver Potion", tier: "rare", buffs: [{ kind: "speed" }] },
  { name: "Rage Potion", tier: "rare", buffs: [{ kind: "speed" }] },
  { name: "Strange Potion II", tier: "rare", buffs: [{ kind: "random" }] },
  { name: "Strange Potion I", tier: "rare", buffs: [{ kind: "random" }] },
  { name: "Fortune Potion III", tier: "uncommon", buffs: [{ kind: "luck" }] },
  { name: "Fortune Potion II", tier: "uncommon", buffs: [{ kind: "luck" }] },
  { name: "Fortune Potion I", tier: "uncommon", buffs: [{ kind: "luck" }] },
  { name: "Haste Potion III", tier: "uncommon", buffs: [{ kind: "speed" }] },
  { name: "Haste Potion II", tier: "uncommon", buffs: [{ kind: "speed" }] },
  { name: "Haste Potion I", tier: "uncommon", buffs: [{ kind: "speed" }] },
];

const TIER_BY_KEY: Record<string, PotionTier> = Object.fromEntries(POTION_TIERS.map((t) => [t.key, t]));

export function potionTier(name: string): PotionTier | null {
  const p = POTIONS.find((x) => x.name === name);
  return p ? TIER_BY_KEY[p.tier] || null : null;
}

export function potionBuffs(name: string): Buff[] {
  return POTIONS.find((x) => x.name === name)?.buffs || [];
}
