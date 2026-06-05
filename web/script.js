let accounts = [];
let webhooks = [];
let isRunning = false;

let uptimeSeconds = 0;
let uptimeInterval = null;
let statusInterval = null;

let unknownBiomes = {};
let appVersion = "";
let appSettings = {};
const collapsedTiers = new Set();

const hasEel = typeof eel !== "undefined";

const DEFAULT_AVATAR =
  "https://tr.rbxcdn.com/38c6edcb50633730ff4cf39ac8859840/150/150/AvatarHeadshot/Png";

const BIOMES = [
  {
    key: "windy",
    name: "Windy",
    tier: "normal",
    rarity: 500,
    grad: "linear-gradient(135deg,#67e8f9,#38bdf8)",
    shadow: "#38bdf8",
  },
  {
    key: "rainy",
    name: "Rainy",
    tier: "normal",
    rarity: 750,
    grad: "linear-gradient(135deg,#60a5fa,#2563eb)",
    shadow: "#2563eb",
  },
  {
    key: "snowy",
    name: "Snowy",
    tier: "normal",
    rarity: 600,
    grad: "linear-gradient(135deg,#e0f2fe,#93c5fd)",
    shadow: "#bae6fd",
  },
  {
    key: "sandstorm",
    name: "Sand Storm",
    tier: "normal",
    rarity: 3000,
    grad: "linear-gradient(135deg,#fbbf24,#d97706)",
    shadow: "#f59e0b",
  },
  {
    key: "hell",
    name: "Hell",
    tier: "normal",
    rarity: 6666,
    grad: "linear-gradient(135deg,#fb923c,#dc2626)",
    shadow: "#ef4444",
  },
  {
    key: "starfall",
    name: "Starfall",
    tier: "normal",
    rarity: 7500,
    grad: "linear-gradient(135deg,#818cf8,#3730a3)",
    shadow: "#6366f1",
  },
  {
    key: "corruption",
    name: "Corruption",
    tier: "normal",
    rarity: 9000,
    grad: "linear-gradient(135deg,#c084fc,#7e22ce)",
    shadow: "#a855f7",
  },
  {
    key: "null",
    name: "Null",
    tier: "normal",
    rarity: 10100,
    grad: "linear-gradient(135deg,#94a3b8,#334155)",
    shadow: "#64748b",
  },
  {
    key: "heaven",
    name: "Heaven",
    tier: "normal",
    rarity: 8333,
    grad: "linear-gradient(135deg,#fde68a,#f59e0b)",
    shadow: "#fcd34d",
  },
  {
    key: "graveyard",
    name: "Graveyard",
    tier: "event",
    rarity: null,
    grad: "linear-gradient(135deg,#b2b2b2,#565656)",
    shadow: "#b2b2b2",
  },
  {
    key: "singularity",
    name: "Singularity",
    tier: "normal",
    rarity: null,
    grad: "linear-gradient(135deg,#ff5900,#c9772a)",
    shadow: "#ff5900",
  },
  {
    key: "aurora",
    name: "Aurora",
    tier: "event",
    rarity: null,
    grad: "linear-gradient(135deg,#bf60ff,#84ffda)",
    shadow: "#bf60ff",
  },
  {
    key: "glitched",
    name: "Glitched",
    tier: "rare",
    rarity: null,
    grad: "linear-gradient(135deg,#40d683,#249e42)",
    shadow: "#40d683",
  },
  {
    key: "dreamspace",
    name: "Dreamspace",
    tier: "rare",
    rarity: null,
    grad: "linear-gradient(135deg,#db4abb,#de72ea)",
    shadow: "#db4abb",
  },
  {
    key: "cyberspace",
    name: "Cyberspace",
    tier: "rare",
    rarity: null,
    grad: "linear-gradient(135deg,#2b32ff,#3b64e2)",
    shadow: "#2b32ff",
  },
];

const TIERS = [
  {
    key: "rare",
    label: "Rare",
    color: "var(--t-rare)",
    desc: "extremely rare",
  },
  { key: "normal", label: "Normal", color: "var(--t-normal)", desc: "common" },
  { key: "event", label: "Event", color: "var(--t-event)", desc: "limited" },
];

const RARE_KEYS = BIOMES.filter((b) => b.tier === "rare").map((b) => b.key);

let biomeCounts = BIOMES.reduce((o, b) => ((o[b.key] = 0), o), {});

const ACCENTS = [
  { c: "#4f6ef7", c2: "#3b5bdb" },
  { c: "#22d3ee", c2: "#2dd4bf" },
  { c: "#34d399", c2: "#10b981" },
  { c: "#fb7185", c2: "#f43f5e" },
  { c: "#fbbf24", c2: "#f59e0b" },
];

async function callPy(fn, ...args) {
  if (!hasEel) return null;
  try {
    return await eel[fn](...args)();
  } catch (err) {
    console.error(`[eel] ${fn} failed:`, err);
    return null;
  }
}

function applyState(state) {
  if (!state) return;
  if (Array.isArray(state.accounts)) accounts = state.accounts;
  if (Array.isArray(state.webhooks)) webhooks = state.webhooks;
  if (state.biomeCounts) biomeCounts = state.biomeCounts;
  if (state.unknownBiomes) unknownBiomes = state.unknownBiomes;
  if (state.settings) appSettings = state.settings;
  if (state.version) setVersion(state.version);
  renderAll();
  setRunning(!!state.running, state.uptime || 0);
}

function setVersion(v) {
  appVersion = v || "";
  const el = document.getElementById("versionTag");
  if (el && appVersion) el.textContent = "v" + appVersion;
}

function renderAll() {
  renderBiomes();
  renderLogs();
  renderAccounts();
  renderWebhooks();
  renderStats();
  renderAntiAfk();
}

function switchTab(tabId, btn) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.remove("active-tab", "tab-enter"));
  document
    .querySelectorAll(".nav-item")
    .forEach((n) => n.classList.remove("active"));
  const tab = document.getElementById(tabId);
  tab.classList.add("active-tab");
  void tab.offsetWidth;
  tab.classList.add("tab-enter");
  btn.classList.add("active");
  if (tabId === "stats") renderStats();
}

function clientValidate() {
  const errors = [];
  if (webhooks.length === 0) {
    errors.push("You must add at least one webhook.");
  } else {
    webhooks.forEach((w) => {
      if (!w.url || !w.url.trim())
        errors.push(`Webhook "${w.name || "?"}" has no valid URL.`);
    });
  }
  const hasRoute = webhooks.some(
    (w) => (w.active ?? true) && (w.routedAccounts || []).length,
  );
  if (webhooks.length && !hasRoute)
    errors.push("At least one webhook must be linked to an account.");

  const routed = new Set();
  webhooks.forEach((w) => {
    if (w.active ?? true)
      (w.routedAccounts || []).forEach((id) => routed.add(id));
  });
  accounts.forEach((a) => {
    const link = (a.link || "").trim();
    if (routed.has(a.id) && !link)
      errors.push(`Account "${a.name}" has no private server link.`);
    else if (link && !link.toLowerCase().includes("roblox.com"))
      errors.push(
        `Private server link for "${a.name}" must be a roblox.com URL.`,
      );
  });
  return errors;
}

async function toggleMacro() {
  if (!isRunning) {
    if (hasEel) {
      const res = await callPy("start_macro");
      if (res && res.ok === false) {
        showErrors(res.errors || ["Unknown error."]);
        return;
      }
      setRunning(true, res ? res.uptime : 0);
      startPolling();
    } else {
      const errs = clientValidate();
      if (errs.length) {
        showErrors(errs);
        return;
      }
      setRunning(true, 0);
    }
  } else {
    stopPolling();
    if (hasEel) await callPy("stop_macro");
    setRunning(false);
  }
}

function showErrors(errors) {
  alert("Macro could not be started:\n\n• " + errors.join("\n• "));
}

function setRunning(running, uptime = 0) {
  isRunning = running;

  const dot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const btn = document.getElementById("toggleBtn");

  if (running) {
    dot.className = "dot running";
    statusText.textContent = "Online";
    btn.className = "power-btn running";
    btn.innerHTML = '<i class="fa-solid fa-stop"></i><span>Stop</span>';
    uptimeSeconds = uptime || 0;
    paintTime(uptimeSeconds);
    clearInterval(uptimeInterval);
    uptimeInterval = setInterval(tickUptime, 1000);
  } else {
    dot.className = "dot stopped";
    statusText.textContent = "Offline";
    btn.className = "power-btn stopped";
    btn.innerHTML = '<i class="fa-solid fa-power-off"></i><span>Start</span>';
    clearInterval(uptimeInterval);
    uptimeInterval = null;
    uptimeSeconds = 0;
    paintTime(0);
  }

  lockUI(running);
  renderLogs();
  renderAntiAfk();
}

function lockUI(running) {
  document.body.classList.toggle("locked", running);

  document
    .querySelectorAll(".input-bar .field, .btn-add")
    .forEach((el) => (el.disabled = running));
}

function tickUptime() {
  uptimeSeconds++;
  paintTime(uptimeSeconds);
}

function paintTime(sec) {
  const t = formatTime(sec);
  const up = document.getElementById("uptime");
  if (up) up.textContent = t;
  const st = document.getElementById("statTime");
  if (st) st.textContent = t;
}

function formatTime(sec) {
  const h = Math.floor(sec / 3600)
    .toString()
    .padStart(2, "0");
  const m = Math.floor((sec % 3600) / 60)
    .toString()
    .padStart(2, "0");
  const s = (sec % 60).toString().padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function applyAccountStates(states) {
  const byId = {};
  states.forEach((st) => (byId[st.id] = st));
  accounts.forEach((a) => {
    const st = byId[a.id];
    a.currentBiome = st ? st.currentBiome : null;
    a.online = st ? !!st.online : false;
  });
}

function startPolling() {
  clearInterval(statusInterval);
  statusInterval = setInterval(async () => {
    const s = await callPy("get_status");
    if (!s) return;
    if (s.biomeCounts) biomeCounts = s.biomeCounts;
    if (s.unknownBiomes) unknownBiomes = s.unknownBiomes;
    if (Array.isArray(s.accountStates)) applyAccountStates(s.accountStates);
    if (typeof s.uptime === "number") {
      uptimeSeconds = s.uptime;
      paintTime(uptimeSeconds);
    }
    renderBiomes();
    renderStats();
    renderLogs();
    if (!s.running) {
      stopPolling();
      setRunning(false);
    }
  }, 3000);
}

function stopPolling() {
  clearInterval(statusInterval);
  statusInterval = null;
}

function totalBiomes() {
  return Object.values(biomeCounts).reduce((a, b) => a + b, 0);
}

function updateStats() {
  const total = totalBiomes();
  const el = document.getElementById("biomeTotal");
  if (el) el.textContent = total.toLocaleString("en-US");
  renderStats();
}

function biomeMeta(key) {
  return BIOMES.find((b) => b.key === key) || null;
}
function maxCount() {
  const known = Object.values(biomeCounts);
  const unk = Object.values(unknownBiomes);
  return Math.max(1, ...known, ...unk);
}
function fmtRarity(x) {
  if (!x || x === "?") return "1 in ?";
  return "1 in " + Number(x).toLocaleString("en-US");
}
function biomeRowHTML(b, max) {
  const count = biomeCounts[b.key] || 0;
  const pct = Math.max(2, (count / max) * 100);
  const rareTag = b.tier === "rare" ? '<span class="rare-tag">RARE</span>' : "";
  const rarityCell = b.rarity
    ? `<span class="b2-rarity">${fmtRarity(b.rarity)}</span>`
    : `<span class="b2-rarity"></span>`;
  return `
    <div class="biome-row2 ${b.tier === "rare" ? "rare" : ""}" style="--biome-grad:${b.grad}; --biome-shadow:${b.shadow}">
      <span class="b2-swatch"></span>
      <span class="b2-name">${b.name} ${rareTag}</span>
      <span class="b2-bar"><i style="width:${pct}%"></i></span>
      ${rarityCell}
      <span class="b2-count ${count === 0 ? "zero" : ""}">${count.toLocaleString("en-US")}</span>
    </div>`;
}
function unknownRowHTML(name, count, max) {
  const pct = Math.max(2, (count / max) * 100);
  return `
    <div class="biome-row2 unknown" style="--biome-grad:linear-gradient(135deg,#9aa0b5,#5b6075); --biome-shadow:#7e8499">
      <span class="b2-swatch"></span>
      <span class="b2-name">${esc(name)} <span class="rare-tag unknown-tag">NEW</span></span>
      <span class="b2-bar"><i style="width:${pct}%"></i></span>
      <span class="b2-rarity">${fmtRarity("?")}</span>
      <span class="b2-count ${count === 0 ? "zero" : ""}">${count.toLocaleString("en-US")}</span>
    </div>`;
}
function toggleTier(key) {
  if (collapsedTiers.has(key)) collapsedTiers.delete(key);
  else collapsedTiers.add(key);
  renderBiomes();
}
function groupHTML(key, label, color, total, rowsHTML) {
  const collapsed = collapsedTiers.has(key);
  const group = document.createElement("div");
  group.className = "biome-group" + (collapsed ? " collapsed" : "");
  group.innerHTML = `
    <div class="tier-head" onclick="toggleTier('${key}')">
      <i class="fa-solid fa-chevron-down tier-chevron"></i>
      <span class="tier-dot" style="background:${color}"></span>
      <span class="tier-label" style="color:${color}">${label}</span>
      <span class="tier-line"></span>
      <span class="tier-meta">${total.toLocaleString("en-US")}</span>
    </div>
    <div class="biome-rows">${rowsHTML}</div>`;
  return group;
}
function renderBiomes() {
  const wrap = document.getElementById("biomeGrid");
  if (!wrap) return;
  const max = maxCount();
  wrap.innerHTML = "";

  TIERS.forEach((tier) => {
    let list = BIOMES.filter((b) => b.tier === tier.key);
    if (tier.key === "rare") {
      list = list.sort(
        (a, b) => RARE_KEYS.indexOf(a.key) - RARE_KEYS.indexOf(b.key),
      );
    } else {
      list = list.sort((a, b) => (b.rarity || 0) - (a.rarity || 0));
    }
    if (list.length === 0) return;
    const groupTotal = list.reduce((s, b) => s + (biomeCounts[b.key] || 0), 0);
    const rows = list.map((b) => biomeRowHTML(b, max)).join("");
    wrap.appendChild(
      groupHTML(tier.key, tier.label, tier.color, groupTotal, rows),
    );
  });

  const unknownNames = Object.keys(unknownBiomes);
  if (unknownNames.length) {
    unknownNames.sort(
      (a, b) => (unknownBiomes[b] || 0) - (unknownBiomes[a] || 0),
    );
    const total = unknownNames.reduce((s, n) => s + (unknownBiomes[n] || 0), 0);
    const rows = unknownNames
      .map((n) => unknownRowHTML(n, unknownBiomes[n] || 0, max))
      .join("");
    wrap.appendChild(
      groupHTML("unknown", "Unknown", "var(--text-faint)", total, rows),
    );
  }

  updateStats();
}

function renderLogs() {
  const list = document.getElementById("logList");
  const badge = document.getElementById("onlineBadge");
  if (!list) return;
  list.innerHTML = "";

  if (accounts.length === 0) {
    list.innerHTML =
      '<div class="log-empty">No accounts registered. Add one under the Accounts tab.</div>';
    if (badge) badge.textContent = "0 online";
    return;
  }
  if (badge) badge.textContent = `${isRunning ? accounts.length : 0} online`;

  accounts.forEach((acc) => {
    const meta = biomeMeta(acc.currentBiome);
    const isRare = meta && meta.tier === "rare";
    const accent = meta ? meta.shadow : "var(--stroke)";
    const biomePill = meta
      ? `<span class="biome-pill ${isRare ? "rare" : ""}"><span class="d" style="--g:${meta.shadow}"></span>${meta.name}</span>`
      : `<span class="biome-pill">Awaiting biome…</span>`;
    const row = document.createElement("div");
    row.className = `log-row ${isRare ? "is-rare" : ""}`;
    row.style.setProperty("--row-accent", accent);
    row.innerHTML = `
      <img src="${acc.avatar || DEFAULT_AVATAR}" class="log-avatar" alt="">
      <div class="log-meta">
        <span class="log-name">${esc(acc.name)}</span>
        ${biomePill}
      </div>
      <div class="log-status">
        ${isRunning && isRare ? '<span class="rare-flash">RARE FIND</span>' : ""}
        <span class="lp ${isRunning ? "live" : ""}"><span class="sd"></span>${isRunning ? "Online" : "Idle"}</span>
      </div>`;
    list.appendChild(row);
  });
}

function tierTotals() {
  const out = { normal: 0, event: 0, rare: 0 };
  BIOMES.forEach((b) => {
    out[b.tier] += biomeCounts[b.key] || 0;
  });
  return out;
}
function statHeadCard(ico, icoClass, value, cap, valId, small) {
  return `
    <div class="glass card stat">
      <div class="stat-ico ${icoClass}"><i class="${ico}"></i></div>
      <div class="stat-body">
        <span class="stat-num ${small ? "sm" : ""}" ${valId ? `id="${valId}"` : ""}>${value}</span>
        <span class="stat-cap">${cap}</span>
      </div>
    </div>`;
}
function renderStats() {
  const head = document.getElementById("statsHead");
  if (!head) return;
  const total = totalBiomes();
  const t = tierTotals();

  head.innerHTML =
    statHeadCard(
      "fa-solid fa-user-check",
      "ico-accent",
      accounts.length.toString(),
      "Accounts",
    ) +
    statHeadCard(
      "fa-brands fa-discord",
      "ico-blurple",
      webhooks.filter((w) => w.active).length.toString(),
      "Active Webhooks",
    ) +
    statHeadCard(
      "fa-solid fa-stopwatch",
      "ico-accent",
      formatTime(uptimeSeconds),
      "Tracking Time",
      "statTime",
    );

  document.getElementById("rarityTotal").textContent =
    `${total.toLocaleString("en-US")} logged`;

  const bar = document.getElementById("rarityBar");
  bar.innerHTML = `
    <div class="rarity-seg normal" style="flex-grow:${t.normal}"></div>
    <div class="rarity-seg event"  style="flex-grow:${t.event}"></div>
    <div class="rarity-seg rare"   style="flex-grow:${t.rare}"></div>`;

  const safe = total || 1;
  const pct = (n) => ((n / safe) * 100).toFixed(n && n / safe < 0.01 ? 2 : 1);
  document.getElementById("rarityLegend").innerHTML = [
    { c: "linear-gradient(90deg,#5b6075,#7e8499)", n: "Normal", v: t.normal },
    { c: "linear-gradient(90deg,#d9931a,#f0b429)", n: "Event", v: t.event },
    { c: "linear-gradient(90deg,#ff6bd6,#6be7ff)", n: "Rare", v: t.rare },
  ]
    .map(
      (x) => `
      <div class="rl-item">
        <span class="rl-swatch" style="background:${x.c}"></span>
        <span class="rl-text">
          <span class="rl-name">${x.n}</span>
          <span class="rl-val">${x.v.toLocaleString("en-US")} &middot; ${pct(x.v)}%</span>
        </span>
      </div>`,
    )
    .join("");

  document.getElementById("rareSpotlight").innerHTML = RARE_KEYS.map((k) => {
    const b = biomeMeta(k);
    const count = biomeCounts[k] || 0;
    return `
      <div class="rare-card ${count > 0 ? "hit" : ""}" style="--biome-grad:${b.grad}; --biome-shadow:${b.shadow}">
        <div class="rc-top"><span class="rc-swatch"></span><span class="rc-name">${b.name}</span></div>
        <div class="rc-count ${count === 0 ? "zero" : ""}">${count.toLocaleString("en-US")}</div>
        <div class="rc-cap">${count === 0 ? "not yet found" : count === 1 ? "time found" : "times found"}</div>
      </div>`;
  }).join("");
}

async function addAccount() {
  if (isRunning) return;
  const nameInput = document.getElementById("accName");
  const linkInput = document.getElementById("accLink");
  const username = nameInput.value.trim();
  if (username === "") return;
  const link = linkInput.value.trim();

  if (!link) {
    showErrors(["Please provide a private server link (required)."]);
    return;
  }
  if (!isRobloxLink(link)) {
    showErrors(["The private server link must be a valid roblox.com URL."]);
    return;
  }

  if (hasEel) {
    applyState(await callPy("add_account", username, link));
  } else {
    accounts.push({
      id: Date.now(),
      name: username,
      link,
      avatar: DEFAULT_AVATAR,
      currentBiome: null,
    });
    renderAll();
  }
  nameInput.value = "";
  linkInput.value = "";
}

async function deleteAccount(id) {
  if (isRunning) return;
  if (hasEel) {
    applyState(await callPy("delete_account", id));
  } else {
    accounts = accounts.filter((a) => a.id !== id);
    webhooks.forEach(
      (w) =>
        (w.routedAccounts = (w.routedAccounts || []).filter(
          (aid) => aid !== id,
        )),
    );
    renderAll();
  }
}

function editAccount(id) {
  if (isRunning) return;
  const acc = accounts.find((a) => a.id === id);
  if (!acc) return;
  openModal(
    "Edit Account",
    `
    <div><div class="modal-label">Username</div>
      <input class="field" id="editAccName" value="${esc(acc.name)}" placeholder="Username"></div>
    <div><div class="modal-label">Private Server URL</div>
      <input class="field" id="editAccLink" value="${esc(acc.link || "")}" placeholder="roblox.com Private Server URL"></div>`,
    async () => {
      const newName = document.getElementById("editAccName").value.trim();
      const newLink = document.getElementById("editAccLink").value.trim();
      if (!newName) return false;
      if (hasEel) {
        applyState(await callPy("update_account", id, newName, newLink));
      } else {
        acc.name = newName;
        acc.link = newLink;
        renderAll();
      }
      return true;
    },
  );
}

function renderAccounts() {
  const list = document.getElementById("accountList");
  const empty = document.getElementById("accEmpty");
  if (!list) return;
  list.innerHTML = "";
  empty.classList.toggle("show", accounts.length === 0);

  accounts.forEach((acc, i) => {
    const card = document.createElement("div");
    card.className = "data-card";
    card.style.animationDelay = `${i * 0.05}s`;
    card.innerHTML = `
      <div class="dc-head">
        <div class="dc-title">
          <img src="${acc.avatar || DEFAULT_AVATAR}" class="acc-avatar" alt="">
          <span>${esc(acc.name)}</span>
        </div>
        <div class="dc-actions">
          <button class="edit-btn" onclick="editAccount(${acc.id})"><i class="fa-solid fa-pen"></i></button>
          <button class="del-btn" onclick="deleteAccount(${acc.id})"><i class="fa-solid fa-trash"></i></button>
        </div>
      </div>
      <p class="dc-sub ${acc.link ? "" : "muted"}">${acc.link ? esc(acc.link) : "No private server link"}</p>`;
    list.appendChild(card);
  });
}

async function addWebhook() {
  if (isRunning) return;
  const nameInput = document.getElementById("whName");
  const urlInput = document.getElementById("whUrl");
  if (nameInput.value.trim() === "" || urlInput.value.trim() === "") return;
  const name = nameInput.value.trim();
  const url = urlInput.value.trim();

  if (hasEel) {
    applyState(await callPy("add_webhook", name, url));
  } else {
    webhooks.push({
      id: Date.now(),
      name,
      url,
      active: true,
      routedAccounts: [],
    });
    renderAll();
  }
  nameInput.value = "";
  urlInput.value = "";
}

async function deleteWebhook(id) {
  if (isRunning) return;
  if (hasEel) {
    applyState(await callPy("delete_webhook", id));
  } else {
    webhooks = webhooks.filter((w) => w.id !== id);
    renderAll();
  }
}

function editWebhook(id) {
  if (isRunning) return;
  const wh = webhooks.find((w) => w.id === id);
  if (!wh) return;
  openModal(
    "Edit Webhook",
    `
    <div><div class="modal-label">Label</div>
      <input class="field" id="editWhName" value="${esc(wh.name)}" placeholder="Label"></div>
    <div><div class="modal-label">Webhook URL</div>
      <input class="field" id="editWhUrl" value="${esc(wh.url)}" placeholder="Webhook URL"></div>`,
    async () => {
      const newName = document.getElementById("editWhName").value.trim();
      const newUrl = document.getElementById("editWhUrl").value.trim();
      if (!newName || !newUrl) return false;
      if (hasEel) {
        applyState(await callPy("update_webhook", id, newName, newUrl));
      } else {
        wh.name = newName;
        wh.url = newUrl;
        renderAll();
      }
      return true;
    },
  );
}

async function toggleWebhookState(id) {
  if (isRunning) return;
  const wh = webhooks.find((w) => w.id === id);
  if (!wh) return;
  const next = !wh.active;
  if (hasEel) {
    applyState(await callPy("set_webhook_active", id, next));
  } else {
    wh.active = next;
    renderAll();
  }
}

async function toggleRouting(webhookId, accountId, checkbox) {
  if (isRunning) {
    checkbox.checked = !checkbox.checked;
    return;
  }
  const enabled = checkbox.checked;
  if (hasEel) {
    applyState(await callPy("set_routing", webhookId, accountId, enabled));
  } else {
    const wh = webhooks.find((w) => w.id === webhookId);
    if (!wh) return;
    wh.routedAccounts = wh.routedAccounts || [];
    if (enabled) {
      if (!wh.routedAccounts.includes(accountId))
        wh.routedAccounts.push(accountId);
    } else
      wh.routedAccounts = wh.routedAccounts.filter((id) => id !== accountId);
    renderStats();
  }
}

function renderWebhooks() {
  const list = document.getElementById("webhookList");
  const empty = document.getElementById("whEmpty");
  if (!list) return;
  list.innerHTML = "";
  empty.classList.toggle("show", webhooks.length === 0);

  webhooks.forEach((wh, i) => {
    let opts = accounts
      .map(
        (acc) => `
        <label class="route-opt">
          <input type="checkbox" onchange="toggleRouting(${wh.id}, ${acc.id}, this)" ${(wh.routedAccounts || []).includes(acc.id) ? "checked" : ""}>
          <img src="${acc.avatar || DEFAULT_AVATAR}" class="route-mini" alt="">
          ${esc(acc.name)}
        </label>`,
      )
      .join("");
    if (accounts.length === 0)
      opts = '<span class="no-acc">No accounts registered yet.</span>';

    const card = document.createElement("div");
    card.className = "data-card";
    card.style.animationDelay = `${i * 0.05}s`;
    card.innerHTML = `
      <div class="dc-head">
        <div class="dc-title"><i class="fa-brands fa-discord"></i><span>${esc(wh.name)}</span></div>
        <div class="dc-actions">
          <label class="switch"><input type="checkbox" onchange="toggleWebhookState(${wh.id})" ${wh.active ? "checked" : ""}><span class="slider"></span></label>
          <button class="edit-btn" onclick="editWebhook(${wh.id})"><i class="fa-solid fa-pen"></i></button>
          <button class="del-btn" onclick="deleteWebhook(${wh.id})"><i class="fa-solid fa-trash"></i></button>
        </div>
      </div>
      <div class="route-label">Logged accounts</div>
      <div class="routing-list">${opts}</div>
      <p class="dc-sub" style="margin-top:10px">${esc(maskWebhook(wh.url))}</p>`;
    list.appendChild(card);
  });
}

let _modalSaveCallback = null;

function openModal(title, bodyHtml, onSave) {
  document.getElementById("modalTitle").textContent = title;
  document.getElementById("modalBody").innerHTML = bodyHtml;
  _modalSaveCallback = onSave;
  document.getElementById("editModal").classList.add("open");
  const first = document.querySelector("#modalBody .field");
  if (first) setTimeout(() => first.focus(), 50);
}

function closeEditModal(e) {
  if (e && e.target !== document.getElementById("editModal")) return;
  document.getElementById("editModal").classList.remove("open");
  _modalSaveCallback = null;
}

let _updateUrl = null;

async function checkForUpdate() {
  if (!hasEel) return;
  const info = await callPy("check_update");
  if (info && info.available && info.url) {
    showUpdateModal(info);
  }
}

function showUpdateModal(info) {
  _updateUrl = info.url;
  const cur = document.getElementById("updCurrent");
  const lat = document.getElementById("updLatest");
  if (cur)
    cur.textContent = "v" + String(info.current || "?").replace(/^v/i, "");
  if (lat)
    lat.textContent = "v" + String(info.latest || "?").replace(/^v/i, "");
  document.getElementById("updateModal").classList.add("open");
}

function closeUpdateModal(e) {
  if (e && e.target !== document.getElementById("updateModal")) return;
  document.getElementById("updateModal").classList.remove("open");
}

async function openUpdatePage() {
  if (!_updateUrl) return;
  if (hasEel) {
    await callPy("open_url", _updateUrl);
  } else {
    window.open(_updateUrl, "_blank");
  }
  closeUpdateModal();
}

function clampInterval(v) {
  if (!Number.isFinite(v)) return 300;
  return Math.max(30, Math.min(900, Math.round(v / 30) * 30));
}

function formatInterval(sec) {
  if (sec >= 60) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s.toString().padStart(2, "0")}s`;
  }
  return `${sec}s`;
}

function renderAntiAfk() {
  const toggle = document.getElementById("antiAfkToggle");
  if (!toggle) return;

  const enabled = !!appSettings.antiAfkEnabled;
  const action = appSettings.antiAfkAction === "zoom" ? "zoom" : "space";
  const interval = clampInterval(parseInt(appSettings.antiAfkInterval, 10));

  toggle.checked = enabled;
  toggle.disabled = isRunning;

  document.querySelectorAll("#antiAfkAction .seg-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.action === action);
  });

  const range = document.getElementById("antiAfkInterval");
  const value = document.getElementById("antiAfkIntervalValue");
  if (range) {
    range.value = interval;
    const pct = ((interval - 30) / (900 - 30)) * 100;
    range.style.backgroundSize = `${pct}% 100%`;
  }
  if (value) value.textContent = formatInterval(interval);

  const badge = document.getElementById("antiAfkStateBadge");
  if (badge) {
    if (isRunning && enabled) badge.textContent = "Running";
    else if (enabled) badge.textContent = "Ready";
    else badge.textContent = "Inactive";
  }
}

async function onAntiAfkToggle(el) {
  if (isRunning) {
    el.checked = !el.checked;
    return;
  }
  const val = el.checked;
  appSettings.antiAfkEnabled = val;
  if (hasEel) {
    applyState(await callPy("set_setting", "antiAfkEnabled", val));
  } else {
    renderAntiAfk();
  }
}

function setAntiAfkAction(action) {
  appSettings.antiAfkAction = action;
  renderAntiAfk();
  if (hasEel) callPy("set_setting", "antiAfkAction", action);
}

function onAntiAfkIntervalInput(el) {
  const v = clampInterval(parseInt(el.value, 10));
  appSettings.antiAfkInterval = v;
  const value = document.getElementById("antiAfkIntervalValue");
  if (value) value.textContent = formatInterval(v);
  const pct = ((v - 30) / (900 - 30)) * 100;
  el.style.backgroundSize = `${pct}% 100%`;
}

function onAntiAfkIntervalChange(el) {
  const v = clampInterval(parseInt(el.value, 10));
  appSettings.antiAfkInterval = v;
  if (hasEel) callPy("set_setting", "antiAfkInterval", v);
}

function renderSwatches() {
  const wrap = document.getElementById("swatches");
  if (!wrap) return;
  wrap.innerHTML = "";
  ACCENTS.forEach((a, i) => {
    const b = document.createElement("button");
    b.className = "swatch-btn" + (i === 0 ? " sel" : "");
    b.style.background = `linear-gradient(135deg, ${a.c}, ${a.c2})`;
    b.onclick = () => setAccent(a, b);
    wrap.appendChild(b);
  });
}
function setAccent(a, btn) {
  const root = document.documentElement.style;
  root.setProperty("--accent", a.c);
  root.setProperty("--accent-2", a.c2);
  root.setProperty("--accent-glow", hexToGlow(a.c));
  const rgb1 = hexToRgb(a.c),
    rgb2 = hexToRgb(a.c2);
  root.setProperty("--orb-1-r", rgb1.r);
  root.setProperty("--orb-1-g", rgb1.g);
  root.setProperty("--orb-1-b", rgb1.b);
  root.setProperty("--orb-2-r", rgb2.r);
  root.setProperty("--orb-2-g", rgb2.g);
  root.setProperty("--orb-2-b", rgb2.b);
  document
    .querySelectorAll(".swatch-btn")
    .forEach((s) => s.classList.remove("sel"));
  btn.classList.add("sel");
}
function hexToGlow(hex) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, 0.45)`;
}
function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function isRobloxLink(link) {
  try {
    let u = link.trim();
    if (!u.includes("://")) u = "https://" + u;
    const host = new URL(u).hostname.toLowerCase();
    return host === "roblox.com" || host.endsWith(".roblox.com");
  } catch (e) {
    return false;
  }
}

function maskWebhook(url) {
  if (!url || !url.trim()) return "No webhook URL";
  const m = url.match(/discord(?:app)?\.com\/api\/(?:v\d+\/)?webhooks\/(\d+)/i);
  if (m) return `discord.com/api/webhooks/${m[1]}/...`;
  try {
    let u = url.includes("://") ? url : "https://" + url;
    return new URL(u).hostname + "/...";
  } catch (e) {
    return "•••";
  }
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function blockDevtools() {
  document.addEventListener(
    "keydown",
    (e) => {
      const k = (e.key || "").toLowerCase();
      const blocked =
        e.key === "F12" ||
        (e.ctrlKey && e.shiftKey && (k === "i" || k === "j" || k === "c")) ||
        (e.ctrlKey && k === "u");
      if (blocked) {
        e.preventDefault();
        e.stopPropagation();
        return false;
      }
    },
    true,
  );
  document.addEventListener("contextmenu", (e) => e.preventDefault());
}

/* =====================================================================
   INIT
   ===================================================================== */
document.addEventListener("DOMContentLoaded", async () => {
  blockDevtools();

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab, btn));
  });

  document
    .getElementById("modalSaveBtn")
    .addEventListener("click", async () => {
      if (_modalSaveCallback) {
        const ok = await _modalSaveCallback();
        if (ok !== false)
          document.getElementById("editModal").classList.remove("open");
      }
    });
  document
    .getElementById("updateGoBtn")
    .addEventListener("click", () => openUpdatePage());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.getElementById("editModal").classList.remove("open");
      document.getElementById("updateModal").classList.remove("open");
    }
  });

  renderSwatches();

  if (hasEel) {
    applyState(await callPy("get_state"));
    checkForUpdate();
  } else {
    renderAll();
    setRunning(false);
  }
});
document.addEventListener(
  "keydown",
  function (e) {
    if (e.ctrlKey && (e.key === "s" || e.key === "S")) {
      e.preventDefault();
      e.stopPropagation();
      return false;
    }
    if (
      e.ctrlKey &&
      (e.key === "p" || e.key === "P" || e.key === "u" || e.key === "U")
    ) {
      e.preventDefault();
      e.stopPropagation();
      return false;
    }
  },
  true,
);
document.addEventListener("contextmenu", function (e) {
  e.preventDefault();
});
