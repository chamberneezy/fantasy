const app = document.querySelector("#app");
const MARK = "/static/mark.png";

let state = { started: false, categories: [] };
let error = "";
let line = "";
let day = "";
let busy = false;

function brand() {
  return `<a class="brand" href="/" data-home-reset aria-label="NBA Fantasy home. Clears helper, mock, lab, and season."><span class="mark-wrap"><img class="mark" src="${MARK}" width="64" height="64" alt=""></span><span class="wordmark">NBA Fantasy</span></a>`;
}

async function api(path, body) {
  const response = await fetch(day ? `${path}?date=${day}` : path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Could not read that.");
  return payload;
}

function banner() {
  return `<header class="banner"><div class="banner-inner">${brand()}<nav class="links"><a href="/helper">Helper</a><a href="/season">Season</a><a href="/draft">Mock</a><a href="/lab">Lab</a>${window.themeToggleHtml ? window.themeToggleHtml() : ""}</nav></div></header>`;
}

function cats() {
  const tape = state.tape || {};
  const calls = state.calls || {};
  return `<ul class="cats">${(state.categories || []).map((cat) => {
    const call = calls[cat] || "ok";
    const value = tape[cat];
    const shown = value == null ? "—" : (value > 0 ? `+${value.toFixed(1)}` : value.toFixed(1));
    return `<li class="${call}"><span>${cat}</span><strong>${shown}</strong></li>`;
  }).join("")}</ul>`;
}

function roster() {
  const rows = state.roster || [];
  const il = state.il_enabled ? (state.il || []) : [];
  return `<ul class="wallet season-roster">${rows.map((row) => {
    const games = row.games == null ? "—" : `${row.games} g`;
    const ilBtn = state.il_enabled ? `<button type="button" class="text" data-il="${row.player_name}">IL</button>` : "";
    const dropBtn = row.protected ? "" : `<button type="button" class="text" data-drop="${row.player_name}">Drop</button>`;
    return `<li><span>${row.label} ${row.player_name}${row.unlisted ? " · $1" : ""}</span><span>${games}${ilBtn}${dropBtn}</span></li>`;
  }).join("")}</ul>${il.length ? `<p class="next-head">IL</p><ul class="wallet">${il.map((row) => `<li><span>${row.slot_id} ${row.player_name}</span><button type="button" class="text" data-activate="${row.player_name}">Activate</button></li>`).join("")}</ul>` : ""}`;
}

function streamers() {
  const rows = state.streamers || [];
  if (!rows.length) return "";
  return `<div class="nexts"><p class="next-head">Adds · holes ${ (state.categories || []).filter((cat) => (state.calls || {})[cat] === "hole").join(" · ") || "none"}</p><ul>${rows.map((row) => `<li><button type="button" data-add="${row.player_name}"><span class="next-who">${row.player_name}</span><span class="next-meta">${row.positions} · ${row.why}</span><strong>Add</strong></button></li>`).join("")}</ul></div>`;
}

function tip(utc) {
  const when = new Date(utc);
  if (Number.isNaN(when.getTime())) return "";
  return when.toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" });
}

function shortDate(iso) {
  const [, month, date] = iso.split("-");
  return `${Number(date)}.${Number(month)}.`;
}

function calendar() {
  const cal = state.calendar;
  if (!cal) return `<p class="roomline">No schedule yet. Refresh data to pull it.</p>`;
  const chosen = cal.day.date;
  const head = cal.days.map((d) => {
    const cls = [d.date === chosen ? "on" : "", d.date === cal.today ? "today" : "", d.over ? "over" : "", d.past ? "past" : ""].join(" ").trim();
    return `<th class="${cls}"><button type="button" data-day="${d.date}" aria-pressed="${d.date === chosen}"><span>${d.dow}</span><span>${shortDate(d.date)}</span><strong>${d.mine}</strong></button></th>`;
  }).join("");
  const body = cal.rows.map((row) => `<tr><th scope="row">${row.player_name}<span>${row.team || "—"} · ${row.games} g</span></th>${row.cells.map((cell, i) => {
    const d = cal.days[i];
    const cls = [d.date === chosen ? "on" : "", d.past ? "past" : ""].join(" ").trim();
    if (!cell) return `<td class="${cls}"></td>`;
    return `<td class="${cls} game${cell.b2b ? " b2b" : ""}${cell.seat ? " start" : " bench"}">${cell.home ? "" : "@"}${cell.opp}</td>`;
  }).join("")}</tr>`).join("");
  const prev = cal.prev ? `<button type="button" class="text" data-day="${cal.prev}">Earlier</button>` : "";
  const next = cal.next ? `<button type="button" class="text" data-day="${cal.next}">Later</button>` : "";
  return `<div class="slate"><div class="slate-head"><p class="next-head">Week ${cal.week} · ${shortDate(cal.start)}–${shortDate(cal.end)} · up to ${cal.starts_left} starts left</p><span>${prev}${next}</span></div><div class="slate-scroll"><table><thead><tr><th></th>${head}</tr></thead><tbody>${body}</tbody></table></div><p class="slate-key">Number = your players with a game. Red = more than 5, someone sits. Bold = start, faint = sit. Underline = second night of a back-to-back.</p></div>${dayCard(cal.day)}`;
}

function stat(value, digits = 1) {
  return Number(value).toFixed(digits);
}

function pct(value) {
  return `${Math.round(value * 100)}%`;
}

function dayCard(card) {
  const title = `${card.dow} ${shortDate(card.date)} · ${card.league_games} NBA games · ${card.mine} of yours`;
  if (!card.playing.length) return `<div class="nexts dayline"><p class="next-head">${title}</p><p class="lede">Nobody on your 10 plays.</p></div>`;
  const rows = card.playing.map((row) => {
    const p = row.line;
    const mark = row.status
      ? `<button type="button" class="text" data-status="clear" data-who="${row.player_name}">Clear ${row.status}</button>`
      : `<button type="button" class="text" data-status="out" data-who="${row.player_name}">Mark out</button>`;
    const where = `${row.home ? "vs" : "@"} ${row.opp} · ${tip(row.tip_utc)}${row.b2b ? " · back-to-back" : ""} · ${row.positions}`;
    const head = `<span class="next-who"><em class="${row.seat ? "seat" : "seat sit"}">${row.seat || "Sit"}</em> ${row.player_name}</span><span class="next-meta">${where}</span>`;
    if (!p) return `<li class="${row.seat ? "" : "benched"}"><div>${head}<span class="next-meta">${row.why || "No NBA games on file yet, so no line."}</span></div><strong>—</strong></li>`;
    const numbers = `${stat(p.mp, 0)} min · ${stat(p.pts)} pts · ${stat(p.reb)} reb · ${stat(p.ast)} ast · ${stat(p.stl)} stl · ${stat(p.blk)} blk · ${stat(p.fg3m)} 3s · ${stat(p.to)} to · ${stat(p.pf)} pf · FG ${stat(p.fgm)}/${stat(p.fga)} · FT ${stat(p.ftm)}/${stat(p.fta)} · DD ${pct(p.dd)}`;
    const notes = [];
    if (row.chance != null && row.chance < 1) notes.push(`${pct(row.chance)} to play${row.why ? ` (${row.why})` : ""}`);
    if (p.context) notes.push(`matchup ${p.context > 0 ? "+" : ""}${Math.round(p.context * 100)}% on points`);
    if (p.new_team) notes.push("new team, last year’s role may not carry");
    if (row.costs.length) notes.push(`costs you ${row.costs.join(", ")}`);
    const worth = row.swing == null ? `${p.value > 0 ? "+" : ""}${stat(p.value)}` : `${row.swing > 0 ? "+" : ""}${stat(row.swing, 2)}`;
    return `<li class="${row.seat ? "" : "benched"}"><div>${head}<span class="next-meta">${numbers}</span><span class="next-meta">${notes.join(" · ") || `From ${p.basis}`}</span><span class="next-meta">${mark}</span></div><strong>${worth}</strong></li>`;
  }).join("");
  const off = card.off.length ? `<p class="slate-key">No game: ${card.off.join(" · ")}</p>` : "";
  const key = card.matchup_aware
    ? "Right-hand number is the categories this game is worth against this opponent. A player sits when his seat is taken by a better game, or when he costs more than he adds."
    : "No opponent on file for this week, so the five is picked on 12-cat value alone.";
  return `<div class="nexts dayline"><p class="next-head">${title}</p><ul>${rows}</ul>${off}<p class="slate-key">${key} Tip times are in your local time.</p></div>`;
}

function matchupCard() {
  const m = state.calendar && state.calendar.matchup;
  if (!m) return "";
  const rows = m.cats.map((row) => {
    const call = row.win >= 0.65 ? "win" : row.win <= 0.35 ? "hole" : "ok";
    const digits = row.cat.includes("%") ? 3 : row.cat === "DD" ? 1 : 0;
    return `<tr class="${call}"><th scope="row">${row.cat}</th><td>${stat(row.mine, digits)}</td><td>${stat(row.theirs, digits)}</td><td><strong>${pct(row.win)}</strong></td></tr>`;
  }).join("");
  const missing = m.their_no_line.length ? ` Counted as zero, no games on file: ${m.their_no_line.join(", ")}.` : "";
  return `<div class="slate matchup"><p class="next-head">vs ${m.opponent} · ${stat(m.expected)} of 12 cats · win ${pct(m.win)} · tie ${pct(m.tie)} · lose ${pct(m.lose)}</p><div class="slate-scroll"><table><thead><tr><th></th><th>You</th><th>Them</th><th>Your chance</th></tr></thead><tbody>${rows}</tbody></table></div><p class="slate-key">Simulated week: ${m.my_starts} starts for you, ${m.their_starts} for them, assuming they start their best legal five every day.${missing}</p></div>`;
}

function plans() {
  const rows = (state.calendar && state.calendar.plans) || [];
  if (!rows.length) return "";
  return `<div class="nexts"><p class="next-head">Adds for this matchup · ${state.adds_left} left</p><ul>${rows.map((row) => `<li><button type="button" data-swap-add="${row.add}" data-swap-drop="${row.drop}"><span class="next-who">${row.add} for ${row.drop}</span><span class="next-meta">${row.team} · ${row.positions}${row.verified ? "" : " (position guessed)"} · ${row.games} games left · week ${row.win >= 0 ? "+" : ""}${Math.round(row.win * 100)}% · season value ${stat(row.add_value)} vs ${stat(row.drop_value)}</span><strong>${row.cats > 0 ? "+" : ""}${stat(row.cats, 2)}</strong></button></li>`).join("")}</ul><p class="slate-key">Right-hand number is extra categories this week. Only players nobody owns, with 20+ NBA games on file. Tapping one drops and adds here; do it in Yahoo yourself.</p></div>`;
}

function feedLine() {
  const feed = state.feed || {};
  const when = feed.fetched_at ? new Date(feed.fetched_at).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "never";
  const failed = Object.keys(feed.errors || {});
  return `<p class="slate-key">NBA data pulled ${when} · ${feed.games_logged || 0} player-games this season${failed.length ? ` · failed: ${failed.join(", ")}` : ""}</p>`;
}

function desk() {
  return `${banner()}<div class="sheet"><p class="lede">${state.note || "Daily – Today. 4 adds/week. No waivers. No IL."}</p><p class="roomline">Week ${state.week} · ${state.adds_left} adds left</p>${cats()}${matchupCard()}${calendar()}<form class="feed" id="season-feed"><input id="q" type="text" autocomplete="off" spellcheck="false" placeholder="name · add or drop" value="${line.replace(/"/g, "&quot;")}"></form>${error ? `<p class="error">${error}</p>` : ""}<div class="close season-acts"><button type="button" class="me" id="do-add">Add</button><button type="button" class="sold" id="do-drop">Drop</button></div>${roster()}${plans() || streamers()}<div class="actions"><button type="button" class="text" id="week">New week</button><button type="button" class="text" id="refresh"${busy ? " disabled" : ""}>${busy ? "Pulling…" : "Refresh data"}</button></div>${feedLine()}</div>`;
}

function paint() {
  if (!state.started) {
    app.innerHTML = `${banner()}<div class="sheet"><h1>Season</h1><p class="lede">Your 10. 12-cat tape. 4 adds a week. No IL — a DNP costs a drop.</p><button type="button" class="go" id="start">Open the pad</button></div>`;
    return;
  }
  // Browsing days must not pull the keyboard up, so only a typist keeps the caret.
  const typing = document.activeElement instanceof HTMLInputElement && document.activeElement.id === "q";
  app.innerHTML = desk();
  const input = document.querySelector("#q");
  if (input) {
    input.value = line;
    if (typing) {
      input.focus();
      input.selectionStart = input.selectionEnd = line.length;
    }
  }
}

async function boot() {
  try {
    state = await api("/season/api/state");
    if (!state.started) state = await api("/season/api/start", {});
    error = "";
  } catch (exc) {
    error = exc.message;
  }
  paint();
}

async function act(path, query) {
  error = "";
  try {
    state = await api(path, { query });
    line = "";
  } catch (exc) {
    error = exc.message;
  }
  paint();
}

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (target.id === "start") {
    boot();
    return;
  }
  if (target.id === "do-add") {
    act("/season/api/add", line);
    return;
  }
  if (target.id === "do-drop") {
    act("/season/api/drop", line);
    return;
  }
  if (target.id === "refresh") {
    busy = true;
    paint();
    api("/season/api/refresh", {}).then((payload) => {
      state = payload;
      error = "";
    }).catch((exc) => {
      error = exc.message;
    }).finally(() => {
      busy = false;
      paint();
    });
    return;
  }
  const mark = target.closest("[data-status]");
  if (mark) {
    error = "";
    api("/season/api/status", { query: mark.getAttribute("data-who"), status: mark.getAttribute("data-status") }).then((payload) => {
      state = payload;
    }).catch((exc) => {
      error = exc.message;
    }).finally(paint);
    return;
  }
  const swap = target.closest("[data-swap-add]");
  if (swap) {
    error = "";
    api("/season/api/drop", { query: swap.getAttribute("data-swap-drop") })
      .then(() => api("/season/api/add", { query: swap.getAttribute("data-swap-add") }))
      .then((payload) => {
        state = payload;
      }).catch((exc) => {
        error = exc.message;
      }).finally(paint);
    return;
  }
  const pick = target.closest("[data-day]");
  if (pick) {
    day = pick.getAttribute("data-day");
    api("/season/api/state").then((payload) => {
      state = payload;
      error = "";
    }).catch((exc) => {
      error = exc.message;
    }).finally(paint);
    return;
  }
  if (target.id === "week") {
    api("/season/api/week", {}).then((payload) => {
      state = payload;
      error = "";
      paint();
    }).catch((exc) => {
      error = exc.message;
      paint();
    });
    return;
  }
  const add = target.closest("[data-add]");
  if (add) {
    act("/season/api/add", add.getAttribute("data-add"));
    return;
  }
  const drop = target.closest("[data-drop]");
  if (drop) {
    act("/season/api/drop", drop.getAttribute("data-drop"));
    return;
  }
  const inj = target.closest("[data-il]");
  if (inj && state.il_enabled) {
    act("/season/api/il", inj.getAttribute("data-il"));
    return;
  }
  const actv = target.closest("[data-activate]");
  if (actv) {
    act("/season/api/activate", actv.getAttribute("data-activate"));
  }
});

document.addEventListener("submit", (event) => {
  if (!(event.target instanceof HTMLFormElement) || event.target.id !== "season-feed") return;
  event.preventDefault();
  act("/season/api/add", line);
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.id !== "q") return;
  line = target.value;
});

boot();
