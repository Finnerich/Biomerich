import { useStore } from "../store";
import { callPy } from "../bridge";
import type { BackendState } from "../types";
import {
  AntiAfkSettings,
  MiscSettings,
  RamTrimSettings,
  ToggleRow,
} from "./moduleBuilder/parts";

export function Safety() {
  const running = useStore((s) => s.running);
  const settings = useStore((s) => s.settings);
  const patchSettings = useStore((s) => s.patchSettings);
  const applyState = useStore((s) => s.applyState);

  async function setSetting(key: string, on: boolean) {
    patchSettings({ [key]: on });
    applyState(await callPy<BackendState>("set_setting", key, on));
  }

  return (
    <section className="tab active-tab" id="safety">
      <header className="page-head">
        <h1>Safety</h1>
        <p>Everything that protects your accounts and your PC, in one place.</p>
      </header>

      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-person-running"></i> Anti-AFK</div>
        </div>
        <ToggleRow
          name="Anti-AFK"
          desc="Nudges every open Roblox window so the 20-minute idle kick never happens. Off means Roblox disconnects you after ~20 minutes of no input, usually the #1 reason an overnight run dies."
          checked={!!settings.antiAfkEnabled}
          disabled={running}
          onChange={(c) => void setSetting("antiAfkEnabled", c)}
        />
        <div className="afk-divider"></div>
        <AntiAfkSettings />
      </div>

      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-memory"></i> Auto-Trim RAM</div>
        </div>
        <ToggleRow
          name="Auto-Trim RAM"
          desc="Frees system memory on a timer while the engine runs. Off means long sessions with several Roblox windows can slowly eat your RAM until the PC crawls."
          checked={!!settings.ramTrimEnabled}
          onChange={(c) => void setSetting("ramTrimEnabled", c)}
        />
        <div className="afk-divider"></div>
        <RamTrimSettings />
      </div>

      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-shield-halved"></i> Failsafes</div>
        </div>
        <MiscSettings />
      </div>
    </section>
  );
}
