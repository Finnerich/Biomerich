# Third-Party Notices

SolRich itself is licensed under the Apache License 2.0 (see [LICENSE](LICENSE)). It
bundles or depends on the third-party open-source components listed below, each of
which remains under its own license. This file satisfies their attribution
requirements; it does **not** relicense SolRich's own code.

## Desktop backend (Python)
| Component | License |
|---|---|
| FastAPI | MIT |
| Starlette | BSD-3-Clause |
| Uvicorn | BSD-3-Clause |
| websockets | BSD-3-Clause |
| Requests | Apache-2.0 |
| pytesseract | Apache-2.0 |
| Pillow (PIL) | HPND (PIL/MIT-style) |
| pywin32 | PSF |
| PyInstaller (build only) | GPL-2.0 with a bundling exception (does not apply its GPL to the packaged app) |
| Tesseract OCR (downloaded/bundled at runtime) | Apache-2.0 |

## Desktop frontend & mobile app (JS/TS)
| Component | License |
|---|---|
| React, React-DOM | MIT |
| Zustand | MIT |
| qrcode.react | ISC |
| Vite, @vitejs/plugin-react | MIT |
| TypeScript | Apache-2.0 |
| Capacitor (@capacitor/*) | MIT |
| cordova-plugin-background-mode, cordova-plugin-device | Apache-2.0 / MIT |

## Fonts & icons
| Component | License | Note |
|---|---|---|
| Poppins | SIL Open Font License 1.1 | bundling in apps is permitted |
| DM Mono | SIL Open Font License 1.1 | |
| Sarpanch | SIL Open Font License 1.1 | |
| Font Awesome Free | Icons: CC BY 4.0 · Fonts: SIL OFL 1.1 · Code: MIT | the CC BY icons require attribution — this notice provides it |

Full license texts are available from each project's repository. If a component is
added or removed, update this file accordingly.
