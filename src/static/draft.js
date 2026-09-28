const app = document.querySelector("#app");
let state = { started: false, categories: [], team_count: 16, budget: 200 };
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
  if (label === "BN") return true;
  return String(player.positions || "").split("/").includes(label);
}

function render() {
  app.innerHTML = state.started ? boardHtml() : setupHtml();
  bind();
}

function setupHtml() {
  const categories = state.categories || [];
  const teams = state.team_count || 16;
  return `
    <section class="setup">
      <header class="banner"><p>Pilsner mock</p></header>
      <h1>Where do you nominate?</h1>
      <p class="lede">This is the practice room: Yahoo clocks, computers, circular nominations. The live helper is a different page. The lab runs thousands of rooms and sale scenarios.</p>
      <div class="slots" id="slot-choices"></div>
      <div class="fields">
        <label>Teams
          <input id="team-count" type="number" min="2" max="16" value="${teams}">
        </label>
        <label>Budget
          <input id="budget" type="number" min="50" max="240" value="${state.budget || 200}">
        </label>
      </div>
      <p class="lede">Leave a category out of the price only if you are punting it. Personal fouls stay in unless you tick them. Fewer fouls win that category.</p>
      <div class="punts">
        ${categories.map((category) => `<label><input type="checkbox" value="${category}"> ${category}</label>`).join("")}
      </div>
      <button class="primary" id="start" type="button">Open the board</button>
      <p class="lede"><a href="/helper">Live room helper</a> — type what Yahoo shows. Separate from this mock.</p>
      <p class="error" id="error">${error}</p>
    </section>`;
}

function money(value) {
  return value == null ? "" : `$${value}`;
}

function rosterHtml(roster) {
  return `
    <section class="roster ${roster.is_you ? "yours" : "theirs"}">
      <header><strong>${roster.name}</strong><small>${money(roster.budget)} left</small></header>
      <ol>
        ${roster.slots.map((slot) => {
          if (slot.player) {
            return `<li><span>${slot.label}</span><div class="filled"><span>${slot.player.player_name}</span><small>${money(slot.player.price)}</small></div></li>`;
          }
          return `<li><span>${slot.label}</span><div class="filled"><span>Empty</span></div></li>`;
        }).join("")}
      </ol>
    </section>`;
}

function boardHtml() {
  viewing = Math.min(viewing, (state.rosters || []).length - 1);
  const roster = (state.rosters || [])[viewing] || { slots: [], name: "", budget: 0 };
  const rows = (state.available || []).filter((player) => {
    const matches = player.player_name.toLowerCase().includes(query.toLowerCase());
    return matches && (filter === "All" || eligible(player, filter));
  });
  const clock = formatClock(state.seconds_left);
  const title = state.complete
    ? "Auction complete"
    : state.on_block
      ? `${state.on_block.player_name} · ${money(state.on_block.bid)} · ${state.on_block.high_bidder} · ${clock}`
      : `${state.your_turn ? "You nominate" : `${state.on_clock} nominates`} · ${clock}`;
  return `
    <section class="board">
      <header class="banner"><p>Pilsner mock</p></header>
      <div class="board-head">
        <div class="call">
          <h1>${title}</h1>
          <p class="hint">${state.guide || ""} You have ${money(state.budget_left)} and ${state.spots_left} seats left.${state.nomination_slot ? ` You nominate in seat ${state.nomination_slot}.` : ""}</p>
          ${coachHtml()}
          ${blockHtml()}
          ${suggestionHtml()}
          <ol class="log">${(state.log || []).slice(-5).map((pick) => `<li>${pick.pick_number}. ${pick.team} paid ${money(pick.price)} for ${pick.player_name} (${pick.slot_label})</li>`).join("")}</ol>
          <p class="error">${error}</p>
        </div>
        <div class="actions">
          <button class="primary" id="nominate" type="button" ${state.can_nominate ? "" : "disabled"}>Nominate</button>
          <button class="primary" id="bid" type="button" ${!state.on_block || state.complete ? "disabled" : ""}>Offer ${state.on_block ? money(state.on_block.next_bid) : ""}</button>
          <button class="text-button" id="undo" type="button">Undo</button>
          <button class="text-button" id="reset" type="button">New draft</button>
        </div>
      </div>
      <div class="layout">
        <div class="roster-column">
          <div class="team-switch">
            ${(state.rosters || []).map((item, index) => `<button type="button" class="text-button ${index === viewing ? "selected" : ""}" data-view="${index}">${item.name}</button>`).join("")}
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
              <thead><tr><th>Player</th><th>Pos</th><th>$</th><th>Value</th><th>Games</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>DD</th><th>PF</th></tr></thead>
              <tbody>
                ${rows.slice(0, 80).map((player) => `
                  <tr data-player="${escapeAttr(player.player_name)}" class="${player.player_name === selectedPlayer ? "selected" : ""}">
                    <td class="${player.rookie ? "rookie" : ""}">${player.player_name}${player.superstar ? " ★" : ""}</td>
                    <td>${player.positions}</td>
                    <td>${money(player.auction_value)}</td>
                    <td>${player.total_value ?? ""}</td>
                    <td>${player.predicted_games ?? ""}</td>
                    <td>${player.mp ?? ""}</td>
                    <td>${player.pts ?? ""}</td>
                    <td>${player.reb ?? ""}</td>
                    <td>${player.ast ?? ""}</td>
                    <td>${player.dd ?? ""}</td>
                    <td>${player.pf ?? ""}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>
        </section>
        <section class="roster queue">
          <header><strong>Watch list</strong></header>
          <ol>
            ${(state.queue || []).map((player) => `<li><button type="button" data-unqueue="${escapeAttr(player.player_name)}">${player.player_name} ${money(player.auction_value)}</button></li>`).join("") || "<li><div class='filled'><span>Empty</span></div></li>"}
          </ol>
          <button class="text-button" id="enqueue" type="button">Add selected</button>
        </section>
      </div>
    </section>`;
}

function coachHtml() {
  const coach = state.coach;
  if (!coach) return "";
  const bid = coach.bid == null ? "—" : money(coach.bid);
  return `
    <section class="bug call-${coach.call}">
      <header>
        <p class="bug-name">${coach.player_name}</p>
        <p class="bug-bid">${bid}</p>
      </header>
      <ol>
        <li class="${coach.call === "stay" || coach.call === "ready" ? "on" : ""}"><span>Stay</span> ${money(coach.stay)}</li>
        <li class="${coach.call === "stretch" ? "on" : ""}"><span>Stretch</span> ${money(coach.stretch)}</li>
        <li class="${coach.call === "pass" ? "on" : ""}"><span>Pass</span> over ${money(coach.stretch)}</li>
      </ol>
      <p class="bug-why">${coach.why}</p>
    </section>`;
}

function blockHtml() {
  const block = state.on_block;
  if (!block) return "";
  const usual = block.typical_low != null ? ` · usual sale ${money(block.typical_low)}–${money(block.typical_high)}` : "";
  return `<p class="lede">${block.player_name} · ${block.positions} · current ${money(block.bid)} · ${block.high_bidder} has the offer · listed ${money(block.auction_value)}${usual} · stay in until ${money(block.your_max)}. ${block.your_high ? "You are high." : ""}</p>`;
}

function suggestionHtml() {
  const pick = state.suggestion;
  if (!pick) return "";
  const cards = (pick.options || []).map((option, index) => {
    const games = option.predicted_games == null ? "" : ` · ${option.predicted_games} games`;
    const button = option.action === "nominate" && state.phase === "nominate" && !state.on_block
      ? `<button class="primary" type="button" data-nominate="${escapeAttr(option.player_name)}">${option.label || "Nominate"}</button>`
      : option.action === "bid" && state.on_block
        ? `<button class="primary" type="button" data-offer="${option.bid}">${option.label || "Offer"}</button>`
        : "";
    return `
      <article class="option">
        <p class="suggestion-kicker">${option.label || (index === 0 ? "A" : "B")}${option.percent == null ? "" : ` · ${option.percent}%`}</p>
        <p class="suggestion-name">${option.player_name}</p>
        <p class="suggestion-meta">${option.positions || ""} · listed ${money(option.auction_value)}${option.typical_low != null ? ` · usual ${money(option.typical_low)}–${money(option.typical_high)}` : ""} · pay up to ${money(option.max_bid)}${games}</p>
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
  const nominate = document.querySelector("#nominate");
  if (nominate) nominate.addEventListener("click", () => nominatePlayer(selectedPlayer));
  document.querySelectorAll("[data-nominate]").forEach((button) => {
    button.addEventListener("click", () => nominatePlayer(button.dataset.nominate));
  });
  const bid = document.querySelector("#bid");
  if (bid) bid.addEventListener("click", () => offer(state.on_block?.next_bid));
  document.querySelectorAll("[data-offer]").forEach((button) => {
    button.addEventListener("click", () => offer(Number(button.dataset.offer)));
  });
  const enqueue = document.querySelector("#enqueue");
  if (enqueue) enqueue.addEventListener("click", () => {
    if (!selectedPlayer) {
      error = "Select a player first.";
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
  const budget = document.querySelector("#budget").value;
  const punts = [...document.querySelectorAll(".punts input:checked")].map((input) => input.value);
  if (!draftSlot) {
    error = "Choose your nomination order.";
    render();
    return;
  }
  await run(() => api("/draft/api/start", { draft_slot: Number(draftSlot), team_count: Number(teamCount), budget: Number(budget), punts }));
  armClock();
}

async function nominatePlayer(playerName) {
  if (!playerName) {
    error = "Select the player you are nominating.";
    render();
    return;
  }
  await run(() => api("/draft/api/nominate", { player_name: playerName, opening: 1 }));
  selectedPlayer = "";
}

async function offer(amount) {
  if (!amount) return;
  await run(() => api("/draft/api/bid", { amount }));
}

let ticking = false;

function armClock() {
  if (clock) clearInterval(clock);
  if (!state.started || state.complete) return;
  clock = setInterval(() => {
    if (ticking) return;
    ticking = true;
    api("/draft/api/tick", {})
      .then((next) => {
        state = next;
        if (!state.started) {
          error = "";
          if (clock) clearInterval(clock);
        } else if (state.complete && clock) {
          clearInterval(clock);
        }
        render();
      })
      .catch(() => {
        ticking = false;
      })
      .finally(() => {
        ticking = false;
      });
  }, 400);
}

function formatClock(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

async function run(action) {
  try {
    error = "";
    state = await action();
    if (!state.started && clock) clearInterval(clock);
    render();
    if (state.started && !state.complete) armClock();
  } catch (exc) {
    error = exc.message;
    render();
  }
}

function escapeAttr(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
}

run(() => api("/draft/api/state")).then(() => armClock());
