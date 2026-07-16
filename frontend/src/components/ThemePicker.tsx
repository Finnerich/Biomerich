import { useStore } from "../store";
import { THEMES } from "../data/themes";
import { applyTheme } from "../data/themes";
import { withColorTransition } from "../themeFlash";

export function ThemePicker() {
  const themeId = useStore((s) => s.themeId);

  return (
    <div className="theme-picker">
      {THEMES.map((theme) => {
        const sel = theme.id === themeId ? " sel" : "";
        let thumb;
        if (theme.image) {
          thumb = <div className="theme-thumb" style={{ backgroundImage: `url("${theme.image}")` }}></div>;
        } else {
          thumb = <div className="theme-thumb none"><i className="fa-solid fa-ban"></i></div>;
        }
        return (
          <button key={theme.id} className={`theme-card${sel}`} data-theme={theme.id} onClick={() => withColorTransition(() => applyTheme(theme.id, true))}>
            {thumb}
            <span className="theme-name">{theme.name}</span>
          </button>
        );
      })}
    </div>
  );
}
