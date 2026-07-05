import { POTIONS, POTION_TIERS, type Buff, type PotionTier } from "./potions";

export type AutobuyMerchant = "mari" | "jester";

export const AUTOBUY_MERCHANTS: AutobuyMerchant[] = ["mari", "jester"];

export interface MerchantItem {
  name: string;
  tier: string;
  buffs: Buff[];
}

export const RUNE_GRAD = "linear-gradient(135deg,#3b82f6,#22c55e 50%,#f97316)";
export const MERCHANT_EXTRA_TIERS: PotionTier[] = [
  { key: "rune", label: "Rune", color: "#22c55e" },
  { key: "tool", label: "Tool", color: "#ffffff" },
];

const ALL_TIERS = [...POTION_TIERS, ...MERCHANT_EXTRA_TIERS];
const TIER_BY_KEY: Record<string, PotionTier> = Object.fromEntries(ALL_TIERS.map((t) => [t.key, t]));

export function merchantTierMeta(key: string): PotionTier | null {
  return TIER_BY_KEY[key] || null;
}

const fromPotion = (name: string): MerchantItem => {
  const p = POTIONS.find((x) => x.name === name);
  return { name, tier: p?.tier || "common", buffs: p?.buffs ? [...p.buffs] : [] };
};

const rune = (name: string): MerchantItem => ({ name, tier: "rune", buffs: [] });

export const MERCHANT_AUTOBUY_CATALOG: Record<AutobuyMerchant, MerchantItem[]> = {
  mari: [
    { name: "Void Coin", tier: "oblivion", buffs: [] },
    { name: "Gear A", tier: "tool", buffs: [] },
    { name: "Gear B", tier: "tool", buffs: [] },
    { name: "Lucky Penny", tier: "tool", buffs: [{ kind: "luck" }] },
    { name: "Fortune Spoid I", tier: "uncommon", buffs: [{ kind: "luck" }] },
    { name: "Fortune Spoid II", tier: "uncommon", buffs: [{ kind: "luck" }] },
    { name: "Fortune Spoid III", tier: "uncommon", buffs: [{ kind: "luck" }] },
    { name: "Mixed Potion", tier: "common", buffs: [{ kind: "speed" }, { kind: "luck" }] },
    { name: "Lucky Potion", tier: "common", buffs: [{ kind: "luck" }] },
    { name: "Lucky Potion L", tier: "common", buffs: [{ kind: "luck" }] },
    { name: "Lucky Potion XL", tier: "common", buffs: [{ kind: "luck" }] },
    { name: "Speed Potion", tier: "common", buffs: [{ kind: "speed" }] },
    { name: "Speed Potion L", tier: "common", buffs: [{ kind: "speed" }] },
    { name: "Speed Potion XL", tier: "common", buffs: [{ kind: "speed" }] },
  ],
  jester: [
    fromPotion("Oblivion Potion"),
    fromPotion("Heavenly Potion"),
    fromPotion("Potion of Bound"),
    fromPotion("Strange Potion I"),
    fromPotion("Strange Potion II"),
    { name: "Lucky Potion", tier: "common", buffs: [{ kind: "luck" }] },
    { name: "Speed Potion", tier: "common", buffs: [{ kind: "speed" }] },
    rune("Rune of Everything"),
    rune("Rune of Nothing"),
    rune("Rune of Corruption"),
    rune("Rune of Galaxy"),
    rune("Rune of Hell"),
    rune("Rune of Rainstorm"),
    rune("Rune of Frost"),
    rune("Rune of Wind"),
    { name: "Stella's Star", tier: "tool", buffs: [] },
    { name: "Merchant Tracker", tier: "tool", buffs: [] },
    { name: "Random Potion Sack", tier: "tool", buffs: [{ kind: "random" }] },
  ],
};

export const MERCHANT_AUTOBUY_ITEMS: Record<AutobuyMerchant, string[]> = {
  mari: MERCHANT_AUTOBUY_CATALOG.mari.map((i) => i.name),
  jester: MERCHANT_AUTOBUY_CATALOG.jester.map((i) => i.name),
};

export function merchantItemMeta(mid: AutobuyMerchant, name: string): MerchantItem | null {
  return MERCHANT_AUTOBUY_CATALOG[mid].find((i) => i.name === name) || null;
}

export const MERCHANT_META: Record<AutobuyMerchant, { name: string; grad: string; shadow: string }> = {
  mari: { name: "Mari", grad: "linear-gradient(135deg,#ffffff,#cbd5e1 52%,#7c8899)", shadow: "#dbe2ea" },
  jester: { name: "Jester", grad: "linear-gradient(135deg,#c084fc,#9b59b6 52%,#3b0764)", shadow: "#9b59b6" },
};

export const MERCHANT_DISPLAY_NAMES: Record<string, string> = {
  mari: "Mari",
  jester: "Jester",
  rin: "Rin",
};
