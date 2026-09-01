import { useStore } from "../store";


export function BiomeHealthAlert() {
  const warnings = useStore((state) => state.biomeHealthWarnings);
  const setCurrentTab = useStore((state) => state.setCurrentTab);
  const dismiss = useStore((state) => state.dismissBiomeHealthWarning);

  if (!warnings.length) return null;

  const names = warnings.map((warning) => warning.account).join(", ");
  const longestSilence = Math.max(...warnings.map((warning) => warning.silentMinutes));

  function openLogCleanup() {
    setCurrentTab("settings");
    window.setTimeout(() => {
      document.getElementById("robloxLogCleanup")?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }, 120);
  }

  return (
    <div className="biome-health-alert" role="alert" aria-live="assertive">
      <div className="biome-health-alert__icon">
        <i className="fa-solid fa-triangle-exclamation"></i>
      </div>
      <div className="biome-health-alert__copy">
        <strong>Biomes broken? Try to clear Roblox logs.</strong>
        <span>
          No valid biome signal from {names} for {longestSilence}+ minutes.
          Stop the macro before clearing the logs.
        </span>
      </div>
      <button className="biome-health-alert__action" onClick={openLogCleanup}>
        <i className="fa-solid fa-screwdriver-wrench"></i> Open fix
      </button>
      <button
        className="biome-health-alert__dismiss"
        title="Dismiss this warning"
        aria-label="Dismiss biome health warning"
        onClick={() => warnings.forEach((warning) => dismiss(warning.accountId))}
      >
        <i className="fa-solid fa-xmark"></i>
      </button>
    </div>
  );
}
