import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import { THEMES } from "../data/themes";
import { applyTheme, getCustomThemeImage, loadCustomThemeImage, setCustomThemeImage } from "../data/themes";
import { callPy } from "../bridge";
import { withColorTransition } from "../themeFlash";

export function ThemePicker() {
  const themeId = useStore((s) => s.themeId);
  const pushToast = useStore((s) => s.pushToast);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [customImage, setCustomImage] = useState(() => getCustomThemeImage());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void loadCustomThemeImage().then((image) => {
      if (active) setCustomImage(image);
    });
    return () => { active = false; };
  }, []);

  async function uploadCustomImage(file: File | undefined) {
    if (!file) return;
    if ((!/image\/(jpeg|png|webp)/i.test(file.type) && !/\.(jpe?g|png|webp)$/i.test(file.name)) || file.size > 15 * 1024 * 1024) {
      pushToast({ icon: "fa-triangle-exclamation", title: "Background not accepted", detail: "Choose a JPG, PNG or WebP image up to 15 MB." });
      return;
    }
    setBusy(true);
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      const result = await callPy<{ ok?: boolean; error?: string }>("save_custom_theme_background", dataUrl);
      if (!result?.ok) throw new Error(result?.error || "save_failed");
      setCustomThemeImage(dataUrl);
      setCustomImage(dataUrl);
      withColorTransition(() => applyTheme("custom", true));
      pushToast({ icon: "fa-image", title: "Custom background saved", detail: "The subtle drifting animation is enabled automatically." });
    } catch {
      pushToast({ icon: "fa-triangle-exclamation", title: "Background could not be saved", detail: "Try another JPG, PNG or WebP image." });
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function removeCustomImage() {
    setBusy(true);
    const result = await callPy<{ ok?: boolean }>("clear_custom_theme_background").catch(() => null);
    setBusy(false);
    if (!result?.ok) {
      pushToast({ icon: "fa-triangle-exclamation", title: "Background could not be removed", detail: "The saved image is still in use." });
      return;
    }
    setCustomThemeImage("");
    setCustomImage("");
    if (themeId === "custom") withColorTransition(() => applyTheme("none", true));
  }

  return (
    <div className="theme-picker">
      {THEMES.map((theme) => {
        const sel = theme.id === themeId ? " sel" : "";
        let thumb;
        const image = theme.id === "custom" ? customImage : theme.image;
        if (image) {
          thumb = <div className="theme-thumb" style={{ backgroundImage: `url("${image}")` }}></div>;
        } else {
          thumb = <div className="theme-thumb none"><i className={`fa-solid ${theme.id === "custom" ? "fa-image" : "fa-ban"}`}></i></div>;
        }
        return (
          <button key={theme.id} className={`theme-card${sel}`} data-theme={theme.id} onClick={() => theme.id === "custom" && !customImage ? inputRef.current?.click() : withColorTransition(() => applyTheme(theme.id, true))}>
            {thumb}
            <span className="theme-name">{theme.name}</span>
          </button>
        );
      })}
      <div className="custom-theme-actions">
        <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => void uploadCustomImage(event.target.files?.[0])} />
        <button className="btn-add" disabled={busy} onClick={() => inputRef.current?.click()}>
          <i className={`fa-solid ${busy ? "fa-spinner fa-spin" : "fa-upload"}`}></i>
          {customImage ? "Replace custom image" : "Upload background image"}
        </button>
        {customImage && (
          <button className="btn-add custom-theme-remove" disabled={busy} onClick={() => void removeCustomImage()}>
            <i className="fa-solid fa-trash"></i> Remove
          </button>
        )}
        <span>JPG, PNG or WebP · max 15 MB</span>
      </div>
    </div>
  );
}
