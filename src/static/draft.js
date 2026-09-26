const app = document.querySelector("#app");
let state = { started: false, categories: [] };
let query = "";
let filter = "All";
let selectedPlayer = "";
let viewing = 0;
let error = "";
let clock = null;

async function api(path, body) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "The draft could not do that.");
  return payload;
}

function eligible(player, label) {
  if (label === "UTIL" || label === "BN") return true;
  return String(player.positions || "").split("/").includes(label);
}

function render() {
  app.innerHTML = state.started ? boardHtml() : setupHtml();
  bind();
  armClock();
}

function setupHtml() {
  const categories = state.categories || [];
  return `
    <section class="setup">
      <header class="banner"><p>Draft room</p></header>
      <h1>Where are you picking?</h1>
      <p class="lede">Choose your draft position first. In the room you draft a player, and the roster files them into the most specific open slot, the same way Yahoo does.</p>
      <div class="slots" id="slot-choices"></div>
      <div class="fields">
        <label>Teams in the draft
          <input id="team-count" type="number" min="2" max="14" value="2">
        </label>
      </div>
      <p class="lede">Leave a category out of the ranking only if you are punting it.</p>
      <div class="punts">
        ${categories.map((category) => `<label><input type="checkbox" value="${category}"> ${category}</label>`).join("")}
      </div>
      <button class="primary" id="start" type="button">Open the board</button>
      <p class="error" id="error">${error}</p>
    </section>`;
}

function rosterHtml(roster) {
  return `
    <section class="roster ${roster.is_you ? "yours" : "theirs"}">
      <header><strong>${roster.name}</strong></header>
      <ol>
        ${roster.slots.map((slot) => {
          if (slot.player) {
            return `<li><span>${slot.label}</span><div class="filled"><span>${slot.player.player_name}</span><small>${slot.player.positions}</small></div></li>`;
          }
          return `<li><span>${slot.label}</span><div class="filled"><span>Empty</span></div></li>`;
        }).join("")}
      </ol>
    </section>`;
}

function boardHtml() {
  viewing = Math.min(viewing, state.rosters.length - 1);
  const roster = state.rosters[viewing];
  const rows = state.available.filter((player) => {
    const matches = player.player_name.toLowerCase().includes(query.toLowerCase());
    return matches && (filter === "All" || eligible(player, filter));
  });
  const title = state.complete
    ? "Draft complete"
    : `Round ${state.round}, pick ${state.pick_number}. ${state.your_turn ? "You are on the clock." : `${state.on_clock} is on the clock.`}`;
  const clockText = state.complete ? "" : formatClock(state.seconds_left);
  return `
    <section class="board">
      <header class="banner"><p>Draft room</p></header>
      <div class="board-head">
        <div class="call">
          <h1>${title}</h1>
          ${suggestionHtml()}
          <p class="hint">${state.complete ? "The rosters are full." : "Other teams draft the best value left. You pick only on your turn."} <span id="clock">${clockText}</span></p>
          <ol class="log">${(state.log || []).slice(-4).map((pick) => `<li>${pick.pick_number}. ${pick.team} took ${pick.player_name} (${pick.slot_label})</li>`).join("")}</ol>
          <p class="error">${error}</p>
        </div>
        <div class="actions">
          <button class="primary" id="draft" type="button" ${state.complete ? "disabled" : ""}>Draft</button>
          <button class="text-button" id="undo" type="button">Undo last pick</button>
          <button class="text-button" id="reset" type="button">New draft</button>
        </div>
      </div>
      <div class="layout">
        <div class="roster-column">
          <div class="team-switch">
            ${state.rosters.map((item, index) => `<button type="button" class="text-button ${index === viewing ? "selected" : ""}" data-view="${index}">${item.name}</button>`).join("")}
          </div>
          ${rosterHtml(roster)}
        </div>
        <section class="pool">
          <header>
            <div class="filters">
              ${(state.filters || ["All"]).map((name) => `<button type="button" class="text-button ${name === filter ? "selected" : ""}" data-filter="${name}">${name}</button>`).join("")}
            </div>
            <input id="search" placeholder="Find a player" value="${escapeAttr(query)}">
          </header>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Player</th><th>Pos</th><th>Tm</th><th>Value</th><th>Games</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>3PM</th></tr></thead>
              <tbody>
                ${rows.slice(0, 80).map((player) => `
                  <tr data-player="${escapeAttr(player.player_name)}" class="${player.player_name === selectedPlayer ? "selected" : ""}">
                    <td class="${player.rookie ? "rookie" : ""}">${player.player_name}</td>
                    <td>${player.positions}</td>
                    <td>${player.team}</td>
                    <td>${player.total_value ?? ""}</td>
                    <td>${player.predicted_games ?? ""}</td>
                    <td>${player.pts ?? ""}</td><td>${player.reb ?? ""}</td><td>${player.ast ?? ""}</td>
                    <td>${player.stl ?? ""}</td><td>${player.blk ?? ""}</td><td>${player.fg3m ?? ""}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>
        </section>
        <section class="roster queue">
          <header><strong>Your queue</strong></header>
          <ol>
            ${(state.queue || []).map((player) => `<li><button type="button" data-unqueue="${escapeAttr(player.player_name)}">${player.player_name}</button></li>`).join("") || "<li><div class='filled'><span>Queue is empty</span></div></li>"}
          </ol>
          <button class="text-button" id="enqueue" type="button">Add selected to queue</button>
        </section>
      </div>
    </section>`;
}

function suggestionHtml() {
  const pick = state.suggestion;
  if (!pick) return "";
  const options = pick.options || [];
  const cards = options.map((option, index) => {
    const games = option.predicted_games == null ? "" : ` · ${option.predicted_games} games`;
    const button = state.your_turn && !state.complete
      ? `<button class="primary" type="button" data-take="${escapeAttr(option.player_name)}">Draft ${option.player_name}</button>`
      : "";
    return `
      <article class="option">
        <p class="suggestion-kicker">Option ${index === 0 ? "A" : "B"}${option.percent == null ? "" : ` · ${option.percent}%`}</p>
        <p class="suggestion-name">${option.player_name}</p>
        <p class="suggestion-meta">${option.positions} · ${option.team} · ${option.total_value}${games} · files at ${option.slot_label}</p>
        ${button}
      </article>`;
  }).join("");
  return `
    <aside class="suggestion">
      <div class="options">${cards}</div>
      <p class="suggestion-reason">${pick.paragraph || ""}</p>
    </aside>`;
}

function bind() {
  const teamCount = document.querySelector("#team-count");
  if (teamCount) {
    drawSlotChoices(Number(teamCount.value));
    teamCount.addEventListener("input", () => drawSlotChoices(Number(teamCount.value)));
    document.querySelector("#start").addEventListener("click", startDraft);
  }
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      viewing = Number(button.dataset.view);
      render();
    });
  });
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      filter = button.dataset.filter;
      render();
    });
  });
  const search = document.querySelector("#search");
  if (search) {
    search.addEventListener("input", () => {
      query = search.value;
      const start = search.selectionStart;
      render();
      const next = document.querySelector("#search");
      if (next) {
        next.focus();
        next.setSelectionRange(start, start);
      }
    });
  }
  document.querySelectorAll("[data-player]").forEach((row) => {
    row.addEventListener("click", () => {
      selectedPlayer = row.dataset.player;
      render();
    });
  });
  const draft = document.querySelector("#draft");
  if (draft) draft.addEventListener("click", () => takePlayer(selectedPlayer));
  document.querySelectorAll("[data-take]").forEach((button) => {
    button.addEventListener("click", () => takePlayer(button.dataset.take));
  });
  const enqueue = document.querySelector("#enqueue");
  if (enqueue) enqueue.addEventListener("click", () => {
    if (!selectedPlayer) {
      error = "Select a player before adding them to the queue.";
      render();
      return;
    }
    run(() => api("/draft/api/queue", { player_name: selectedPlayer, action: "add" }));
  });
  document.querySelectorAll("[data-unqueue]").forEach((button) => {
    button.addEventListener("click", () => run(() => api("/draft/api/queue", { player_name: button.dataset.unqueue, action: "remove" })));
  });
  const undo = document.querySelector("#undo");
  if (undo) undo.addEventListener("click", () => run(() => api("/draft/api/undo", {})));
  const reset = document.querySelector("#reset");
  if (reset) reset.addEventListener("click", () => run(async () => {
    query = "";
    selectedPlayer = "";
    filter = "All";
    return api("/draft/api/reset", {});
  }));
}

function formatClock(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

function armClock() {
  if (clock) clearInterval(clock);
}

let runningOthers = false;

async function playOthers() {
  if (runningOthers || !state.started || state.complete || state.your_turn) return;
  runningOthers = true;
  try {
    while (state.started && !state.complete && !state.your_turn) {
      state = await api("/draft/api/opponent-pick", {});
      render();
      await new Promise((resolve) => setTimeout(resolve, 280));
    }
  } catch (exc) {
    error = exc.message;
    render();
  } finally {
    runningOthers = false;
  }
}

function drawSlotChoices(count) {
  const holder = document.querySelector("#slot-choices");
  if (!holder) return;
  const current = Number(holder.querySelector(".selected")?.dataset.pick || 1);
  const pick = Math.min(current, count);
  holder.innerHTML = Array.from({ length: count }, (_, index) => {
    const number = index + 1;
    return `<button type="button" class="slot-choice ${number === pick ? "selected" : ""}" data-pick="${number}">${number}</button>`;
  }).join("");
  holder.querySelectorAll(".slot-choice").forEach((button) => {
    button.addEventListener("click", () => {
      holder.querySelectorAll(".slot-choice").forEach((item) => item.classList.remove("selected"));
      button.classList.add("selected");
    });
  });
}

async function startDraft() {
  const draftSlot = document.querySelector(".slot-choice.selected")?.dataset.pick;
  const teamCount = document.querySelector("#team-count").value;
  const punts = [...document.querySelectorAll(".punts input:checked")].map((input) => input.value);
  if (!draftSlot) {
    error = "Choose the position you are picking.";
    render();
    return;
  }
  await run(() => api("/draft/api/start", { draft_slot: Number(draftSlot), team_count: Number(teamCount), punts }));
  await playOthers();
}

async function takePlayer(playerName) {
  if (!playerName) {
    error = "Select the player you are drafting.";
    render();
    return;
  }
  await run(() => api("/draft/api/pick", { player_name: playerName }));
  selectedPlayer = "";
  await playOthers();
}

async function run(action) {
  try {
    error = "";
    state = await action();
    render();
  } catch (exc) {
    error = exc.message;
    render();
  }
}

function escapeAttr(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
}

run(() => api("/draft/api/state")).then(() => playOthers());
