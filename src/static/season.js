const app = document.querySelector("#app");
// GitHub Pages sets this: a read-only copy that reads one JSON file per day.
const STATIC = window.SEASON_STATIC || null;
const MARK = STATIC ? "img/mark.png" : "/static/mark.png";
const READ_ONLY = "This is the read-only copy. Add, drop and lineup changes happen on the laptop pad.";
let published = null;

let state = { started: false, categories: [] };
let error = "";
let line = "";
let day = "";
let busy = false;
// Matchup detail panels: which are open, and what the server sent for each.
const scoutOpen = new Set();
// My Team table: which stat line the columns show.
let view = "today";
const scouts = {};

function brand() {
  return `<a class="brand" href="${STATIC ? "index.html" : "/"}" data-home-reset aria-label="NBA Fantasy home. Clears helper, mock, lab, and season."><span class="mark-wrap"><img class="mark" src="${MARK}" width="64" height="64" alt=""></span><span class="wordmark">NBA Fantasy</span></a>`;
}

async function staticApi(path, body) {
  if (body) throw new Error(READ_ONLY);
  if (!published) published = await (await fetch(`${STATIC.base}index.json`, { cache: "no-cache" })).json();
  if (path !== "/season/api/state") throw new Error(READ_ONLY);
  if (day && !published.days.includes(day)) throw new Error("Only this week is published. Earlier and later weeks are on the laptop pad.");
  const response = await fetch(`${STATIC.base}${day || published.default}.json`, { cache: "no-cache" });
  if (!response.ok) throw new Error("This day is not published yet.");
  return response.json();
}

async function api(path, body) {
  if (STATIC) return staticApi(path, body);
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
  const links = STATIC
    ? `<a href="helper.html">Helper</a><a href="season.html">Season</a><a href="draft.html">Mock</a>`
    : `<a href="/helper">Helper</a><a href="/season">Season</a><a href="/draft">Mock</a><a href="/lab">Lab</a>`;
  return `<header class="banner"><div class="banner-inner">${brand()}<nav class="links">${links}${window.themeToggleHtml ? window.themeToggleHtml() : ""}</nav></div></header>`;
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
  const open = (iso) => iso && (!STATIC || (published && published.days.includes(iso)));
  const prev = open(cal.prev) ? `<button type="button" class="text" data-day="${cal.prev}">Earlier</button>` : "";
  const next = open(cal.next) ? `<button type="button" class="text" data-day="${cal.next}">Later</button>` : "";
  return `<div class="slate"><div class="slate-head"><p class="next-head">Week ${cal.week} · ${shortDate(cal.start)}–${shortDate(cal.end)} · up to ${cal.starts_left} starts left</p><span>${prev}${next}</span></div><div class="slate-scroll"><table><thead><tr><th></th>${head}</tr></thead><tbody>${body}</tbody></table></div><p class="slate-key">Number = your players with a game. Red = more than 5, someone sits. Bold = start, faint = sit. Underline = second night of a back-to-back.</p></div>${dayCard(cal.day)}`;
}

function stat(value, digits = 1) {
  return Number(value).toFixed(digits);
}

function pct(value) {
  return `${Math.round(value * 100)}%`;
}

const GROUP_NAMES = { G: "guards", F: "forwards", C: "centres" };

function ordinal(n) {
  const tail = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
  return `${n}${tail}`;
}

function scoutKey(row) {
  return `${row.player_name}|${row.opp}|${row.home ? 1 : 0}`;
}

function shortLine(p) {
  return `${stat(p.min, 0)} min · ${stat(p.pts)} pts · ${stat(p.reb)} reb · ${stat(p.ast)} ast · ${stat(p.fg3m)} 3s · ${stat(p.stl)} stl · ${stat(p.blk)} blk · ${stat(p.to)} to${p.fg_pct == null ? "" : ` · FG ${stat(p.fg_pct * 100)}%`}`;
}

function versusLine(v, o) {
  const keys = [["pts", "pts"], ["reb", "reb"], ["ast", "ast"], ["fg3m", "3s"], ["stl", "stl"], ["blk", "blk"], ["to", "to"]];
  const gaps = keys
    .map(([key, label]) => ({ label, gap: v[key] - o[key], good: key === "to" ? v[key] < o[key] : v[key] > o[key] }))
    .filter((row) => Math.abs(row.gap) >= 0.5)
    .map((row) => `<span class="${row.good ? "up" : "down"}">${row.gap > 0 ? "+" : ""}${stat(row.gap)} ${row.label}</span>`);
  if (v.fg_pct != null && o.fg_pct != null && Math.abs(v.fg_pct - o.fg_pct) >= 0.02) {
    const gap = (v.fg_pct - o.fg_pct) * 100;
    gaps.push(`<span class="${gap > 0 ? "up" : "down"}">${gap > 0 ? "+" : ""}${stat(gap)} FG%</span>`);
  }
  return gaps.length ? gaps.join(" · ") : "about his usual";
}

function scoutPanel(row) {
  const s = scouts[scoutKey(row)];
  if (!s) return `<div class="scout"><p class="slate-key">Reading the logs…</p></div>`;
  if (s.error) return `<div class="scout"><p class="error">${s.error}</p></div>`;
  const when = s.early ? `${s.team_basis}, last season. This season takes over once every team has 10 games.` : s.team_basis;
  const chips = s.allowed.map((c) => {
    const call = c.rank <= 10 ? "win" : c.rank >= 21 ? "hole" : "ok";
    return `<li class="${call}"><span>${c.cat}</span><strong>${ordinal(c.rank)}</strong><em>${c.ratio > 0 ? "+" : ""}${Math.round(c.ratio * 100)}%</em></li>`;
  }).join("");
  const parts = [];
  parts.push(`<p class="next-head">${s.opp} against ${GROUP_NAMES[s.group] || "his position"}</p>`);
  if (chips) parts.push(`<ul class="cats scout-cats">${chips}</ul><p class="slate-key">1st = the kindest of 30 for you in that category; % = what ${s.opp} gives up per minute to ${GROUP_NAMES[s.group] || "the group"} against league average. From ${when}</p>`);
  if (s.team) parts.push(`<p class="next-meta">Pace ${ordinal(s.team.pace_rank)} fastest · defence ${ordinal(s.team.drtg_rank)} softest (est. ${stat(s.team.drtg)} pts per 100)</p>`);
  if (s.history) {
    const v = s.history.versus;
    parts.push(`<p class="next-meta"><strong>vs ${s.opp} since ${s.history.seasons[0]}:</strong> ${v.games} g · ${shortLine(v)}</p><p class="next-meta">Against his own average in those seasons: ${versusLine(v, s.history.overall)}${v.games < 6 ? " · small sample" : ""}</p>`);
  } else {
    parts.push(`<p class="next-meta">Never played ${s.opp} in the seasons on file.</p>`);
  }
  if (s.meetings.length) {
    parts.push(`<p class="next-meta">Last meetings: ${s.meetings.map((m) => `${shortDate(m.date)}${String(m.date).slice(2, 4)} ${m.home ? "vs" : "@"} ${m.pts}/${m.reb}/${m.ast}, ${m.fg3m} 3s, ${m.stl} stl, ${m.blk} blk, ${m.to} to, FG ${m.fg}`).join(" · ")}</p>`);
  }
  if (s.splits && s.splits.home && s.splits.away) {
    const side = (label, p) => `<span class="${s.splits.tonight === label ? "tonight" : ""}">${label === "home" ? "Home" : "Away"} ${p.games} g: ${stat(p.pts)} pts · ${stat(p.reb)} reb · ${stat(p.ast)} ast${p.fg_pct == null ? "" : ` · FG ${stat(p.fg_pct * 100)}%`}</span>`;
    parts.push(`<p class="next-meta">${side("home", s.splits.home)} · ${side("away", s.splits.away)} <span class="slate-key">(${s.splits.basis}; tonight underlined)</span></p>`);
  }
  if (s.role) {
    parts.push(`<p class="next-meta">Usage ${s.role.usage == null ? "—" : `${stat(s.role.usage)}%`} · true shooting ${s.role.ts == null ? "—" : `${stat(s.role.ts * 100)}%`} <span class="slate-key">(${s.role.basis})</span></p>`);
  }
  parts.push(`<p class="slate-key">Information only. The simulated week already uses a small, clamped opponent factor. No offensive rebounds in the free logs, so pace and defence are estimates; read the ranks.</p>`);
  return `<div class="scout">${parts.join("")}</div>`;
}

function toggleScout(row) {
  const key = `${row.name}|${row.opp}|${row.home}`;
  if (scoutOpen.has(key)) {
    scoutOpen.delete(key);
    paint();
    return;
  }
  scoutOpen.add(key);
  paint();
  if (scouts[key] && !scouts[key].error) return;
  if (STATIC) {
    scouts[key] = (state.scouts || {})[key] || { error: "No matchup detail published for this game." };
    paint();
    return;
  }
  const query = new URLSearchParams({ name: row.name, opp: row.opp, home: row.home });
  fetch(`/season/api/scout?${query}`)
    .then((response) => response.json().then((payload) => (response.ok ? payload : { error: payload.error || "Could not read that." })))
    .catch(() => ({ error: "Could not reach the pad." }))
    .then((payload) => {
      scouts[key] = payload;
      paint();
    });
}

function dayCard(card) {
  const title = `${card.dow} ${shortDate(card.date)} · ${card.league_games} NBA games · ${card.mine} of yours`;
  if (!card.playing.length) return `<div class="nexts dayline"><p class="next-head">${title}</p><p class="lede">Nobody on your 10 plays.</p></div>`;
  const rows = card.playing.map((row) => {
    const p = row.line;
    const mark = STATIC
      ? ""
      : row.status
      ? `<button type="button" class="text" data-status="clear" data-who="${row.player_name}">Clear ${row.status}</button> · `
      : `<button type="button" class="text" data-status="out" data-who="${row.player_name}">Mark out</button> · `;
    const where = `${row.home ? "vs" : "@"} ${row.opp} · ${tip(row.tip_utc)}${row.b2b ? " · back-to-back" : ""} · ${row.positions}`;
    const head = `<span class="next-who"><em class="${row.seat ? "seat" : "seat sit"}">${row.seat || "Sit"}</em> ${row.player_name}</span><span class="next-meta">${where}</span>`;
    const open = scoutOpen.has(scoutKey(row));
    const scoutBtn = `<button type="button" class="text" data-scout="${row.player_name}" data-opp="${row.opp}" data-home="${row.home ? 1 : 0}" aria-expanded="${open}">${open ? "Hide matchup" : "Matchup"}</button>`;
    const detail = open ? scoutPanel(row) : "";
    if (!p) return `<li class="${row.seat ? "" : "benched"}"><div>${head}<span class="next-meta">${row.why || "No NBA games on file yet, so no line."}</span><span class="next-meta">${scoutBtn}</span></div><strong>—</strong>${detail}</li>`;
    const numbers = `${stat(p.mp, 0)} min · ${stat(p.pts)} pts · ${stat(p.reb)} reb · ${stat(p.ast)} ast · ${stat(p.stl)} stl · ${stat(p.blk)} blk · ${stat(p.fg3m)} 3s · ${stat(p.to)} to · ${stat(p.pf)} pf · FG ${stat(p.fgm)}/${stat(p.fga)} · FT ${stat(p.ftm)}/${stat(p.fta)} · DD ${pct(p.dd)}`;
    const notes = [];
    if (row.chance != null && row.chance < 1) notes.push(`${pct(row.chance)} to play${row.why ? ` (${row.why})` : ""}`);
    if (p.context) notes.push(`matchup ${p.context > 0 ? "+" : ""}${Math.round(p.context * 100)}% on points`);
    if (p.new_team) notes.push("new team, last year’s role may not carry");
    if (row.costs.length) notes.push(`costs you ${row.costs.join(", ")}`);
    const worth = row.swing == null ? `${p.value > 0 ? "+" : ""}${stat(p.value)}` : `${row.swing > 0 ? "+" : ""}${stat(row.swing, 2)}`;
    return `<li class="${row.seat ? "" : "benched"}"><div>${head}<span class="next-meta">${numbers}</span><span class="next-meta">${notes.join(" · ") || `From ${p.basis}`}</span><span class="next-meta">${mark}${scoutBtn}</span></div><strong>${worth}</strong>${detail}</li>`;
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

const VIEWS = [["today", "Tonight"], ["last", "Last game"], ["week", "This week"], ["l7", "7 days"], ["season", "Season"], ["proj", "Proj."]];
// Box-score order: minutes, what you pile up, what you want low, then shooting. Value closes the row.
const SHEET_COLS = [
  ["MIN", "mp", "lead"],
  ["PTS", "pts", "group"], ["REB", "reb"], ["AST", "ast"], ["STL", "stl"], ["BLK", "blk"], ["3PM", "fg3m"], ["DD", "dd"],
  ["TO", "to", "group"], ["PF", "pf"],
  ["FG%", "fg_pct", "group"], ["FT%", "ft_pct"],
];

function dow(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString([], { weekday: "short" });
}

function rate(value) {
  return value == null ? "—" : value.toFixed(3).replace(/^0/, "");
}

function cell(line, key, whole) {
  if (!line) return "—";
  const value = line[key];
  if (value == null) return "—";
  if (key === "fg_pct" || key === "ft_pct") return rate(value);
  if (key === "mp") return Math.round(value);
  if (key === "dd") return whole ? value : value.toFixed(2).replace(/^0/, "");
  return whole ? value : value.toFixed(1);
}

function boxLine(p) {
  const bits = [`${p.pts} pts`, `${p.reb} reb`, `${p.ast} ast`];
  if (p.fg3m) bits.push(`${p.fg3m} 3s`);
  if (p.stl) bits.push(`${p.stl} stl`);
  if (p.blk) bits.push(`${p.blk} blk`);
  bits.push(`${p.to} to`, `FG ${p.fgm}/${p.fga}`);
  return bits.join(" · ");
}

function brief() {
  const b = state.brief;
  if (!b) return "";
  const head = `This morning · ${dow(b.today)} ${shortDate(b.today)}`;
  const parts = [`<p class="next-head">${head}</p>`];
  if (!b.started) {
    parts.push(`<p class="next-meta">Week ${b.week} starts ${dow(b.starts_on)} ${shortDate(b.starts_on)}</p>`);
  } else if (b.so_far) {
    const f = b.so_far;
    parts.push(`<p class="brief-score">So far <strong>${f.won}–${f.lost}–${f.tied}</strong> <span class="next-meta">(won–lost–tied, as the pad seated your five)</span></p>`);
    parts.push(`<ul class="cats brief-cats">${f.cats.map((c) => {
      const digits = c.cat.includes("%") ? 3 : 0;
      return `<li class="${c.call}"><span>${c.cat}</span><strong>${c.cat.includes("%") ? rate(c.mine) : stat(c.mine, digits)}</strong><em>${c.cat.includes("%") ? rate(c.theirs) : stat(c.theirs, digits)}</em></li>`;
    }).join("")}</ul>`);
  }
  if (b.last_night.length || b.no_show.length) {
    const rows = b.last_night.map((p) => `<li><span class="next-who">${p.player_name}</span><span class="next-meta">${boxLine(p)}</span></li>`).join("");
    const dnp = b.no_show.length ? `<li><span class="next-meta">Had a game, did not play: ${b.no_show.join(", ")}</span></li>` : "";
    parts.push(`<p class="brief-sub">Last night · ${dow(b.yesterday)} ${shortDate(b.yesterday)}</p><ul class="brief-list">${rows}${dnp}</ul>`);
  }
  if (b.hurt.length) {
    parts.push(`<p class="brief-sub">Injuries</p><ul class="brief-list">${b.hurt.map((h) => `<li><span class="next-meta"><b class="inj">${h.short}</b> ${h.player_name}${h.part ? ` · ${h.part}` : ""}${h.back ? ` · back ~${shortDate(h.back)}` : ""}</span></li>`).join("")}</ul>`);
  }
  return `<div class="nexts brief">${parts.join("")}</div>`;
}

function dayChips(chosen) {
  const ahead = (state.brief && state.brief.ahead) || [];
  if (!ahead.length) return "";
  const days = ahead.map((d) => {
    const note = d.sits ? `${d.sits} sit${d.sits > 1 ? "" : "s"}` : d.empty && d.games ? `${d.empty} empty` : d.games ? "full" : "no games";
    const cls = [d.sits ? "busy" : d.empty >= 2 ? "light" : "", d.date === chosen ? "on" : ""].join(" ").trim();
    return `<button type="button" class="day-chip ${cls}" data-day="${d.date}" aria-pressed="${d.date === chosen}"><span>${d.dow} ${shortDate(d.date)}</span><strong>${d.games}</strong><em>${note}</em></button>`;
  }).join("");
  return `<div class="day-chips">${days}</div>`;
}

function tag(injury) {
  return injury ? ` <b class="inj" title="${injury.status}${injury.part ? ` · ${injury.part}` : ""}">${injury.short}</b>` : "";
}

function moves(sh) {
  if (sh.past) return `<p class="slate-key">Played. The table shows final lines for those who played.</p>`;
  const parts = [];
  if (sh.moves.length) {
    const rows = sh.moves.map((m) => {
      const start = m.start ? `Start <strong>${m.start}</strong>` : "Leave empty";
      const sit = m.sit ? `<span class="next-meta">Out of ${m.seat}: ${m.sit} — ${m.sit_why}</span>` : "";
      return `<li><em class="seat">${m.seat}</em><div><span>${start} <span class="next-meta">${m.start_why}</span></span>${sit}</div></li>`;
    }).join("");
    parts.push(`<div class="moves"><p class="brief-sub">${sh.moves.length} change${sh.moves.length > 1 ? "s" : ""} for ${dow(sh.date)} ${shortDate(sh.date)}</p><ul>${rows}</ul>${STATIC ? "" : `<button type="button" class="text" id="set-lineup">Done in Yahoo — mark these as set</button>`}</div>`);
  } else {
    parts.push(`<p class="next-meta moves-ok">Lineup is right for ${dow(sh.date)} ${shortDate(sh.date)} — no changes.</p>`);
  }
  if (sh.benched.length) {
    parts.push(`<p class="next-meta">Sits with a game: ${sh.benched.map((b) => `${b.player_name} ${b.game} — ${b.why}`).join(" · ")}</p>`);
  }
  if (sh.playing && sh.empty.length) {
    parts.push(`<p class="next-meta">Empty seat${sh.empty.length > 1 ? "s" : ""}: ${sh.empty.join(", ")} — nobody eligible plays.</p>`);
  }
  return parts.join("");
}

function myTeam() {
  const sh = state.calendar && state.calendar.sheet;
  if (!sh) return "";
  const tabs = VIEWS.map(([key, label]) => `<button type="button" class="text${view === key ? " on" : ""}" data-view="${key}" aria-pressed="${view === key}">${label}</button>`).join("");
  const head = `<tr><th>Slot</th><th class="pname">Player</th><th>${view === "week" ? "G" : "Opp"}</th>${SHEET_COLS.map(([label, , cls]) => `<th class="${cls || ""}">${label}</th>`).join("")}<th class="group value">Value</th></tr>`;
  const body = sh.rows.map((r) => {
    const line = r.stats[view];
    const whole = view === "last" || view === "week" || (view === "today" && r.banked);
    const slot = r.best !== r.slot && !sh.past ? `${r.slot}<span class="to">→ ${r.best}</span>` : r.slot;
    const game = r.game ? `${r.game.home ? "" : "@"}${r.game.opp}<span>${r.banked ? "final" : tip(r.game.tip_utc).replace(/^\S+\s/, "")}</span>` : "—";
    const drop = r.protected || STATIC ? "" : `<button type="button" class="text drop" data-drop="${r.player_name}">Drop</button>`;
    const cls = [r.slot === "BN" ? "bn" : "", r.game ? "" : "idle"].join(" ").trim();
    const where = view === "week" ? (line ? line.games : "—") : game;
    const value = line && line.value != null ? `${line.value > 0 ? "+" : ""}${line.value.toFixed(1)}` : "—";
    const tone = line && line.value != null ? (line.value >= 5 ? "up" : line.value < 0 ? "down" : "") : "";
    return `<tr class="${cls}"><td class="slot">${slot}</td><th scope="row">${r.player_name}${tag(r.injury)}<span>${r.team || "—"} · ${r.positions}${drop}</span></th><td class="opp">${where}</td>${SHEET_COLS.map(([, key, group]) => `<td class="${group || ""}">${cell(line, key, whole)}</td>`).join("")}<td class="group value ${tone}">${value}</td></tr>`;
  }).join("");
  const key = {
    today: "Tonight = projected line for this game (final once played), adjusted for opponent and venue.",
    last: "His most recent game before this day.",
    week: "Totals this fantasy week before this day; G = games.",
    l7: "Per game over the 7 days before this day.",
    season: "Per game this season, before this day.",
    proj: "The pad's season line for his next game.",
  }[view];
  const b = state.brief;
  const versus = b && b.opponent ? ` · Week ${b.week} vs ${b.opponent}` : "";
  return `<div class="slate team"><p class="next-head">My team · ${dow(sh.date)} ${shortDate(sh.date)} · ${sh.playing} play${versus}</p>${dayChips(sh.date)}<div class="views">${tabs}</div><div class="slate-scroll"><table><thead>${head}</thead><tbody>${body}</tbody></table></div><p class="slate-key">Slot = where he sits now; → = where the pad would put him. ${key} Value = 12-cat worth of a game like that (per game on totals); 0 is a typical player, +5 and up is very good. Tap a day above for its lineup; red = someone sits, blue = 2+ empty seats (an add pays most).</p>${moves(sh)}</div>`;
}

function publishedLine() {
  if (!published) return "";
  const when = new Date(published.published_at).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  return `<p class="slate-key">Read-only copy, published ${when} from the laptop pad (right after last night's final game, around 06:30–07:30, and at 18:00 and 23:30). Changes to your roster or lineup are made there.</p>`;
}

function desk() {
  const errorLine = error ? `<p class="error">${error}</p>` : "";
  const controls = STATIC
    ? errorLine
    : `<form class="feed" id="season-feed"><input id="q" type="text" autocomplete="off" spellcheck="false" placeholder="name · add or drop" value="${line.replace(/"/g, "&quot;")}"></form>${errorLine}<div class="close season-acts"><button type="button" class="me" id="do-add">Add</button><button type="button" class="sold" id="do-drop">Drop</button></div>`;
  const actions = STATIC
    ? publishedLine()
    : `<div class="actions"><button type="button" class="text" id="week">New week</button><button type="button" class="text" id="refresh"${busy ? " disabled" : ""}>${busy ? "Pulling…" : "Refresh data"}</button></div>`;
  return `${banner()}<div class="sheet">${myTeam()}${brief()}${matchupCard()}<p class="roomline">Week ${state.week} · ${state.adds_left} of 4 adds left</p>${calendar()}${controls}${plans() || streamers()}<p class="next-head tape-head">Roster strength · season z by category</p>${cats()}${actions}${feedLine()}</div>`;
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
  const tab = target.closest("[data-view]");
  if (tab) {
    view = tab.getAttribute("data-view");
    paint();
    return;
  }
  if (target.id === "set-lineup") {
    error = "";
    api("/season/api/lineup", {}).then((payload) => {
      state = payload;
    }).catch((exc) => {
      error = exc.message;
    }).finally(paint);
    return;
  }
  const scout = target.closest("[data-scout]");
  if (scout) {
    toggleScout({ name: scout.getAttribute("data-scout"), opp: scout.getAttribute("data-opp"), home: scout.getAttribute("data-home") });
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
