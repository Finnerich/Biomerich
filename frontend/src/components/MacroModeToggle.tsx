import { useStore } from "../store";
import { getMacroMode, setMacroMode } from "../data/macroMode";

export function MacroModeToggle() {
  const settings = useStore((s) => s.settings);
  const running = useStore((s) => s.running);
  const mode = getMacroMode(settings);

  return (
    <div className="glass card macro-mode-bar" id="macroModeToggle" data-reveal>
      <div className="mm-info">
        <span className="mm-title"><i className="fa-solid fa-layer-group"></i> Macro Mode</span>
        <span className="mm-desc">
          {mode === "normal"
            ? "Normal: one account, simple setup. Switch to Multi-Macro for many accounts at once."
            : "Multi-Macro: full control over many accounts. Switch to Normal for a simple one-account setup."}
        </span>
      </div>
      <div className="macro-mode-seg">
        <button
          className={`mms-btn${mode === "normal" ? " sel" : ""}`}
          disabled={running}
          onClick={() => void setMacroMode("normal")}
        >
          <i className="fa-solid fa-user"></i> Normal
        </button>
        <button
          className={`mms-btn${mode === "multi" ? " sel" : ""}`}
          disabled={running}
          onClick={() => void setMacroMode("multi")}
        >
          <i className="fa-solid fa-users"></i> Multi-Macro
        </button>
      </div>
    </div>
  );
}
