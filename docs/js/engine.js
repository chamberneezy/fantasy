const Pilsner = (() => {
  const CATEGORIES = ["MIN", "FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO", "PF", "DD"];
  const SLOTS = [
    ["PG", "PG"],
    ["SG", "SG"],
    ["SF", "SF"],
    ["PF", "PF"],
    ["C", "C"],
    ["BN1", "BN"],
    ["BN2", "BN"],
    ["BN3", "BN"],
    ["BN4", "BN"],
    ["BN5", "BN"],
  ];
  const FILTERS = ["All", "PG", "SG", "SF", "PF", "C"];
  const ROSTER_SIZE = 10;
  const DEFAULT_BUDGET = 200;
  const MIN_BUDGET = 160;
  const MAX_BUDGET = 240;
  const TEAM_COUNT = 16;
  const ELITE = 40;
  const STAR = 40;
  const MID = 20;
  const MIN_SAMPLES = 2;
  const HEAT_FLOOR = 0.85;
  const HEAT_CEILING = 1.22;
  const STAY_FACTOR = 1.05;
  const STRETCH_FACTOR = 1.12;
  const SECOND_STAR = 0.5;
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
    halliburton: "tyrese haliburton",
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

  let pool = [];
  let helper = null;

  function fold(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function nameKey(name) {
    return fold(name).replace(/['’.]/g, "").replace(/\s+/g, " ").trim();
  }

  function leftoverMax(budgetLeft, spotsLeft) {
    if (spotsLeft <= 0) return 0;
    return Math.max(0, budgetLeft - (spotsLeft - 1));
  }

  function typicalSale(listed) {
    const price = Math.max(1, listed | 0);
    return [Math.max(1, Math.round(price * 0.88)), Math.max(price, Math.round(price * 1.1))];
  }

  function stayPrice(listed, budgetLeft, spotsLeft, ownsElite, player) {
    const ceiling = leftoverMax(budgetLeft, spotsLeft);
    if (ceiling <= 0) return 0;
    const price = Math.max(1, listed | 0);
    if (ownsElite && price >= ELITE) return Math.max(1, Math.min(ceiling, Math.round(price * SECOND_STAR)));
    if (player && player.stay_market) return Math.max(1, Math.min(ceiling, player.stay_market | 0));
    return Math.max(1, Math.min(ceiling, Math.round(price * STAY_FACTOR)));
  }

  function stretchPrice(listed, budgetLeft, spotsLeft, ownsElite, player) {
    const stay = stayPrice(listed, budgetLeft, spotsLeft, ownsElite, player);
    const ceiling = leftoverMax(budgetLeft, spotsLeft);
    if (ceiling <= 0) return 0;
    const price = Math.max(1, listed | 0);
    if (ownsElite && price >= ELITE) return stay;
    if (player && player.stretch_market) return Math.max(stay, Math.min(ceiling, player.stretch_market | 0));
    return Math.max(stay, Math.min(ceiling, Math.round(price * STRETCH_FACTOR)));
  }

  function capBid(want, budgetLeft, spotsLeft) {
    if (spotsLeft <= 0) return 0;
    return Math.max(1, Math.min(want | 0, leftoverMax(budgetLeft, spotsLeft)));
  }

  function recommendedStay(listed, leftover) {
    if (leftover <= 0) return 0;
    return Math.max(1, Math.min(leftover, Math.round(Math.max(1, listed) * 1.05)));
  }

  function callFor(bid, stay, stretch) {
    if (bid == null) return "ready";
    if (bid <= stay) return "stay";
    if (bid <= stretch) return "stretch";
    return "pass";
  }

  function bucket(listed) {
    const price = Math.max(1, listed | 0);
    if (price >= STAR) return "star";
    if (price >= MID) return "mid";
    return "end";
  }

  function median(values) {
    const xs = [...values].sort((a, b) => a - b);
    const mid = Math.floor(xs.length / 2);
    return xs.length % 2 ? xs[mid] : (xs[mid - 1] + xs[mid]) / 2;
  }

  function fairMarks(player, listed, budget) {
    return [
      stayPrice(listed, budget, ROSTER_SIZE, false, player),
      stretchPrice(listed, budget, ROSTER_SIZE, false, player),
    ];
  }

  function saleMarks(item, budget) {
    const player = item.player || {};
    const listed = (item.listed || player.yahoo_listed || item.auction_value || 1) | 0;
    let stay = (item.fair_stay || 0) | 0;
    let stretch = (item.fair_stretch || 0) | 0;
    if (stay <= 0 || stretch <= 0) [stay, stretch] = fairMarks(player, listed, budget);
    return [listed, stay, stretch];
  }

  function readRoom(taken, teamCount, budget) {
    const samples = { star: [], mid: [], end: [] };
    let over = 0;
    let spent = 0;
    for (const item of taken) {
      const [listed, stay, stretch] = saleMarks(item, budget);
      const price = Math.max(1, (item.price || 1) | 0);
      spent += price;
      if (item.kind === "dynasty") continue;
      samples[bucket(listed)].push(price / Math.max(1, stay));
      if (listed >= STAR && price > stretch) over += 1;
    }
    const counts = { star: samples.star.length, mid: samples.mid.length, end: samples.end.length };
    const factors = { star: 1, mid: 1, end: 1 };
    for (const key of Object.keys(samples)) {
      if (samples[key].length < MIN_SAMPLES) continue;
      factors[key] = Math.round(Math.min(HEAT_CEILING, Math.max(HEAT_FLOOR, median(samples[key]))) * 1000) / 1000;
    }
    if (over >= 3 && factors.star > 1) {
      const lift = 1 + 0.45 * (factors.star - 1);
      factors.mid = Math.round(Math.min(HEAT_CEILING, Math.max(factors.mid, lift)) * 1000) / 1000;
    }
    const seatsLeft = Math.max(0, teamCount * ROSTER_SIZE - taken.length);
    const cash = teamCount * budget - spent;
    const perSeat = seatsLeft ? Math.round((cash / seatsLeft) * 10) / 10 : 0;
    const listening = Object.values(counts).some((count) => count >= MIN_SAMPLES);
    let note = "Stay is the published tape until two sales land in the same tier.";
    if (seatsLeft && perSeat < 8 && taken.length >= 8) note = `League leftover is $${perSeat} a seat. The $1 endgame is close.`;
    else if (listening && factors.star >= 1.08) note = `Stars are going ${factors.star.toFixed(2)}× Stay. This room's Stay is marked up.`;
    else if (listening && factors.star <= 0.92 && counts.star >= MIN_SAMPLES) note = `Stars are going ${factors.star.toFixed(2)}× Stay. This room is cheaper than the tape.`;
    else if (counts.star === 1) note = "One star sale is noise. A second $40+ hammer teaches the tier.";
    return { factors, counts, cash, seats_left: seatsLeft, per_seat: perSeat, note };
  }

  function factorFor(listed, room) {
    if (!room) return 1;
    return Number((room.factors || {})[bucket(listed)] || 1);
  }

  function applyRoom(stay, stretch, listed, budgetLeft, spotsLeft, ownsElite, room) {
    const ceiling = leftoverMax(budgetLeft, spotsLeft);
    if (ceiling <= 0) return [0, 0];
    if (ownsElite && listed >= STAR) return [stay, stretch];
    const factor = factorFor(listed, room);
    if (Math.abs(factor - 1) < 0.03) return [stay, stretch];
    const roomStay = Math.min(ceiling, Math.max(1, Math.round(stay * factor)));
    const roomStretch = Math.min(ceiling, Math.max(roomStay, Math.round(stretch * factor)));
    return [roomStay, roomStretch];
  }

  function eligible(positions, label) {
    if (label === "BN") return true;
    return String(positions || "")
      .split("/")
      .map((part) => part.trim().toUpperCase())
      .includes(label);
  }

  function firstOpenSlot(positions, filled) {
    for (const [id, label] of SLOTS) {
      if (filled.has(id)) continue;
      if (eligible(positions, label)) return id;
    }
    throw new Error("This roster has no open slot for that player.");
  }

  function parseFeed(line) {
    const tokens = String(line || "")
      .trim()
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean);
    if (!tokens.length) throw new Error("Type a name.");
    let action = "lookup";
    let amount = null;
    const names = [];
    for (const token of tokens) {
      const cleaned = token.replace(/,$/, "");
      if (["sold", "gone", "taken"].includes(cleaned)) {
        action = "sold";
        continue;
      }
      if (["me", "mine", "got", "you"].includes(cleaned)) {
        action = "me";
        continue;
      }
      if (["keep", "dynasty"].includes(cleaned)) {
        action = "keep";
        continue;
      }
      if (cleaned === "locked") {
        action = "locked";
        continue;
      }
      if (cleaned.startsWith("$") && /^\d+$/.test(cleaned.slice(1))) {
        amount = Number(cleaned.slice(1));
        continue;
      }
      if (/^\d+$/.test(cleaned)) {
        amount = Number(cleaned);
        continue;
      }
      names.push(cleaned);
    }
    if (!names.length) throw new Error("Type the player name first.");
    const query = names.join(" ");
    return { query: ALIASES[query] || query, amount, action };
  }

  function matchPlayer(query, players) {
    const needle = nameKey(ALIASES[query] || query);
    if (!needle) throw new Error("Type a player name.");
    const scored = [];
    for (const player of players) {
      const key = nameKey(player.player_name);
      const last = key.split(" ").pop();
      if (key === needle || last === needle) return player;
      if (key.startsWith(needle) || key.includes(needle)) scored.push([key.startsWith(needle) ? 0 : 1, player]);
      else if (needle.split(" ").every((part) => key.includes(part))) scored.push([2, player]);
    }
    if (!scored.length) throw new Error(`No player matches ${query}.`);
    scored.sort((a, b) => a[0] - b[0] || (b[1].auction_value || 0) - (a[1].auction_value || 0));
    return scored[0][1];
  }

  function nextTargets(available, budgetLeft, spotsLeft, ownsElite, skip, room) {
    const chosen = [];
    for (const player of available) {
      if (player.player_name === skip) continue;
      const listed = (player.yahoo_listed || player.auction_value || 1) | 0;
      if (ownsElite && listed >= ELITE) continue;
      let stay = stayPrice(listed, budgetLeft, spotsLeft, ownsElite, player);
      let stretch = stretchPrice(listed, budgetLeft, spotsLeft, ownsElite, player);
      [stay, stretch] = applyRoom(stay, stretch, listed, budgetLeft, spotsLeft, ownsElite, room);
      if (stay <= 0) continue;
      const [low, high] = typicalSale(listed);
      chosen.push({ player_name: player.player_name, listed, stay, typical_low: low, typical_high: high });
      if (chosen.length === 3) break;
    }
    return chosen;
  }

  function buildCard(player, bid, budgetLeft, spotsLeft, ownsElite, available, room) {
    const listed = (player.yahoo_listed || player.auction_value || 1) | 0;
    const fairStay = stayPrice(listed, budgetLeft, spotsLeft, ownsElite, player);
    const fairStretch = stretchPrice(listed, budgetLeft, spotsLeft, ownsElite, player);
    const [stay, stretch] = applyRoom(fairStay, fairStretch, listed, budgetLeft, spotsLeft, ownsElite, room);
    const factor = factorFor(listed, room);
    const low = (player.typical_low || typicalSale(listed)[0]) | 0;
    const high = (player.typical_high || typicalSale(listed)[1]) | 0;
    const signal = callFor(bid, stay, stretch);
    const price = bid == null ? stay : bid | 0;
    const tax = Math.max(0, price - stay);
    const after = Math.max(0, budgetLeft - price);
    const seats = Math.max(0, spotsLeft - 1);
    const ownsAfter = ownsElite || listed >= ELITE;
    const targets = nextTargets(available, after, seats, ownsAfter, player.player_name, room);
    const second = ownsElite && listed >= ELITE;
    let roomNote = "";
    if (room && Math.abs(factor - 1) >= 0.03 && !second) {
      roomNote = ` Fair Stay $${fairStay}. This room is at $${stay} (${factor.toFixed(2)}× on this tier).`;
    }
    let why;
    if (spotsLeft <= 0) why = "Your roster is full. Log the sale if someone else got him.";
    else if (second) why = `You already have a $${ELITE}+ player. Stay is $${stay} only if he is a steal. Market on this name is $${low}–$${high}. A second star wrecks the bench.`;
    else if (signal === "ready") why = `Yahoo lists $${listed}. Rooms pay $${low}–$${high}. Stay $${stay}. Stretch $${stretch}. Past that is a tax on the last seats.${roomNote}`;
    else if (signal === "stay") why = `Pay this. After $${price} you have $${after} for ${seats} seats.${roomNote}`;
    else if (signal === "stretch") why = `$${tax} over stay. You can, then $${after} for ${seats} seats. The next $${ELITE}+ name is a pass.${roomNote}`;
    else why = `Pass. Tax $${tax} on a $${listed} name. If you still pay $${price} you have $${after} for ${seats} seats and you are in stars-and-scrubs.${roomNote}`;
    if (targets.length && signal !== "pass") {
      why += ` Next: ${targets.slice(0, 2).map((item) => `${item.player_name} stay $${item.stay}`).join(", ")}.`;
    }
    return {
      player_name: player.player_name,
      positions: player.positions || "",
      listed,
      bid,
      stay,
      stretch,
      fair_stay: fairStay,
      fair_stretch: fairStretch,
      room_factor: Math.round(factor * 1000) / 1000,
      typical_low: low,
      typical_high: high,
      call: signal,
      tax,
      after,
      seats_after: seats,
      second_star: second,
      why,
      next: targets,
    };
  }

  class Sidecar {
    constructor(players, teamCount, budget) {
      this.players = Object.fromEntries(players.map((player) => [player.player_name, { ...player }]));
      this.team_count = teamCount;
      this.budget = budget;
      this.budget_left = budget;
      this.picks = [];
      this.taken = [];
      this.focus = null;
      this.queue = [];
    }

    spotsLeft() {
      return ROSTER_SIZE - this.picks.length;
    }

    ownsElite() {
      return this.picks.some((pick) => (pick.auction_value || 0) >= ELITE);
    }

    available() {
      const gone = new Set(this.taken.map((item) => item.player_name));
      return Object.values(this.players)
        .filter((player) => !gone.has(player.player_name))
        .sort((a, b) => (b.auction_value || 0) - (a.auction_value || 0) || (b.total_value || -999) - (a.total_value || -999));
    }

    room() {
      return readRoom(this.taken, this.team_count, this.budget);
    }

    pick(query, amount) {
      this.feed([query, amount != null ? String(amount) : ""].filter(Boolean).join(" "));
    }

    feed(line) {
      const command = parseFeed(line);
      const search = this.available().concat(this.taken.map((item) => item.player).filter(Boolean));
      const player = matchPlayer(command.query, search);
      const name = player.player_name;
      const already = this.taken.find((item) => item.player_name === name);
      if (already && command.action === "lookup") {
        this.focus = { player_name: name, bid: already.price };
        return;
      }
      if (already) throw new Error(`${name} is already logged at $${already.price}.`);
      this.focus = { player_name: name, bid: command.amount };
      if (command.action === "lookup") return;
      this.close(command.action, command.amount);
    }

    closePrice(amount) {
      if (!this.focus) throw new Error("Pick a name first.");
      const player = this.players[this.focus.player_name];
      if (amount != null) return Math.max(1, amount | 0);
      if (this.focus.bid != null) return Math.max(1, this.focus.bid | 0);
      const listed = (player.yahoo_listed || player.auction_value || 1) | 0;
      return stayPrice(listed, this.budget_left, this.spotsLeft(), this.ownsElite(), player);
    }

    close(action, amount) {
      if (!["sold", "me", "keep", "locked"].includes(action)) throw new Error("Tap Sold, Me, Keep, or Locked.");
      if (!this.focus) throw new Error("Pick a name first.");
      const name = this.focus.player_name;
      if (this.taken.find((item) => item.player_name === name)) throw new Error(`${name} is already logged.`);
      const player = this.players[name];
      const listed = (player.yahoo_listed || player.auction_value || 1) | 0;
      const dynasty = action === "keep" || action === "locked";
      if (dynasty && player.superstar) throw new Error("Pilsner superstars cannot be dynasty. Log Sold or Me.");
      const price = dynasty ? listed : this.closePrice(amount);
      const [stay, stretch] = fairMarks(player, listed, this.budget);
      const stamp = {
        player_name: name,
        player: { ...player },
        price,
        auction_value: (player.auction_value || 1) | 0,
        listed,
        fair_stay: stay,
        fair_stretch: stretch,
        yours: action === "me" || action === "keep",
        kind: dynasty ? "dynasty" : "sale",
      };
      if (stamp.yours) {
        if (this.spotsLeft() <= 0) throw new Error("Your ten seats are full.");
        const ceiling = leftoverMax(this.budget_left, this.spotsLeft());
        if (price > ceiling) throw new Error(`That leaves empty seats unpaid. Most you can log is $${ceiling}.`);
        const filled = new Set(this.picks.map((pick) => pick.slot_id));
        let slotId;
        try {
          slotId = firstOpenSlot(player.positions, filled);
        } catch {
          slotId = SLOTS.find(([id]) => !filled.has(id))[0];
        }
        stamp.slot_id = slotId;
        stamp.slot_label = Object.fromEntries(SLOTS)[slotId];
        this.picks.push(stamp);
        this.taken.push(stamp);
        this.budget_left -= price;
      } else {
        this.taken.push(stamp);
      }
      this.focus = null;
    }

    undo() {
      if (this.focus) {
        this.focus = null;
        return;
      }
      if (!this.taken.length) throw new Error("Nothing to undo.");
      const last = this.taken.pop();
      if (last.yours) {
        this.picks = this.picks.filter((pick) => pick.player_name !== last.player_name);
        this.budget_left += last.price | 0;
      }
    }

    state() {
      const room = this.room();
      let coach = null;
      if (this.focus && this.players[this.focus.player_name]) {
        coach = buildCard(
          this.players[this.focus.player_name],
          this.focus.bid,
          this.budget_left,
          this.spotsLeft(),
          this.ownsElite(),
          this.available(),
          room,
        );
      }
      const filed = Object.fromEntries(this.picks.map((pick) => [pick.slot_id, pick]));
      const slots = SLOTS.map(([id, label]) => {
        const pick = filed[id];
        return {
          id,
          label,
          player: pick
            ? { player_name: pick.player_name, positions: pick.player?.positions || pick.slot_label, price: pick.price }
            : null,
        };
      });
      return {
        started: true,
        mode: "live",
        complete: this.picks.length >= ROSTER_SIZE,
        categories: CATEGORIES,
        filters: FILTERS,
        budget: this.budget,
        budget_left: this.budget_left,
        spots_left: this.spotsLeft(),
        coach,
        room,
        available: this.available(),
        rosters: [{ name: "You", is_you: true, budget: this.budget_left, slots }],
        log: this.taken.map((item, index) => ({
          pick_number: index + 1,
          team: item.yours ? "You" : item.kind === "dynasty" ? "Locked" : "Room",
          player_name: item.player_name,
          slot_label: item.slot_label || "—",
          price: item.price,
        })),
      };
    }

    dump() {
      return {
        team_count: this.team_count,
        budget: this.budget,
        budget_left: this.budget_left,
        picks: this.picks,
        taken: this.taken,
        focus: this.focus,
      };
    }

    static load(payload, players) {
      const session = new Sidecar(players, payload.team_count, payload.budget);
      session.budget_left = payload.budget_left ?? payload.budget;
      session.picks = payload.picks || [];
      session.taken = payload.taken || [];
      session.focus = payload.focus || null;
      return session;
    }
  }

  function idleHelper() {
    return { started: false, categories: CATEGORIES, team_count: TEAM_COUNT, budget: DEFAULT_BUDGET };
  }

  function saveHelper() {
    if (!helper) {
      localStorage.removeItem("pilsner-helper");
      return;
    }
    localStorage.setItem("pilsner-helper", JSON.stringify(helper.dump()));
  }

  function restoreHelper() {
    const raw = localStorage.getItem("pilsner-helper");
    if (!raw) return;
    try {
      helper = Sidecar.load(JSON.parse(raw), pool);
    } catch {
      helper = null;
    }
  }

  function helperApi(path, body) {
    const route = path.split("/helper/api/")[1] || path;
    if (route === "state") return helper ? helper.state() : idleHelper();
    if (route === "start") {
      const budget = (body.budget ?? DEFAULT_BUDGET) | 0;
      const teams = (body.team_count ?? TEAM_COUNT) | 0;
      if (budget < MIN_BUDGET || budget > MAX_BUDGET) throw new Error("Draft dollars are $160–$240. That number is your cap, not a payment.");
      helper = new Sidecar(pool, teams, budget);
      saveHelper();
      return helper.state();
    }
    if (!helper) return idleHelper();
    if (route === "pick") helper.pick(body.player_name, body.amount);
    else if (route === "feed") helper.feed(body.line);
    else if (route === "close") helper.close(String(body.action || ""), body.amount);
    else if (route === "undo") helper.undo();
    else if (route === "reset") {
      helper = null;
      saveHelper();
      return idleHelper();
    } else throw new Error("Unknown helper action.");
    saveHelper();
    return helper.state();
  }

  async function load() {
    const response = await fetch("data/pool.json");
    const payload = await response.json();
    pool = payload.players || payload;
    restoreHelper();
    return pool;
  }

  return {
    CATEGORIES,
    SLOTS,
    FILTERS,
    ROSTER_SIZE,
    DEFAULT_BUDGET,
    TEAM_COUNT,
    ALIASES,
    leftoverMax,
    typicalSale,
    stayPrice,
    stretchPrice,
    capBid,
    recommendedStay,
    buildCard,
    matchPlayer,
    firstOpenSlot,
    eligible,
    load,
    pool: () => pool,
    helperApi,
    idleHelper,
  };
})();
