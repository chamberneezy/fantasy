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

let state = { started: false, categories: [], team_count: 16, budget: 200, draft_slot: 1 };
let error = "";
let line = "";
let hammer = null;
let lastPlayer = "";
let searchCaret = null;
let seatPick = 1;
const MARK = "img/mark.png";

function brand() {
  return `<a class="brand" href="index.html" data-home-reset aria-label="NBA Fantasy home. Clears helper, mock, and lab."><span class="mark-wrap"><img class="mark" src="${MARK}" width="64" height="64" alt=""></span><span class="wordmark">NBA Fantasy</span></a>`;
}

async function api(path, body) {
  try {
    return NBA.helperApi(path, body || {});
  } catch (exc) {
    throw new Error(exc.message || "Could not read that.");
  }
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

function typedQuery(text) {
  return String(text || "").replace(/(?:^|\s)\$?\d+\s*$/, "").trim();
}

function typedAmount(text) {
  const match = String(text || "").match(/(?:^|\s)\$?(\d+)\s*$/);
  return match ? Number(match[1]) : null;
}

function priced() {
  return state.board || [];
}

function suggestions() {
  const query = typedQuery(line);
  const pool = priced();
  if (query) return pool.filter((player) => matchesPlayer(player, query)).slice(0, 8);
  if (state.next && state.next.length) return state.next;
  return pool.slice(0, 8);
}

function roomLine() {
  const room = state.room;
  if (!room || !room.listening) return "";
  return `<p class="roomline">${room.note || ""}</p>`;
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
            <a href="draft.html">Practice mock</a>
            <a href="index.html">Home</a>
            ${themeToggleHtml()}
          </nav>
        </div>
      </header>
      <a class="mark-wrap mark-hero" href="index.html" data-home-reset aria-label="NBA Fantasy home. Clears helper, mock, and lab."><img class="mark" src="${MARK}" width="150" height="150" alt=""></a>
      <h1>Where do you sit?</h1>
      <p class="lede">Your nomination seat, 1–16. Then Open. This page does not bid.</p>
      <div class="slots" id="slot-choices">${seatButtons(state.team_count || 16)}</div>
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
      <p class="markets">Yahoo list ${money(coach.listed)} · fair ${money(coach.fair_stay)}–${money(coach.fair_stretch)}${coach.room_factor && Math.abs(coach.room_factor - 1) >= 0.03 ? ` · this room ${money(coach.room_stay || coach.stay)} (${Number(coach.room_factor).toFixed(2)}×)` : ""}${coach.your_max != null && coach.room_stay != null && coach.your_max < coach.room_stay ? ` · you ${money(coach.your_max)}` : ""} · tape ${money(coach.typical_low)}–${money(coach.typical_high)}</p>
      <p class="why">${coach.why}</p>
      <div class="hammer">
        <button type="button" data-nudge="-1">−1</button>
        <button type="button" data-nudge="1">+1</button>
        <button type="button" data-nudge="5">+5</button>
      </div>
      <div class="close">
        <button class="sold" id="sold" type="button">Gone</button>
        <button class="me" id="mine" type="button">Me</button>
      </div>
    </section>` : "";
  const seats = (state.rosters && state.rosters[0] && state.rosters[0].slots) || [];
  return `
    <section class="sheet">
      <header class="banner">
        <div class="banner-inner">
          ${brand()}
          <nav class="links">${themeToggleHtml()}</nav>
          <span class="budget">${money(state.budget_left)} · ${state.spots_left} left · sit ${state.nomination_slot || seatPick}</span>
        </div>
      </header>
      ${roomLine()}
      <p class="lede">Gone = room got him. Tap the name only if you want him. Optional: jokic 160 + Enter.</p>
      <form class="feed" id="feed-form">
        <input id="feed" autocomplete="off" placeholder="name or name 160" value="${escapeAttr(line)}">
      </form>
      ${namesHtml()}
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

function namesHtml() {
  const names = suggestions();
  if (!names.length) return `<p class="lede">${typedQuery(line) ? "No name matches that." : "Board is empty."}</p>`;
  return `
    <section class="nexts">
      <p class="next-head">${typedQuery(line) ? "Matches" : "Stay names"}</p>
      <ul>
        ${names.map((player) => `
          <li class="${player.short ? "short" : ""}">
            <button type="button" data-pick="${escapeAttr(player.player_name)}">
              <span class="next-who">${player.player_name}</span>
              <span class="next-meta">${player.positions || ""} · list ${money(player.listed)}${player.your_max != null ? ` · leftover ${money(player.your_max)}` : ""}${player.second ? " · second star" : ""}${player.short ? " · leftover binds" : ""}</span>
              <strong>${player.short ? "You" : "Stay"} ${money(player.stay)}</strong>
            </button>
            <button type="button" class="gone" data-gone="${escapeAttr(player.player_name)}">Gone</button>
          </li>`).join("")}
      </ul>
    </section>`;
}

function seatButtons(count) {
  const teams = Math.max(2, Math.min(16, Number(count) || 16));
  const pick = Math.min(Math.max(1, Number(seatPick) || 1), teams);
  return Array.from({ length: teams }, (_, index) => {
    const number = index + 1;
    return `<button type="button" class="slot-choice ${number === pick ? "selected" : ""}" data-seat="${number}">${number}</button>`;
  }).join("");
}

function drawSlotChoices(count) {
  const holder = document.querySelector("#slot-choices");
  if (!holder) return;
  const teams = Math.max(2, Math.min(16, Number(count) || 16));
  seatPick = Math.min(Math.max(1, Number(seatPick) || 1), teams);
  holder.innerHTML = seatButtons(teams);
  bindSeats();
}

function bindSeats() {
  document.querySelectorAll("[data-seat]").forEach((button) => {
    button.addEventListener("click", () => {
      seatPick = Number(button.dataset.seat);
      document.querySelectorAll("[data-seat]").forEach((item) => item.classList.toggle("selected", Number(item.dataset.seat) === seatPick));
    });
  });
}

function bind() {
  const open = document.querySelector("#open");
  if (open) {
    const teamCount = document.querySelector("#team-count");
    if (teamCount) teamCount.addEventListener("input", () => drawSlotChoices(Number(teamCount.value)));
    bindSeats();
    open.addEventListener("click", async () => {
      const budget = Number(document.querySelector("#budget").value);
      const teams = Number(document.querySelector("#team-count").value);
      const draftSlot = Math.min(Math.max(1, Number(seatPick) || 1), Math.max(2, Math.min(16, teams || 16)));
      await run(() => api("/helper/api/start", { budget, team_count: teams, draft_slot: draftSlot, punts: [] }));
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
      if (/\b(me|mine|got|you|keep|locked|dynasty)\b/i.test(text)) {
        line = "";
        await run(() => api("/helper/api/feed", { line: text }));
        return;
      }
      const dollar = typedAmount(text);
      const name = typedQuery(text);
      const first = available().find((player) => matchesPlayer(player, name)) || suggestions()[0];
      line = "";
      await markGone(first ? first.player_name : name, dollar);
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
  app.querySelectorAll("[data-gone]").forEach((button) => {
    button.addEventListener("click", () => markGone(button.dataset.gone));
  });
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
  const undo = document.querySelector("#undo");
  if (undo) undo.addEventListener("click", () => run(() => api("/helper/api/undo", {})));
  const reset = document.querySelector("#reset");
  if (reset) reset.addEventListener("click", () => run(() => api("/helper/api/reset", {})));
}

async function markGone(playerName, amount) {
  line = "";
  searchCaret = null;
  const body = { player_name: playerName };
  if (amount != null && amount !== "") body.amount = amount;
  await run(() => api("/helper/api/gone", body));
}

async function closeNight(action) {
  line = "";
  searchCaret = null;
  await run(() => api("/helper/api/close", { action, amount: hammer }));
}

async function run(action) {
  try {
    error = "";
    state = await action();
    if (state.nomination_slot) seatPick = Number(state.nomination_slot);
    else if (state.draft_slot) seatPick = Number(state.draft_slot);
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

NBA.load()
  .then(() => run(() => api("/helper/api/state")))
  .catch((exc) => {
    error = exc.message || "Could not load the board.";
    render();
  });

