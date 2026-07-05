import { useStore } from "../store";
import { THEMES } from "../data/themes";
import { applyTheme } from "../data/themes";
import { withColorTransition } from "../themeFlash";

export function ThemePicker() {
  const themeId = useStore((s) => s.themeId);

  return (
    <div className="theme-picker">
      {THEMES.map((t) => {
        const sel = t.id === themeId ? " sel" : "";
        let thumb;
        if (t.image) {
          thumb = <div className="theme-thumb" style={{ backgroundImage: `url("${t.image}")` }}></div>;
        } else {
          thumb = <div className="theme-thumb none"><i className="fa-solid fa-ban"></i></div>;
        }
        return (
          <button key={t.id} className={`theme-card${sel}`} data-theme={t.id} onClick={() => withColorTransition(() => applyTheme(t.id, true))}>
            {thumb}
            <span className="theme-name">{t.name}</span>
          </button>
        );
      })}
    </div>
  );
}
