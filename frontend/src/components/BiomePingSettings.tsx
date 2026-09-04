import { useStore } from "../store";
import { callPy } from "../bridge";
import { CustomSelect } from "./CustomSelect";
import { BIOMES, TIERS, type Biome } from "../data/biomes";
import type { BackendState } from "../types";

interface PingCfg {
  type: "none" | "user" | "role" | "everyone";
  id: string;
}
type PingMap = Record<string, PingCfg>;

function defaultFor(biome: Biome): PingCfg {
  return biome.tier === "rare" ? { type: "everyone", id: "" } : { type: "none", id: "" };
}
function isOn(config: PingCfg): boolean {
  return config.type === "everyone" || /\d/.test(config.id);
}

export function BiomePingSettings() {
  const automation = useStore((s) => s.automation);
  const patchAutomation = useStore((s) => s.patchAutomation);
  const applyState = useStore((s) => s.applyState);
  const pings = (automation.biomePings as PingMap) || {};

  function cfgFor(biome: Biome): PingCfg {
    return pings[biome.key] || defaultFor(biome);
  }
  function save(key: string, next: PingCfg) {
    patchAutomation({ biomePings: { ...pings, [key]: next } });
    void callPy<BackendState>("set_biome_ping", key, next.type, next.id).then((state) => applyState(state));
  }
  function onType(biome: Biome, type: string) {
    save(biome.key, { type: type as PingCfg["type"], id: cfgFor(biome).id });
  }
  function onId(biome: Biome, raw: string) {
    save(biome.key, { type: cfgFor(biome).type, id: raw.replace(/\D+/g, "") });
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
        Pick who gets pinged per biome. Rare biomes default to <b>@everyone</b>, but can use a custom
        role, user, or no ping at all.
      </p>
      {groups.map((group) => (
        <div className="bl-group" key={group.tier.key}>
          <div className="bl-sep">
            <span className="bl-sep-dot" style={{ background: group.tier.grad || group.tier.color }}></span>
            <span
              className="bl-sep-label"
              style={group.tier.grad
                ? { background: group.tier.grad, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }
                : { color: group.tier.color }}
            >
              {group.tier.label}
            </span>
            <span className="bl-sep-line"></span>
          </div>

          {group.rows.map((biome) => {
            const cfg = cfgFor(biome);
            return (
              <div className={`bl-row${isOn(cfg) ? " on" : ""}`} key={biome.key}>
                <span className="bl-dot" style={{ background: biome.grad, boxShadow: "none" }}></span>
                <span className="bl-name">{biome.name}</span>
                <CustomSelect
                  className="bl-select"
                  options={[
                    { value: "everyone", label: "@everyone" },
                    { value: "role", label: "Role ID" },
                    { value: "user", label: "User ID" },
                    { value: "none", label: "No ping" },
                  ]}
                  value={cfg.type}
                  onChange={(v) => onType(biome, v)}
                />
                {cfg.type === "user" || cfg.type === "role" ? (
                  <input
                    className="bl-input"
                    inputMode="numeric"
                    placeholder="ID (numbers only)"
                    value={cfg.id}
                    onChange={(e) => onId(biome, e.target.value)}
                  />
                ) : (
                  <span className={`bl-target ${cfg.type}`}>
                    <i className={`fa-solid ${cfg.type === "everyone" ? "fa-bullhorn" : "fa-bell-slash"}`}></i>
                    {cfg.type === "everyone" ? "Default" : "Disabled"}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
