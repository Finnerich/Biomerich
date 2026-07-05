import { useTesseract } from "../tesseract";

export function TesseractInstallButton({
  className = "",
  label = "Install Tesseract",
  onClick,
}: {
  className?: string;
  label?: string;
  onClick?: () => void;
}) {
  return (
    <button
      className={`tess-install-btn ${className}`.trim()}
      onClick={onClick ?? (() => useTesseract.getState().openInstall())}
    >
      <i className="fa-solid fa-download"></i> {label}
    </button>
  );
}
