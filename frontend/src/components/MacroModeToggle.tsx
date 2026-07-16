import { useStore } from "../store";
import { getMacroMode, setMacroMode } from "../data/macroMode";

export function MacroModeToggle(props: { id?: string; className?: string }) {
  const settings = useStore((s) => s.settings);
  const running = useStore((s) => s.running);
  const mode = getMacroMode(settings);

  return (
    <div
      id={props.id}
      className={`mode-seg mode-seg-2 macro-mode-switch ${mode}${props.className ? ` ${props.className}` : ""}`}
      role="group"
      aria-label="Macro mode"
      title={running ? "Stop the engine before changing Macro mode" : "Switch between Normal and Multi-Macro mode"}
    >
      <span className="mode-seg-glider"></span>
      <button
        className={`mode-seg-opt${mode === "normal" ? " active" : ""}`}
        data-mode="normal"
        disabled={running}
        onClick={() => void setMacroMode("normal")}
      >
        <i className="fa-solid fa-user"></i><span>Normal</span>
      </button>
      <button
        className={`mode-seg-opt${mode === "multi" ? " active" : ""}`}
        data-mode="multi"
        disabled={running}
        onClick={() => void setMacroMode("multi")}
      >
        <i className="fa-solid fa-users"></i><span>Multi-Macro</span>
      </button>
    </div>
  );
}
