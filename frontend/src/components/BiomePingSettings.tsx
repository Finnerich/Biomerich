import { useStore } from "../store";
import { callPy } from "../bridge";
import { CustomSelect } from "./CustomSelect";
import { BIOMES, TIERS, type Biome } from "../data/biomes";
import type { BackendState } from "../types";

interface PingCfg {
  type: "user" | "role" | "everyone";
  id: string;
}
type PingMap = Record<string, PingCfg>;

function isForcedEveryone(b: Biome): boolean {
  return b.tier === "rare";
}
function defaultFor(): PingCfg {
  return { type: "user", id: "" };
}
function isOn(cfg: PingCfg): boolean {
  return cfg.type === "everyone" || /\d/.test(cfg.id);
}

export function BiomePingSettings() {
  const automation = useStore((s) => s.automation);
  const patchAutomation = useStore((s) => s.patchAutomation);
  const applyState = useStore((s) => s.applyState);
  const pings = (automation.biomePings as PingMap) || {};

  function cfgFor(b: Biome): PingCfg {
    return pings[b.key] || defaultFor();
  }
  function save(key: string, next: PingCfg) {
    patchAutomation({ biomePings: { ...pings, [key]: next } });
    void callPy<BackendState>("set_biome_ping", key, next.type, next.id).then((st) => applyState(st));
  }
  function onType(b: Biome, type: string) {
    save(b.key, { type: type as PingCfg["type"], id: cfgFor(b).id });
  }
  function onId(b: Biome, raw: string) {
    save(b.key, { type: cfgFor(b).type, id: raw.replace(/\D+/g, "") });
  }

  const groups = TIERS.map((tier) => {
    let rows = BIOMES.filter((b) =>
      tier.key === "rare" ? b.tier === "rare" || b.tier === "semi-rare" : b.tier === tier.key,
    );
    if (tier.key === "rare") {
      rows = [...rows].sort((a, b) => (a.tier === "rare" ? 0 : 1) - (b.tier === "rare" ? 0 : 1));
    }
    return { tier, rows };
  }).filter((g) => g.rows.length);

  return (
    <div className="bl-list">
      <p className="bl-note">
        Pick who gets pinged per biome. Enter a numeric Discord ID to turn one on. Rare biomes always
        ping <b>@everyone</b>.
      </p>
      {groups.map((g) => (
        <div className="bl-group" key={g.tier.key}>
          <div className="bl-sep">
            <span className="bl-sep-dot" style={{ background: g.tier.grad || g.tier.color }}></span>
            <span
              className="bl-sep-label"
              style={g.tier.grad
                ? { background: g.tier.grad, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }
                : { color: g.tier.color }}
            >
              {g.tier.label}
            </span>
            <span className="bl-sep-line"></span>
          </div>

          {g.rows.map((b) => {
            if (isForcedEveryone(b)) {
              return (
                <div className="bl-row on" key={b.key}>
                  <span className="bl-dot" style={{ background: b.grad, boxShadow: "none" }}></span>
                  <span className="bl-name">{b.name}</span>
                  <span className="bl-everyone"><i className="fa-solid fa-bullhorn"></i> @everyone</span>
                </div>
              );
            }
            const cfg = cfgFor(b);
            return (
              <div className={`bl-row${isOn(cfg) ? " on" : ""}`} key={b.key}>
                <span className="bl-dot" style={{ background: b.grad, boxShadow: "none" }}></span>
                <span className="bl-name">{b.name}</span>
                <CustomSelect
                  className="bl-select"
                  options={[{ value: "user", label: "User ID" }, { value: "role", label: "Role ID" }]}
                  value={cfg.type === "everyone" ? "user" : cfg.type}
                  onChange={(v) => onType(b, v)}
                />
                <input
                  className="bl-input"
                  inputMode="numeric"
                  placeholder="ID (numbers only)"
                  value={cfg.id}
                  onChange={(e) => onId(b, e.target.value)}
                />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
