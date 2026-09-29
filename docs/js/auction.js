const NBADraft = (() => {
  const NOMINATE_SECONDS = 30;
  const BID_SECONDS = 20;
  const BID_RESET = 10;
  const COMPUTER_CAP = 1.12;
  const ELITE = 40;
  const SECOND_STAR = 0.5;
  const MAX_SHARE = 0.38;
  const MARKET_FLOOR = 0.82;
  const ROUNDS = 10;

  let session = null;

  function now() {
    return Date.now();
  }

  class DraftSession {
    constructor(players, teamCount, draftSlot, budget) {
      this.players = Object.fromEntries(players.map((player) => [player.player_name, { ...player }]));
      this.team_count = teamCount;
      this.draft_slot = draftSlot;
      this.budget = budget;
      this.total_picks = teamCount * ROUNDS;
      this.picks = [];
      this.queue = [];
      this.budgets = Array(teamCount).fill(budget);
      this.on_block = null;
      this.phase = "nominate";
      this.clock_ends = now() + NOMINATE_SECONDS * 1000;
      this.styles = Array.from({ length: teamCount }, (_, index) => 0.9 + Math.min(0.22, index * 0.015));
    }

    get your_team() {
      return this.draft_slot - 1;
    }

    teamName(index) {
      return index === this.your_team ? "You" : `Team ${index + 1}`;
    }

    nominator() {
      if (this.on_block || this.picks.length >= this.total_picks) return null;
      return this.picks.length % this.team_count;
    }

    spotsLeft(index) {
      return NBA.ROSTER_SIZE - this.picks.filter((pick) => pick.team_index === index).length;
    }

    filled(index) {
      return new Set(this.picks.filter((pick) => pick.team_index === index).map((pick) => pick.slot_id));
    }

    available() {
      const taken = new Set(this.picks.map((pick) => pick.player_name));
      if (this.on_block) taken.add(this.on_block.player_name);
      return Object.values(this.players)
        .filter((player) => !taken.has(player.player_name))
        .sort((a, b) => (b.auction_value || 0) - (a.auction_value || 0) || (b.total_value || -999) - (a.total_value || -999));
    }

    maxOffer(index) {
      return NBA.leftoverMax(this.budgets[index], this.spotsLeft(index));
    }

    yourMax(player) {
      return NBA.recommendedStay((player.auction_value || 1) | 0, this.maxOffer(this.your_team));
    }

    ownsElite(index) {
      return this.picks.some((pick) => pick.team_index === index && (pick.auction_value || 0) >= ELITE);
    }

    botMax(index, player) {
      if (index === this.your_team || this.spotsLeft(index) <= 0) return 0;
      const listed = (player.auction_value || 1) | 0;
      const style = Math.min(COMPUTER_CAP, this.styles[index]);
      let priced;
      if (listed >= ELITE && this.ownsElite(index)) priced = Math.round(listed * SECOND_STAR);
      else {
        priced = Math.round(listed * style);
        if (listed >= 12) priced = Math.max(priced, Math.round(listed * MARKET_FLOOR));
      }
      priced = Math.min(priced, Math.round(this.budget * MAX_SHARE));
      return NBA.capBid(Math.max(1, priced), this.budgets[index], this.spotsLeft(index));
    }

    secondsLeft() {
      return Math.max(0, Math.floor((this.clock_ends - now()) / 1000));
    }

    waitingOnYou() {
      if (this.picks.length >= this.total_picks) return false;
      if (this.phase === "bid") return true;
      return this.nominator() === this.your_team;
    }

    nominate(playerName, opening, teamIndex) {
      if (this.on_block) throw new Error("A player is already on the block.");
      const nominator = this.nominator();
      if (nominator == null) throw new Error("The draft is complete.");
      const actor = teamIndex == null ? this.your_team : teamIndex;
      if (actor !== nominator) throw new Error("It is not your turn to nominate.");
      const player = this.players[playerName];
      if (!player) throw new Error(`No available player named ${playerName}.`);
      let bid = Math.max(1, opening | 0);
      if (bid > this.maxOffer(nominator)) bid = this.maxOffer(nominator);
      this.on_block = { player_name: playerName, nominator, bid, high_bidder: nominator };
      this.phase = "bid";
      this.clock_ends = now() + BID_SECONDS * 1000;
    }

    bid(amount, teamIndex) {
      if (!this.on_block || this.phase !== "bid") throw new Error("No player is on the block.");
      const actor = teamIndex == null ? this.your_team : teamIndex;
      const offer = amount | 0;
      const current = this.on_block.bid | 0;
      if (offer <= current) throw new Error(`The offer has to be more than $${current}.`);
      const ceiling = this.maxOffer(actor);
      if (offer > ceiling) throw new Error(`You have to leave $1 for every empty seat. The most you can offer is $${ceiling}.`);
      this.on_block.bid = offer;
      this.on_block.high_bidder = actor;
      if (this.clock_ends - now() < BID_RESET * 1000) this.clock_ends = now() + BID_RESET * 1000;
    }

    tick() {
      if (this.picks.length >= this.total_picks) {
        this.phase = "done";
        return;
      }
      if (this.phase === "bid" && this.on_block) {
        if (now() >= this.clock_ends) {
          this.catchUp();
          this.sell();
          return;
        }
        for (let i = 0; i < 3; i += 1) {
          const bidder = this.nextBot();
          if (bidder == null) break;
          this.botRaise(bidder);
        }
        return;
      }
      const nominator = this.nominator();
      if (nominator == null) return;
      if (nominator !== this.your_team) {
        try {
          this.autoNominate(nominator);
        } catch {
          return;
        }
        return;
      }
      if (now() >= this.clock_ends) {
        try {
          this.autoNominate(nominator);
        } catch {
          return;
        }
      }
    }

    autoNominate(index) {
      const available = this.available();
      if (!available.length) return;
      const names = new Set(available.map((player) => player.player_name));
      let name = this.queue.find((queued) => names.has(queued));
      if (!name && this.ownsElite(index)) name = available[0].player_name;
      else if (!name) {
        const affordable = available.filter((player) => this.botMax(index, player) >= Math.round((player.auction_value || 1) * MARKET_FLOOR));
        name = (affordable[0] || available[0]).player_name;
      }
      if (index === this.your_team) this.queue = this.queue.filter((item) => item !== name);
      this.nominate(name, 1, index);
    }

    botRaise(index) {
      const player = this.players[this.on_block.player_name];
      const current = this.on_block.bid | 0;
      const ceiling = this.botMax(index, player);
      if (ceiling <= current) return;
      const gap = ceiling - current;
      const step = gap <= 2 ? 1 : Math.min(5, Math.max(2, Math.floor(gap / 5)));
      try {
        this.bid(Math.min(current + step, ceiling), index);
      } catch {
        return;
      }
    }

    catchUp() {
      for (let i = 0; i < 400; i += 1) {
        const bidder = this.nextBot();
        if (bidder == null) return;
        this.botRaise(bidder);
      }
    }

    nextBot() {
      if (!this.on_block) return null;
      const player = this.players[this.on_block.player_name];
      const current = this.on_block.bid | 0;
      const high = this.on_block.high_bidder | 0;
      const hopefuls = [];
      for (let index = 0; index < this.team_count; index += 1) {
        if (index === this.your_team || index === high) continue;
        if (this.botMax(index, player) > current) hopefuls.push(index);
      }
      if (!hopefuls.length) return null;
      return hopefuls[this.picks.length % hopefuls.length];
    }

    sell() {
      if (!this.on_block) return;
      const player = this.players[this.on_block.player_name];
      const teamIndex = this.on_block.high_bidder | 0;
      const price = this.on_block.bid | 0;
      const filled = this.filled(teamIndex);
      let slotId;
      try {
        slotId = NBA.firstOpenSlot(player.positions, filled);
      } catch {
        slotId = NBA.SLOTS.find(([id]) => !filled.has(id))[0];
      }
      const labels = Object.fromEntries(NBA.SLOTS);
      this.picks.push({
        pick_number: this.picks.length + 1,
        team_index: teamIndex,
        team: this.teamName(teamIndex),
        player_name: player.player_name,
        player: { ...player },
        slot_id: slotId,
        slot_label: labels[slotId],
        price,
        auction_value: (player.auction_value || 1) | 0,
      });
      this.budgets[teamIndex] -= price;
      delete this.players[player.player_name];
      this.queue = this.queue.filter((name) => name !== player.player_name);
      this.on_block = null;
      this.phase = "nominate";
      this.clock_ends = now() + NOMINATE_SECONDS * 1000;
    }

    undo() {
      if (this.on_block) {
        this.on_block = null;
        this.phase = "nominate";
        this.clock_ends = now() + NOMINATE_SECONDS * 1000;
        return;
      }
      if (!this.picks.length) throw new Error("Nothing to undo.");
      const last = this.picks.pop();
      this.budgets[last.team_index] += last.price;
      const player = last.player || { player_name: last.player_name };
      this.players[player.player_name] = player;
      this.phase = "nominate";
      this.clock_ends = now() + NOMINATE_SECONDS * 1000;
    }

    queueAdd(name) {
      if (!this.players[name] && (!this.on_block || this.on_block.player_name !== name)) throw new Error(`No available player named ${name}.`);
      if (!this.queue.includes(name)) this.queue.push(name);
    }

    queueRemove(name) {
      this.queue = this.queue.filter((item) => item !== name);
    }

    suggestion() {
      if (this.picks.length >= this.total_picks) return { mode: "done", options: [], paragraph: "The auction is over." };
      if (this.phase === "bid" && this.on_block) return this.bidAdvice();
      if (this.nominator() === this.your_team) return this.nominateAdvice();
      const who = this.nominator() != null ? this.teamName(this.nominator()) : "Another manager";
      return {
        mode: "wait",
        options: [],
        paragraph: `${who} has 30 seconds to nominate. The name comes up at $1. Then everyone has 20 seconds to raise.`,
      };
    }

    nominateAdvice() {
      const available = this.available();
      if (!available.length) return { mode: "nominate", options: [], paragraph: "The board is empty." };
      const first = available[0];
      const second = available[1] || available[0];
      const [firstLow, firstHigh] = NBA.typicalSale(first.auction_value | 0);
      const [secondLow, secondHigh] = NBA.typicalSale(second.auction_value | 0);
      return {
        mode: "nominate",
        player_name: first.player_name,
        options: [
          { ...first, action: "nominate", percent: 62, bid: 1, max_bid: this.yourMax(first), typical_low: firstLow, typical_high: firstHigh, label: "Nominate" },
          { ...second, action: "nominate", percent: 38, bid: 1, max_bid: this.yourMax(second), typical_low: secondLow, typical_high: secondHigh, label: "Nominate" },
        ],
        paragraph: `You have ${this.secondsLeft()} seconds to name a player at $1. ${first.player_name} is listed at $${first.auction_value}. Stay in until $${this.yourMax(first)} if you want him.`,
      };
    }

    bidAdvice() {
      const player = this.players[this.on_block.player_name];
      const current = this.on_block.bid | 0;
      const nxt = current + 1;
      const ceiling = Math.min(this.yourMax(player), this.maxOffer(this.your_team));
      const high = this.teamName(this.on_block.high_bidder | 0);
      const [low, highSale] = NBA.typicalSale(player.auction_value | 0);
      return {
        mode: "bid",
        player_name: player.player_name,
        options: [
          { ...player, action: "bid", percent: 70, bid: nxt, max_bid: ceiling, typical_low: low, typical_high: highSale, label: `Offer $${nxt}` },
          { ...player, action: "hold", percent: 30, bid: current, max_bid: ceiling, typical_low: low, typical_high: highSale, label: "Hold" },
        ],
        paragraph: `${player.player_name} is at $${current}. ${high} has the offer. Listed $${player.auction_value}; usual sale $${low}–$${highSale}. Stay in until $${ceiling}.`,
      };
    }

    roster(index) {
      const filed = Object.fromEntries(this.picks.filter((pick) => pick.team_index === index).map((pick) => [pick.slot_id, pick]));
      return {
        name: this.teamName(index),
        is_you: index === this.your_team,
        budget: this.budgets[index],
        slots: NBA.SLOTS.map(([id, label]) => {
          const pick = filed[id];
          return {
            id,
            label,
            player: pick ? { player_name: pick.player_name, positions: pick.player?.positions || pick.slot_label, price: pick.price } : null,
          };
        }),
      };
    }

    state() {
      const complete = this.picks.length >= this.total_picks;
      const nom = this.nominator();
      let block = null;
      if (this.on_block) {
        const player = this.players[this.on_block.player_name];
        const [low, high] = NBA.typicalSale((player.auction_value || 1) | 0);
        block = {
          ...player,
          nominator: this.teamName(this.on_block.nominator),
          bid: this.on_block.bid,
          high_bidder: this.teamName(this.on_block.high_bidder),
          your_high: this.on_block.high_bidder === this.your_team,
          next_bid: (this.on_block.bid | 0) + 1,
          your_max: this.yourMax(player),
          max_offer: this.maxOffer(this.your_team),
          typical_low: low,
          typical_high: high,
        };
      }
      let coach = null;
      if (this.on_block) {
        const player = this.players[this.on_block.player_name];
        coach = NBA.buildCard(player, this.on_block.bid | 0, this.budgets[this.your_team], this.spotsLeft(this.your_team), this.ownsElite(this.your_team), this.available());
      }
      return {
        started: true,
        mode: "mock",
        complete,
        phase: complete ? "done" : this.phase,
        categories: NBA.CATEGORIES,
        filters: NBA.FILTERS,
        can_nominate: !complete && this.phase === "nominate" && this.nominator() === this.your_team,
        your_turn: !complete && this.waitingOnYou(),
        nomination_slot: this.draft_slot,
        on_clock: complete ? null : block ? block.high_bidder : nom != null ? this.teamName(nom) : "",
        budget: this.budget,
        budget_left: this.budgets[this.your_team],
        spots_left: this.spotsLeft(this.your_team),
        seconds_left: complete ? 0 : this.secondsLeft(),
        on_block: block,
        coach,
        suggestion: this.suggestion(),
        available: this.available(),
        rosters: Array.from({ length: this.team_count }, (_, index) => this.roster(index)),
        queue: this.queue.map((name) => this.players[name]).filter(Boolean),
        log: this.picks.map((pick) => ({
          pick_number: pick.pick_number,
          team: pick.team,
          player_name: pick.player_name,
          slot_label: pick.slot_label,
          price: pick.price,
        })),
        guide: "Yahoo salary cap: nominate in a circle. 30 seconds to name a player at $1. 20 seconds to raise. A bid in the last 10 puts 10 seconds back. Leave $1 per empty seat.",
        team_count: this.team_count,
      };
    }
  }

  function idle() {
    return { started: false, categories: NBA.CATEGORIES, team_count: NBA.TEAM_COUNT, budget: NBA.DEFAULT_BUDGET };
  }

  function save() {
    if (!session) {
      localStorage.removeItem("nba-fantasy-draft");
      return;
    }
    localStorage.setItem(
      "nba-fantasy-draft",
      JSON.stringify({
        team_count: session.team_count,
        draft_slot: session.draft_slot,
        budget: session.budget,
        picks: session.picks,
        queue: session.queue,
        budgets: session.budgets,
        on_block: session.on_block,
        phase: session.phase,
        clock_ends: session.clock_ends,
        remaining: Object.values(session.players),
      }),
    );
  }

  function restore() {
    const raw = localStorage.getItem("nba-fantasy-draft");
    if (!raw) return;
    try {
      const payload = JSON.parse(raw);
      session = new DraftSession(NBA.pool(), payload.team_count, payload.draft_slot, payload.budget);
      session.picks = payload.picks || [];
      session.queue = payload.queue || [];
      session.budgets = payload.budgets || session.budgets;
      session.on_block = payload.on_block || null;
      session.phase = payload.phase || "nominate";
      session.clock_ends = payload.clock_ends || session.clock_ends;
      const taken = new Set(session.picks.map((pick) => pick.player_name));
      session.players = Object.fromEntries(NBA.pool().filter((player) => !taken.has(player.player_name)).map((player) => [player.player_name, { ...player }]));
      if (session.on_block && !session.players[session.on_block.player_name]) {
        const found = NBA.pool().find((player) => player.player_name === session.on_block.player_name);
        if (found) session.players[found.player_name] = { ...found };
      }
    } catch {
      session = null;
    }
  }

  function api(path, body) {
    const route = path.split("/draft/api/")[1] || path;
    if (route === "state") {
      if (!session) {
        restore();
        if (!session) return idle();
      }
      return session.state();
    }
    if (route === "start") {
      const teams = (body.team_count || 16) | 0;
      const slot = (body.draft_slot || 1) | 0;
      const budget = (body.budget || 200) | 0;
      if (teams < 2) throw new Error("A draft needs at least two teams.");
      if (slot < 1 || slot > teams) throw new Error(`Your nomination order must be between 1 and ${teams}.`);
      session = new DraftSession(NBA.pool(), teams, slot, budget);
      save();
      return session.state();
    }
    if (!session) return idle();
    if (route === "nominate") session.nominate(body.player_name, body.opening || 1);
    else if (route === "bid") session.bid(body.amount);
    else if (route === "tick") session.tick();
    else if (route === "undo") session.undo();
    else if (route === "queue") {
      if (body.action === "remove") session.queueRemove(body.player_name);
      else session.queueAdd(body.player_name);
    } else if (route === "reset") {
      session = null;
      save();
      return idle();
    } else throw new Error("Unknown draft action.");
    save();
    return session.state();
  }

  return { api, restore, idle };
})();
