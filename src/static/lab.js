const app = document.querySelector("#app");
let report = { ready: false, n: 0, draft_slot: 5, policy: "stay" };
let card = null;
let error = "";
let running = "";
let seat = 5;
let policy = "stay";
let player = "jokic";
let buyer = "room";
let price = 86;
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
  if (!response.ok) throw new Error(payload.error || "The lab could not do that.");
  return payload;
}

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function policyLine(value) {
  return value === "stretch" ? "stretch on the first star" : "stay";
}

function statusLine() {
  if (running) {
    return `Running ${Number(running).toLocaleString()} rooms. Seat ${seat}. You follow ${policyLine(policy)}.`;
  }
  if (report.ready) {
    return `${report.n.toLocaleString()} rooms. Seat ${report.draft_slot}. You follow ${policyLine(report.policy)}.`;
  }
  return "No tape yet. Run a batch.";
}

function readControls() {
  const seatEl = document.querySelector("#seat");
  const policyEl = document.querySelector("#policy");
  if (seatEl) {
    const next = Number(seatEl.value);
    if (Number.isFinite(next) && next >= 1) seat = Math.min(16, Math.max(1, Math.round(next)));
  }
  if (policyEl) policy = policyEl.value === "stretch" ? "stretch" : "stay";
}

function adoptReport(payload) {
  report = payload;
  if (report.draft_slot) seat = report.draft_slot;
  if (report.policy) policy = report.policy;
}

function money(value) {
  return value == null ? "—" : `$${value}`;
}

function render() {
  app.innerHTML = `
    <section class="room">
      <header class="banner">
        <div class="banner-inner">
          ${brand()}
          <nav class="links">
            <a href="/helper">Helper</a>
            <a href="/draft">Mock</a>
            ${themeToggleHtml()}
          </nav>
        </div>
      </header>
      <h1>What the room does to you.</h1>
      <p class="lede">Bots bid inside Stay–Stretch, and a few heat names go over. You sit in a nomination seat and pay Stay unless you switch the policy. A scenario is a filter on those rooms: Jokic to the field at $86, then what is left for you.</p>
      <div class="tools">
        <label>Seat <input id="seat" type="number" min="1" max="16" value="${seat}"></label>
        <label>Policy
          <select id="policy">
            <option value="stay" ${policy === "stay" ? "selected" : ""}>Stay</option>
            <option value="stretch" ${policy === "stretch" ? "selected" : ""}>Stretch first star</option>
          </select>
        </label>
        <button class="go" id="run-2k" type="button" ${running ? "disabled" : ""}>${running === "2000" ? "Running…" : "Run 2,000"}</button>
        <button class="go quiet" id="run-10k" type="button" ${running ? "disabled" : ""}>${running === "10000" ? "Running…" : "Run 10,000"}</button>
      </div>
      <p class="lede">${statusLine()}</p>
      <p class="error">${error}</p>
      ${report.ready ? bodyHtml() : ""}
    </section>`;
  bind();
}

function squadHtml(rows, title, note) {
  if (!rows || !rows.length) return "";
  return `
    <section class="squad">
      <h2>${title}</h2>
      ${note ? `<p class="lede">${note}</p>` : ""}
      <ol>
        ${rows.map((row) => `
          <li>
            <span class="pos">${row.label}</span>
            <span class="who">${row.name || "—"} ${money(row.price)}</span>
            <span class="rate">${pct(row.p)}</span>
            <span class="alts">${(row.alts || []).map((item) => `${item.name} ${pct(item.p)}`).join(" · ")}</span>
          </li>`).join("")}
      </ol>
    </section>`;
}

function bodyHtml() {
  const you = report.you || {};
  const plays = (report.plays || []).map((line) => `<li>${line}</li>`).join("");
  const rows = (report.stars || []).map((row) => `
    <tr>
      <td><button type="button" data-name="${row.name}">${row.name}</button></td>
      <td>${row.positions || ""}</td>
      <td>${money(row.listed)}</td>
      <td>${money(row.stay)}</td>
      <td>${money(row.stretch)}</td>
      <td>${money(row.median)}</td>
      <td class="hide-s">${money(row.p25)}–${money(row.p75)}</td>
      <td>${pct(row.p_you)}</td>
      <td class="${row.p_over_stretch >= 0.18 ? "heat" : ""}">${pct(row.p_over_stretch)}</td>
    </tr>`).join("");
  const scene = card ? `
    <section class="card">
      <h2>${card.player_name}</h2>
      <p class="now">${card.buyer} ${money(card.price)}</p>
      <p>${card.why}</p>
      <p class="lede">${card.matched} rooms · leftover ${money(card.median_leftover)} · a star still ${pct(card.p_star)}</p>
      <ul class="next">
        ${(card.next || []).map((item) => `<li><span>${item.name}</span><span>${pct(item.p)}</span></li>`).join("")}
      </ul>
      ${squadHtml(card.squad, "Your seats in these rooms", "Each seat is its own count. Not one roster.")}
    </section>` : "";
  const often = (you.common || []).slice(0, 8).map((row) => `${row.name} ${pct(row.p)}`).join(" · ");
  return `
    ${squadHtml(you.squad, "Most common name at each seat", "Each seat is counted on its own across rooms. Same name cannot sit twice. Stretching a star leaves $1 seats.")}
    ${often ? `<p class="lede">Names you actually roster most often: ${often}.</p>` : ""}
    <ol class="plays">${plays}</ol>
    <div class="tools">
      <label>Name <input id="who" value="${player}"></label>
      <label>Buyer
        <select id="buyer">
          <option value="room" ${buyer === "room" ? "selected" : ""}>Room</option>
          <option value="me" ${buyer === "me" ? "selected" : ""}>Me</option>
        </select>
      </label>
      <label>Near $ <input id="price" type="number" min="1" max="200" value="${price}"></label>
      <button class="go" id="ask" type="button">Read the rooms</button>
    </div>
    ${scene}
    <table>
      <thead>
        <tr>
          <th>Name</th><th>Pos</th><th>List</th><th>Stay</th><th>Stretch</th><th>Median</th>
          <th class="hide-s">Room</th><th>You</th><th>Over</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="lede">You land one $40+ name in ${pct(you.p_one_star)} of rooms, two in ${pct(you.p_two_stars)}. Median leftover ${money(you.median_leftover)}.</p>`;
}

function bind() {
  const seatEl = document.querySelector("#seat");
  const policyEl = document.querySelector("#policy");
  if (seatEl) seatEl.addEventListener("change", readControls);
  if (policyEl) policyEl.addEventListener("change", readControls);
  const run2 = document.querySelector("#run-2k");
  const run10 = document.querySelector("#run-10k");
  if (run2) run2.addEventListener("click", () => startRun(2000));
  if (run10) run10.addEventListener("click", () => startRun(10000));
  const ask = document.querySelector("#ask");
  if (ask) ask.addEventListener("click", askRooms);
  document.querySelectorAll("[data-name]").forEach((button) => {
    button.addEventListener("click", () => {
      player = button.dataset.name;
      const row = (report.stars || []).find((item) => item.name === player);
      if (row) price = row.median_field || row.median;
      render();
    });
  });
}

async function startRun(n) {
  readControls();
  running = String(n);
  error = "";
  card = null;
  render();
  try {
    adoptReport(await api("/lab/api/run", { n, draft_slot: seat, policy }));
  } catch (exc) {
    error = exc.message;
  }
  running = "";
  render();
  if (report.ready && window.NBAMotion) window.NBAMotion.pulse("deal", 900);
}

async function askRooms() {
  player = document.querySelector("#who").value.trim();
  buyer = document.querySelector("#buyer").value;
  price = Number(document.querySelector("#price").value);
  error = "";
  try {
    card = await api("/lab/api/scenario", { player_name: player, buyer, price });
  } catch (exc) {
    card = null;
    error = exc.message;
  }
  render();
}

api("/lab/api/report").then((payload) => {
  adoptReport(payload);
  render();
  if (payload.ready && window.NBAMotion) window.NBAMotion.pulse("deal", 900);
}).catch((exc) => {
  error = exc.message;
  render();
});
