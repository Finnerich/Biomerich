# 🌟 Biomerich - Advanced Sol's RNG Logger & Macro

Welcome to the official repository for **Biomerich**, a powerful, highly analytical logger and utility tool built for Roblox Sol's RNG.

Designed with a clean, modern Web User Interface and powered by a robust Python backend, Biomerich is built to be the ultimate companion for dedicated Sol's RNG players. It seamlessly tracks your game data in real-time and lays the groundwork for advanced automation.

## ✨ Current Features (v0.1.0)

The current MVP focuses on precise tracking and user experience:

- **Real-Time Log Parsing:** Accurately reads and processes Roblox logs on the fly using our custom engine (`roblox_logs.py`)[cite: 1].
- **Biome Tracking:** Instant detection and logging of current in-game biomes (`biomes.py`)[cite: 1].
- **Discord Webhooks:** Push notifications directly to your Discord server for rare events and biome changes (`webhooks.py`)[cite: 1].
- **Interactive Web UI:** A sleek, lightweight dashboard built with HTML/CSS/JS, powered by Eel (`web/index.html`)[cite: 1].

## 🚀 Roadmap (Upcoming Features)

Biomerich is constantly evolving. The macro engine (`macro_engine.py`) is already implemented in the core[cite: 1], and the following features are actively being developed for upcoming releases:

- 🎣 **Fishing Macro:** Fully automated fishing for continuous resource gathering.
- 🚫 **Anti AFK:** Smart movement to prevent game disconnections.
- 🛡️ **Anti Fake Biome Ping:** Algorithmic filtering to ignore false or manipulated biome alerts.
- 🛠️ **Auto Crafting:** Streamlined crafting system to save time and optimize inventory.
- 🌌 **Limbo Macro:** Specialized automation for Limbo events.

## ⚙️ Technical Requirements

If you wish to run the source code directly instead of using the provided executable:

- Python 3.x
- Dependencies: `eel >= 0.16.0`, `requests >= 2.31.0`[cite: 1]

_(Note: End users can simply download the compiled `.exe` from the Releases tab without installing Python.)_

## 📄 License

This project is licensed under the Apache 2.0 License. See the `LICENSE` file for details.

yes i wrote this readme with ai because i suck at it
