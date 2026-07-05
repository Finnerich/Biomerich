# SolRich

A biome logger and automation tool for the Roblox game Sol's RNG. SolRich was previously called Biomerich.

SolRich reads your game in real time, keeps a full history of the biomes you roll, sends Discord alerts for the things you care about, and runs the repetitive parts of Sol's RNG for you across one account or many. It runs on Windows with a desktop interface.

## Features

- Real time biome logging. Reads the Roblox log as you play and records every biome, with lifetime counts and a tier breakdown in the Stats tab.
- Discord webhooks. Send biome, merchant, and fishing alerts to your own server, with screenshots. Each account can post to a different webhook.
- Automation modules you turn on per account:
  - Strange Controller and Biome Randomizer, which use inventory items on a timer to reroll or shuffle your biome.
  - Merchant Detection, which teleports to a merchant, reads who arrived, and can buy for you.
  - Auto Pop, which fires items the moment a chosen biome starts.
  - Fishing, which casts, reels, and sells your catch on a walking route.
- Eden mode, which parks one account at the Eden spawn and claims Eden the instant it appears.
- Multiple accounts. Add as many as you want, each with its own modules and settings, and run them side by side.
- Performance tab. Throttles the Roblox windows you are not looking at to keep your PC responsive, and gives the focused window full speed.
- Safety tools. Anti-AFK to prevent disconnects, automatic RAM trimming, and failsafes that catch a missed action before it breaks a run.
- Calibration presets. Match SolRich to your resolution once, then fine tune any point. A live overlay shows you where every click will land.
- Quality of life. Start and stop hotkeys, a guided setup walkthrough, an updater built into the app, and a Patchlog tab that shows what changed in every version.

## Getting started

Most people should download the latest `SolRich.exe` from the [Releases](../../releases) page and run it. No Python needed, and your settings live in your local app data folder.

The first time you open it, a short setup guide walks you through adding an account, matching your screen, and starting your first run.

## Running from source

If you would rather run the code directly:

1. Install Python 3.11 or newer.
2. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Build the interface (Node 20 or newer):
   ```
   cd frontend
   npm install
   npm run build
   ```
4. Start it from the project root:
   ```
   python main.py
   ```

## Text reading

Merchant Detection, Auto Pop, and the fishing failsafes read text on your screen, which needs Tesseract. You do not have to install it yourself. If it is missing, a single button inside SolRich downloads and sets it up for you.

## License

SolRich is open source under the Apache License 2.0. See the [LICENSE](LICENSE) file for the full text, and [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) for the components it builds on.

## Disclaimer

SolRich is a fan made tool for Sol's RNG. It is not affiliated with the game or its developers. Use it at your own risk.
