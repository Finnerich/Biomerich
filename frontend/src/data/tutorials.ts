
export interface TutStep {
  tab: string;
  target: string | null;
  icon: string;
  title: string;
  body: string;
  
  
  openDrawer?: { kind: string; account?: boolean };
}
export interface TutDef {
  id: string;
  title: string;
  steps: TutStep[];
}

const firstStart: TutDef = {
  id: "firstStart",
  title: "Welcome",
  steps: [
    { tab: "stats", target: null, icon: "fa-hand-sparkles", title: "Welcome to SolRich",
      body: "This is a quick tour of the four things you need for your first run: add an account, pick what it should do, match it to your screen, and press Start. Hit Next to walk through each one, or Skip if you'd rather poke around yourself." },
    { tab: "accounts", target: '[data-tab="accounts"]', icon: "fa-user-plus", title: "1. Add your account",
      body: "Everything starts in the Accounts tab. Add your Roblox account with a name. Linking its .ROBLOSECURITY cookie is optional: it enables automatic launching and window matching, while manual launch and binding still work without it. Only link your own account on a trusted PC. The cookie is stored locally with Windows encryption and is used only with official Roblox services." },
    { tab: "accounts", target: null, icon: "fa-rocket", title: "Launch and bind",
      body: "With a token added, press Launch to open Roblox, join the private server, and bind the window automatically, so the macro always knows which window to control. Without a token you just open Roblox yourself, then bind the window by hand." },
    { tab: "modules", target: '[data-tab="modules"]', icon: "fa-toggle-on", title: "2. Pick what it does",
      body: "Open the Module Builder and flip on what you want: Strange Controller, Biome Randomizer, Merchant or Aura Detection, Auto Pop, or Fishing. Stay in Normal mode for a single account. The gear on each module opens its own settings." },
    { tab: "calibration", target: '[data-tab="calibration"]', icon: "fa-crosshairs", title: "3. Match your screen",
      body: "In Calibration, load the preset for your resolution, scale and window mode. That lines every click up with your screen so the macro presses the right spots. You can fine-tune any single point afterward." },
    { tab: "stats", target: "#toggleBtn", icon: "fa-power-off", title: "4. Press Start",
      body: "That's the whole setup. Make sure your account is launched, then press Start here (or the F5 hotkey). Stop the same way whenever you want." },
    { tab: "stats", target: '[data-rail-tip="Setup Guide"]', icon: "fa-graduation-cap", title: "Want the full version?",
      body: "This was the short tour. The Setup Guide down here reopens a longer walkthrough that covers every tab in detail, any time you need it." },
  ],
};

const setupGuide: TutDef = {
  id: "setupGuide",
  title: "Setup Guide",
  steps: [
    { tab: "stats", target: null, icon: "fa-graduation-cap", title: "The full setup",
      body: "This walks you through every step from an empty app to your first run, and points out what each part does. Use Back and Next to move at your own pace, and Skip whenever you feel ready." },
    { tab: "accounts", target: '[data-tab="accounts"]', icon: "fa-users-gear", title: "Add your accounts",
      body: "Start in Accounts. Add each Roblox account with a name and its private-server link. You can run one account or many, each keeps its own setup." },
    { tab: "accounts", target: null, icon: "fa-key", title: "Link the token (optional)",
      body: "Linking each account's .ROBLOSECURITY cookie is optional. It lets SolRich launch Roblox, join the private server and match windows automatically. Without one, launch Roblox and bind each window yourself. Only link your own account on a trusted PC. Cookies are protected locally with Windows encryption and used only with official Roblox services." },
    { tab: "accounts", target: null, icon: "fa-rocket", title: "Launch and bind the window",
      body: "With a token, press Launch to open Roblox and join the private server, and the window binds itself, so the macro knows exactly which window is which account, even with several open at once. No token? Open Roblox yourself, then bind the window by hand from the account." },
    { tab: "modules", target: "#macroModeToggle", icon: "fa-layer-group", title: "Normal vs Multi-Macro",
      body: "Use the switch in the top control bar to choose the layout. Normal runs a single account and keeps everything simple, while Multi-Macro runs several accounts side by side. The same switch is also available in the Monitor tab." },
    { tab: "modules", target: null, icon: "fa-toggle-on", title: "Turn on your modules",
      body: "Flip on what each account should do. Strange Controller and Biome Randomizer use inventory items on a timer. Merchant Detection watches for merchants and can auto-buy. Aura Detection reads the auras you roll. Auto Pop fires items the instant a chosen biome starts." },
    { tab: "modules", target: ".mb-drawer.open", icon: "fa-fish", title: "Fishing", openDrawer: { kind: "fishing", account: true },
      body: "Fishing casts, reels and sells your catch on a walking route. Turn the Fishing chip on for an account, then open its settings (this panel) to set how often it sells, which route to walk, your walk speed, and the failsafes that catch a missed reel or a shop that never opened." },
    { tab: "webhooks", target: '[data-tab="webhooks"]', icon: "fa-paper-plane", title: "Webhooks",
      body: "Add a Discord webhook and route it to an account to get biome, aura and merchant pings straight to your server. Merchant notifications can include screenshots. Biome logging needs at least one active webhook, so add one here even if you skip the rest." },
    { tab: "calibration", target: '[data-tab="calibration"]', icon: "fa-crosshairs", title: "Calibrate to your screen",
      body: "Calibration tells SolRich where things sit on your screen. Load the preset that matches your resolution first, then fine-tune any point that's slightly off. Show on screen draws the saved points over Roblox so you can check them before running." },
    { tab: "calibration", target: null, icon: "fa-eye", title: "Tesseract (text reading)",
      body: "Merchant and Aura Detection, plus the OCR failsafes, read text on screen to know what's happening. That needs Tesseract. If it isn't installed, a single button in Calibration installs it for you." },
    { tab: "stats", target: "#modeSeg", icon: "fa-sliders", title: "Choose a run mode",
      body: "Top-left you pick how the macro runs. Idle just logs biomes and keeps the account awake. Automation runs the modules you turned on. Eden parks an account at the Eden spawn and grabs Eden the instant it appears." },
    { tab: "performance", target: '[data-tab="performance"]', icon: "fa-gauge-high", title: "Performance",
      body: "If you run several accounts, the Performance tab throttles the windows you're not looking at, cutting their CPU, GPU and memory so your PC stays smooth. Whichever window you focus always runs at full speed." },
    { tab: "stats", target: "#toggleBtn", icon: "fa-power-off", title: "Start your first run",
      body: "That's everything. Launch your accounts, then press Start here or hit F5. Stop the same way. You're all set, good luck out there." },
  ],
};

const bindWindows: TutDef = {
  id: "bindWindows",
  title: "Window Binding",
  steps: [
    { tab: "modules", target: ".mb-bind-tutorial-btn", icon: "fa-link", title: "What does Bind Window do?",
      body: "Multi-Macro controls several Roblox windows independently. Binding tells SolRich exactly which open Roblox window belongs to each enabled account, so clicks and modules never go to the wrong account." },
    { tab: "modules", target: ".mb-list .prio-chip-bind", icon: "fa-computer-mouse", title: "Bind the matching window",
      body: "Open the account's Roblox window first. Press Bind Window, then click anywhere inside that account's Roblox window. The button waits for that one click and saves the match." },
    { tab: "modules", target: ".mb-list .prio-chip-bind", icon: "fa-circle-check", title: "Repeat until every account is bound",
      body: "A green Bound button means that account is ready. Repeat this for every enabled account before starting the engine. Clicking Bound again clears the match so you can bind a different window." },
  ],
};

export const TUTORIALS: { firstStart: TutDef; setupGuide: TutDef; bindWindows: TutDef; updates: Record<string, TutDef> } = {
  firstStart,
  setupGuide,
  bindWindows,
  updates: {
    "1.0.0": {
      id: "update-1.0.0",
      title: "What's new in v1.0.0",
      steps: [
        { tab: "stats", target: null, icon: "fa-gift", title: "Welcome to v1.0.0",
          body: "This is the biggest update yet, with new modes, a whole new module and a proper performance system. Here's a quick run through the highlights, about a minute." },
        { tab: "modules", target: "#macroModeToggle", icon: "fa-layer-group", title: "Normal mode",
          body: "There's a new Normal mode: a clean, one-account setup for people who don't multi-box. The full multi-account layout you already know is now called Multi-Macro mode, and you switch between them right here." },
        { tab: "modules", target: ".mb-drawer.open", icon: "fa-fish", title: "New: Fishing", openDrawer: { kind: "fishing", account: true },
          body: "Fishing is a brand-new module. It casts, reels and sells your catch on a walking route, per account, with auto-sell and failsafes for a missed reel or a shop that didn't open. Turn on the Fishing chip and open its settings to set it up." },
        { tab: "stats", target: "#modeSeg", icon: "fa-circle-dot", title: "New: Eden mode",
          body: "Eden is a new run mode. Park your main account at the Eden spawn, set the Eden Click Point in Calibration, and it spams E and clicks that point non-stop to claim Eden the moment it shows up." },
        { tab: "performance", target: '[data-tab="performance"]', icon: "fa-gauge-high", title: "New: Performance tab",
          body: "The new Performance tab throttles background Roblox windows to cut their CPU, GPU and memory while you multi-box. Focus a window and it runs at full speed again, click away and it throttles back down." },
        { tab: "creator", target: '[data-tab="creator"]', icon: "fa-heart", title: "Credits",
          body: "The old Creator tab is now Credits: shout-outs to the macros and the testers who helped build SolRich." },
        { tab: "stats", target: null, icon: "fa-check", title: "That's the tour",
          body: "Those are the highlights. The complete changelog lives in the Patchlog tab. Thanks for using SolRich, have fun." },
      ],
    },
  },
};
