const app = document.querySelector("#app");
const ALIASES = {
  ad: "anthony davis",
  ant: "anthony edwards",
  bambi: "victor wembanyama",
  bron: "lebron james",
  cade: "cade cunningham",
  curry: "stephen curry",
  doncic: "luka doncic",
  durant: "kevin durant",
  embiid: "joel embiid",
  flagg: "cooper flagg",
  giannis: "giannis antetokounmpo",
  haliburton: "tyrese haliburton",
  jokic: "nikola jokic",
  joker: "nikola jokic",
  kat: "karl-anthony towns",
  kawhi: "kawhi leonard",
  kd: "kevin durant",
  lebron: "lebron james",
  luka: "luka doncic",
  maxey: "tyrese maxey",
  sga: "shai gilgeous-alexander",
  shai: "shai gilgeous-alexander",
  steph: "stephen curry",
  tatum: "jayson tatum",
  wemby: "victor wembanyama",
  wembanyama: "victor wembanyama",
};

let state = { started: false, categories: [], team_count: 16, budget: 200 };
let error = "";
let line = "";
let hammer = null;
let lastPlayer = "";
let searchCaret = null;
const MARK = "/static/mark.png";

function brand() {
  return `<a class="brand" href="/" data-home-reset aria-label="NBA Fantasy home. Clears helper, mock, and lab."><span class="mark-wrap"><img class="mark" src="${MARK}" width="64" height="64" alt=""></span><span class="wordmark">NBA Fantasy</span></a>`;
}

async function api(path, body) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Could not read that.");
  return payload;
}

function money(value) {
  return value == null ? "—" : `$${value}`;
}

function fold(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function lastName(name) {
  const parts = fold(name).split(/\s+/).filter(Boolean);
  return parts[parts.length - 1] || "";
}

function matchesPlayer(player, query) {
  const needle = fold(query).trim();
  if (!needle) return false;
  const full = fold(player.player_name);
  if (full.includes(needle) || lastName(player.player_name).startsWith(needle)) return true;
  const mapped = ALIASES[needle];
  if (mapped && full.includes(mapped)) return true;
  return Object.entries(ALIASES).some(([key, name]) => key.startsWith(needle) && full.includes(name));
}

function available() {
  return state.available || [];
}

function suggestions() {
  const query = line.trim();
  const pool = available();
  if (query) return pool.filter((player) => matchesPlayer(player, query)).slice(0, 8);
  return pool.slice(0, 8);
}

function roomLine() {
  const room = state.room;
  if (!room) return "";
  const star = room.factors && room.factors.star != null ? Number(room.factors.star).toFixed(2) : "1.00";
  const sales = room.counts && room.counts.star != null ? room.counts.star : 0;
  return `<p class="roomline">${money(room.cash)} league · ${money(room.per_seat)}/seat · stars ${star}× (${sales} ${sales === 1 ? "sale" : "sales"})${room.note ? ` · ${room.note}` : ""}</p>`;
}

function chipName(name) {
  const parts = String(name || "").trim().split(/\s+/);
  return parts[parts.length - 1] || name;
}

function syncHammer(coach) {
  if (!coach) {
    hammer = null;
    lastPlayer = "";
    return;
  }
  if (coach.player_name !== lastPlayer) {
    lastPlayer = coach.player_name;
    hammer = coach.bid == null ? coach.stay : coach.bid;
  }
}

function liveCall(coach) {
  if (!coach) return "";
  if (hammer == null || coach.bid == null && hammer === coach.stay) return coach.call;
  if (hammer <= coach.stay) return "stay";
  if (hammer <= coach.stretch) return "stretch";
  return "pass";
}

function render() {
  syncHammer(state.coach);
  app.innerHTML = state.started ? deskHtml() : gateHtml();
  bind();
}

function gateHtml() {
  return `
    <section class="sheet">
      <header class="banner">
        <div class="banner-inner">
          ${brand()}
          <nav class="links">
            <a href="/draft">Practice mock</a>
            <a href="/lab">Lab</a>
            ${themeToggleHtml()}
          </nav>
        </div>
      </header>
      <a class="mark-wrap mark-hero" href="/" data-home-reset aria-label="NBA Fantasy home. Clears helper, mock, and lab."><img class="mark" src="${MARK}" width="150" height="150" alt=""></a>
      <h1>Tap the name. Then Sold or Me.</h1>
      <p class="lede">This page does not open Yahoo and does not bid. Budget is your draft dollars ($160–$240) — the cap, not a payment. Default $200. No dynasty this year, so use Sold and Me. Keep and Locked stay for a dynasty night only.</p>
      <div class="fields">
        <label>Budget <input id="budget" type="number" min="160" max="240" value="${state.budget || 200}"></label>
        <label>Teams <input id="team-count" type="number" min="2" max="16" value="${state.team_count || 16}"></label>
      </div>
      <button class="go" id="open" type="button">Open the helper</button>
      <p class="error">${error}</p>
    </section>`;
}

function deskHtml() {
  const coach = state.coach;
  const call = liveCall(coach);
  const names = suggestions();
  const card = coach ? `
    <section class="card call-${call}">
      <header>
        <p class="who">${coach.player_name}</p>
        <p class="now">${money(hammer)}</p>
      </header>
      <ol class="meters">
        <li class="${call === "stay" || call === "ready" ? "on" : ""}"><button type="button" data-set="${coach.stay}"><span>Stay</span><strong>${money(coach.stay)}</strong></button></li>
        <li class="${call === "stretch" ? "on" : ""}"><button type="button" data-set="${coach.stretch}"><span>Stretch</span><strong>${money(coach.stretch)}</strong></button></li>
        <li class="${call === "pass" ? "on" : ""}"><span>Pass</span><strong>over ${money(coach.stretch)}</strong></li>
      </ol>
      <p class="markets">Yahoo list ${money(coach.listed)} · fair ${money(coach.fair_stay)}–${money(coach.fair_stretch)} · rooms ${money(coach.typical_low)}–${money(coach.typical_high)}${coach.room_factor && Math.abs(coach.room_factor - 1) >= 0.03 ? ` · this room ${coach.room_factor.toFixed(2)}×` : ""}</p>
      <p class="why">${coach.why}</p>
      <div class="hammer">
        <button type="button" data-nudge="-1">−1</button>
        <button type="button" data-nudge="1">+1</button>
        <button type="button" data-nudge="5">+5</button>
      </div>
      <div class="close">
        <button class="sold" id="sold" type="button">Sold</button>
        <button class="me" id="mine" type="button">Me</button>
        <button class="keep" id="keep" type="button">Keep</button>
        <button class="locked" id="locked" type="button">Locked</button>
      </div>
    </section>` : `<p class="lede">Type a few letters or tap a name. Sold is the room. Me is you.</p>`;
  const seats = (state.rosters && state.rosters[0] && state.rosters[0].slots) || [];
  return `
    <section class="sheet">
      <header class="banner">
        <div class="banner-inner">
          ${brand()}
          <nav class="links">${themeToggleHtml()}</nav>
          <span class="budget">${money(state.budget_left)} · ${state.spots_left} seats</span>
        </div>
      </header>
      ${roomLine()}
      <form class="feed" id="feed-form">
        <input id="feed" autocomplete="off" placeholder="jok" value="${escapeAttr(line)}">
      </form>
      <ul class="board">
        ${names.map((player) => `
          <li>
            <button type="button" data-pick="${escapeAttr(player.player_name)}" title="${escapeAttr(player.player_name)}">
              <span>${chipName(player.player_name)}</span>
              <strong>${money(player.auction_value)}</strong>
            </button>
          </li>`).join("")}
      </ul>
      ${card}
      <p class="error">${error}</p>
      <ul class="wallet">
        ${seats.map((slot) => `<li><span>${slot.label}</span><span>${slot.player ? `${slot.player.player_name} ${money(slot.player.price)}` : "—"}</span></li>`).join("")}
      </ul>
      <ul class="log">
        ${(state.log || []).slice(-8).map((item) => `<li><span>${item.team} ${item.player_name}</span><span>${money(item.price)}</span></li>`).join("")}
      </ul>
      <div class="actions">
        <button class="text" id="undo" type="button">Undo</button>
        <button class="text" id="reset" type="button">Clear night</button>
      </div>
    </section>`;
}

function bind() {
  const open = document.querySelector("#open");
  if (open) {
    open.addEventListener("click", async () => {
      const budget = Number(document.querySelector("#budget").value);
      const teamCount = Number(document.querySelector("#team-count").value);
      await run(() => api("/helper/api/start", { budget, team_count: teamCount, punts: [] }));
    });
  }
  const form = document.querySelector("#feed-form");
  if (form) {
    const input = document.querySelector("#feed");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) {
        error = "Type a few letters.";
        render();
        return;
      }
      if (/\b(sold|gone|taken|me|mine|got|you|keep|locked|dynasty)\b/i.test(text)) {
        line = "";
        await run(() => api("/helper/api/feed", { line: text }));
        return;
      }
      const first = suggestions()[0];
      line = "";
      await run(() => api("/helper/api/pick", { player_name: first ? first.player_name : text }));
    });
    input.addEventListener("input", () => {
      line = input.value;
      searchCaret = input.selectionStart;
      render();
    });
    if (searchCaret != null) {
      input.focus();
      input.setSelectionRange(searchCaret, searchCaret);
      searchCaret = null;
    }
  }
  app.querySelectorAll("[data-pick]").forEach((button) => {
    button.addEventListener("click", async () => {
      line = "";
      await run(() => api("/helper/api/pick", { player_name: button.dataset.pick }));
    });
  });
  app.querySelectorAll("[data-set]").forEach((button) => {
    button.addEventListener("click", () => {
      hammer = Number(button.dataset.set);
      render();
    });
  });
  app.querySelectorAll("[data-nudge]").forEach((button) => {
    button.addEventListener("click", () => {
      hammer = Math.max(1, (hammer || 1) + Number(button.dataset.nudge));
      render();
    });
  });
  const sold = document.querySelector("#sold");
  if (sold) sold.addEventListener("click", () => closeNight("sold"));
  const mine = document.querySelector("#mine");
  if (mine) mine.addEventListener("click", () => closeNight("me"));
  const keep = document.querySelector("#keep");
  if (keep) keep.addEventListener("click", () => closeNight("keep"));
  const locked = document.querySelector("#locked");
  if (locked) locked.addEventListener("click", () => closeNight("locked"));
  const undo = document.querySelector("#undo");
  if (undo) undo.addEventListener("click", () => run(() => api("/helper/api/undo", {})));
  const reset = document.querySelector("#reset");
  if (reset) reset.addEventListener("click", () => run(() => api("/helper/api/reset", {})));
}

async function closeNight(action) {
  line = "";
  await run(() => api("/helper/api/close", { action, amount: hammer }));
}

async function run(action) {
  try {
    error = "";
    state = await action();
    if (!state.coach) {
      hammer = null;
      lastPlayer = "";
    }
    render();
  } catch (exc) {
    error = exc.message;
    render();
  }
}

function escapeAttr(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
}

run(() => api("/helper/api/state"));
