export type Tier = "normal" | "event" | "semi-rare" | "rare" | "dev";

export interface Biome {
  key: string;
  name: string;
  tier: Tier;
  rarity: number | null;
  grad: string;
  shadow: string;
}

export interface TierDef {
  key: string;
  label: string;
  color: string;
  desc: string;
  grad?: string;
}

export const DEFAULT_AVATAR =
  "https://tr.rbxcdn.com/38c6edcb50633730ff4cf39ac8859840/150/150/AvatarHeadshot/Png";

export const BIOMES: Biome[] = [
  { key: "windy", name: "Windy", tier: "normal", rarity: 500, grad: "linear-gradient(135deg,#67e8f9,#38bdf8)", shadow: "#38bdf8" },
  { key: "rainy", name: "Rainy", tier: "normal", rarity: 750, grad: "linear-gradient(135deg,#60a5fa,#2563eb)", shadow: "#2563eb" },
  { key: "snowy", name: "Snowy", tier: "normal", rarity: 600, grad: "linear-gradient(135deg,#e0f2fe,#93c5fd)", shadow: "#bae6fd" },
  { key: "sandstorm", name: "Sand Storm", tier: "normal", rarity: 3000, grad: "linear-gradient(135deg,#fbbf24,#d97706)", shadow: "#f59e0b" },
  { key: "hell", name: "Hell", tier: "normal", rarity: 6666, grad: "linear-gradient(135deg,#fb923c,#dc2626)", shadow: "#ef4444" },
  { key: "starfall", name: "Starfall", tier: "normal", rarity: 7500, grad: "linear-gradient(135deg,#818cf8,#3730a3)", shadow: "#6366f1" },
  { key: "corruption", name: "Corruption", tier: "normal", rarity: 9000, grad: "linear-gradient(135deg,#c084fc,#7e22ce)", shadow: "#a855f7" },
  { key: "null", name: "Null", tier: "normal", rarity: 10100, grad: "linear-gradient(135deg,#94a3b8,#334155)", shadow: "#64748b" },
  { key: "heaven", name: "Heaven", tier: "normal", rarity: 8333, grad: "linear-gradient(135deg,#fde68a,#f59e0b)", shadow: "#fcd34d" },
  { key: "graveyard", name: "Graveyard", tier: "event", rarity: null, grad: "linear-gradient(135deg,#b2b2b2,#565656)", shadow: "#b2b2b2" },
  { key: "singularity", name: "Singularity", tier: "semi-rare", rarity: null, grad: "linear-gradient(135deg,#fde047,#fb7c1e 52%,#1c0d03)", shadow: "#fb923c" },
  { key: "aurora", name: "Aurora", tier: "event", rarity: null, grad: "linear-gradient(135deg,#bf60ff,#84ffda)", shadow: "#bf60ff" },
  { key: "blazing_sun", name: "BLAZING SUN", tier: "event", rarity: null, grad: "linear-gradient(135deg,#fde047,#f97316 58%,#991b1b)", shadow: "#fb923c" },
  { key: "glitched", name: "Glitched", tier: "rare", rarity: null, grad: "linear-gradient(135deg,#86efac,#22c55e 50%,#052e16)", shadow: "#22c55e" },
  { key: "dreamspace", name: "Dreamspace", tier: "rare", rarity: null, grad: "linear-gradient(135deg,#ff9ed8,#f368d4 52%,#b15cff)", shadow: "#f368d4" },
  { key: "cyberspace", name: "Cyberspace", tier: "rare", rarity: null, grad: "linear-gradient(135deg,#22d3ee,#2563eb 52%,#0b1b54)", shadow: "#38bdf8" },
  { key: "the_citadel_of_orders", name: "THE CITADEL OF ORDERS", tier: "dev", rarity: null, grad: "linear-gradient(135deg,#fde047,#f59e0b)", shadow: "#f5b301" },
];

export const TIERS: TierDef[] = [
  { key: "rare", label: "Rare", color: "var(--t-rare)", desc: "extremely rare" },
  { key: "normal", label: "Normal", color: "var(--t-normal)", desc: "common" },
  { key: "event", label: "Event", color: "var(--t-event)", desc: "limited" },
  { key: "dev", label: "Dev Biomes", color: "#38bdf8", desc: "developer", grad: "linear-gradient(135deg,#7dd3fc,#38bdf8)" },
];

export const RARE_KEYS: string[] = BIOMES.filter((b) => b.tier === "rare").map((b) => b.key);
export const SEMI_RARE_KEYS: string[] = BIOMES.filter((b) => b.tier === "semi-rare").map((b) => b.key);

export function biomeMeta(key: string | null | undefined): Biome | null {
  return BIOMES.find((b) => b.key === key) || null;
}
