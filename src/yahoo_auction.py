"""Yahoo live salary-cap draft: circular nominations, rising bids, 30s / 20s clocks."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from auction import assign_auction_values, cap_bid, recommended_stay, typical_sale
from coach import build_card
from draft_room import (
    DEFAULT_BUDGET,
    FILTERS,
    ROSTER_SIZE,
    ROUNDS,
    SESSION_PATH,
    SLOTS,
    TEAM_COUNT,
    first_open_slot,
)
from math_engine import ALL_CATEGORIES

NOMINATE_SECONDS = 30
BID_SECONDS = 20
BID_RESET_SECONDS = 10
COMPUTER_VALUE_CAP = 1.12
ELITE_LISTED = 40
SECOND_STAR_FACTOR = 0.50
MAX_BUDGET_SHARE = 0.38
MARKET_FLOOR = 0.82


class DraftSession:
    def __init__(
        self,
        players: list[dict],
        team_count: int = TEAM_COUNT,
        draft_slot: int = 1,
        punts: list[str] | None = None,
        budget: int = DEFAULT_BUDGET,
        rounds: int = ROUNDS,
    ) -> None:
        if team_count < 2:
            raise ValueError("A draft needs at least two teams.")
        if not 1 <= draft_slot <= team_count:
            raise ValueError(f"Your nomination order must be between 1 and {team_count}.")
        if any(player.get("auction_value") is None for player in players):
            assign_auction_values(players, team_count, len(SLOTS), budget)
        self.players = {player["player_name"]: dict(player) for player in players}
        self.team_count = team_count
        self.draft_slot = draft_slot
        self.punts = list(punts or [])
        self.budget = budget
        self.total_picks = team_count * rounds
        self.picks: list[dict] = []
        self.queue: list[str] = []
        self.clock_started = datetime.now(timezone.utc)
        self.budgets = [budget] * team_count
        self.on_block: dict | None = None
        self.phase = "nominate"
        self.clock_ends = self.clock_started + timedelta(seconds=NOMINATE_SECONDS)
        self.styles = [0.90 + min(0.22, index * 0.015) for index in range(team_count)]

    @property
    def your_team(self) -> int:
        return self.draft_slot - 1

    def team_name(self, team_index: int) -> str:
        if team_index == self.your_team:
            return "You"
        return f"Team {team_index + 1}"

    def nominator(self) -> int | None:
        if self.on_block or len(self.picks) >= self.total_picks:
            return None
        return len(self.picks) % self.team_count

    def spots_left(self, team_index: int) -> int:
        return ROSTER_SIZE - sum(1 for pick in self.picks if pick["team_index"] == team_index)

    def filled_slots(self, team_index: int) -> set[str]:
        return {pick["slot_id"] for pick in self.picks if pick["team_index"] == team_index}

    def available_players(self) -> list[dict]:
        taken = {pick["player_name"] for pick in self.picks}
        if self.on_block:
            taken.add(self.on_block["player_name"])
        return [
            player
            for player in sorted(
                self.players.values(),
                key=lambda item: (-item["auction_value"], -(item["total_value"] or -999)),
            )
            if player["player_name"] not in taken
        ]

    def max_offer(self, team_index: int) -> int:
        spots = self.spots_left(team_index)
        if spots <= 0:
            return 0
        return max(0, self.budgets[team_index] - (spots - 1))

    def your_max(self, player: dict) -> int:
        listed = int(player.get("auction_value") or 1)
        leftover = self.max_offer(self.your_team)
        return recommended_stay(listed, leftover)

    def _owns_elite(self, team_index: int) -> bool:
        return any(int(pick.get("auction_value") or 0) >= ELITE_LISTED for pick in self.picks if pick["team_index"] == team_index)

    def bot_max(self, team_index: int, player: dict) -> int:
        if team_index == self.your_team or self.spots_left(team_index) <= 0:
            return 0
        listed = int(player.get("auction_value") or 1)
        style = min(COMPUTER_VALUE_CAP, self.styles[team_index])
        if listed >= ELITE_LISTED and self._owns_elite(team_index):
            priced = int(round(listed * SECOND_STAR_FACTOR))
        else:
            priced = int(round(listed * style))
            if listed >= 12:
                priced = max(priced, int(round(listed * MARKET_FLOOR)))
        priced = min(priced, int(self.budget * MAX_BUDGET_SHARE))
        return cap_bid(max(1, priced), self.budgets[team_index], self.spots_left(team_index))

    def seconds_left(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        return max(0, int((self.clock_ends - now).total_seconds()))

    def waiting_on_you(self) -> bool:
        if len(self.picks) >= self.total_picks:
            return False
        if self.phase == "bid":
            return True
        return self.nominator() == self.your_team

    def nominate(self, player_name: str, opening: int = 1, team_index: int | None = None) -> None:
        if self.on_block:
            raise ValueError("A player is already on the block.")
        nominator = self.nominator()
        if nominator is None:
            raise ValueError("The draft is complete.")
        actor = self.your_team if team_index is None else team_index
        if actor != nominator:
            raise ValueError("It is not your turn to nominate.")
        player = self.players.get(player_name)
        if player is None:
            raise ValueError(f"No available player named {player_name}.")
        bid = max(1, int(opening))
        if bid > self.max_offer(nominator):
            bid = self.max_offer(nominator)
        now = datetime.now(timezone.utc)
        self.on_block = {
            "player_name": player_name,
            "nominator": nominator,
            "bid": bid,
            "high_bidder": nominator,
        }
        self.phase = "bid"
        self.clock_ends = now + timedelta(seconds=BID_SECONDS)

    def bid(self, amount: int, team_index: int | None = None) -> None:
        if not self.on_block or self.phase != "bid":
            raise ValueError("No player is on the block.")
        actor = self.your_team if team_index is None else team_index
        offer = int(amount)
        current = int(self.on_block["bid"])
        if offer <= current:
            raise ValueError(f"The offer has to be more than ${current}.")
        ceiling = self.max_offer(actor)
        if offer > ceiling:
            raise ValueError(f"You have to leave $1 for every empty seat. The most you can offer is ${ceiling}.")
        now = datetime.now(timezone.utc)
        self.on_block["bid"] = offer
        self.on_block["high_bidder"] = actor
        if (self.clock_ends - now).total_seconds() < BID_RESET_SECONDS:
            self.clock_ends = now + timedelta(seconds=BID_RESET_SECONDS)

    def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        if len(self.picks) >= self.total_picks:
            self.phase = "done"
            return
        if self.phase == "bid" and self.on_block:
            if now >= self.clock_ends:
                self._catch_up_bots()
                self._sell()
                return
            for _ in range(3):
                bidder = self._next_bot_bidder()
                if bidder is None:
                    break
                self._bot_raise(bidder)
            return
        nominator = self.nominator()
        if nominator is None:
            return
        if nominator != self.your_team:
            try:
                self._auto_nominate(nominator)
            except ValueError:
                return
            return
        if now >= self.clock_ends:
            try:
                self._auto_nominate(nominator)
            except ValueError:
                return

    def step(self) -> None:
        self.tick()

    def _auto_nominate(self, team_index: int) -> None:
        available = self.available_players()
        if not available:
            return
        names = {player["player_name"] for player in available}
        name = next((queued for queued in self.queue if queued in names), None)
        if name is None and self._owns_elite(team_index):
            name = available[0]["player_name"]
        elif name is None:
            affordable = [
                player
                for player in available
                if self.bot_max(team_index, player) >= int(round(int(player.get("auction_value") or 1) * MARKET_FLOOR))
            ]
            name = (affordable or available)[0]["player_name"]
        if team_index == self.your_team and name in self.queue:
            self.queue.remove(name)
        self.nominate(name, opening=1, team_index=team_index)

    def _bot_raise(self, team_index: int) -> None:
        player = self.players[self.on_block["player_name"]]
        current = int(self.on_block["bid"])
        ceiling = self.bot_max(team_index, player)
        if ceiling <= current:
            return
        gap = ceiling - current
        step = 1 if gap <= 2 else min(5, max(2, gap // 5))
        try:
            self.bid(min(current + step, ceiling), team_index=team_index)
        except ValueError:
            return

    def _catch_up_bots(self) -> None:
        """Computers make every offer they would have made before the gavel."""
        for _ in range(400):
            bidder = self._next_bot_bidder()
            if bidder is None:
                return
            self._bot_raise(bidder)

    def _next_bot_bidder(self) -> int | None:
        if not self.on_block:
            return None
        player = self.players[self.on_block["player_name"]]
        current = int(self.on_block["bid"])
        high = int(self.on_block["high_bidder"])
        hopefuls = []
        for team_index in range(self.team_count):
            if team_index == self.your_team or team_index == high:
                continue
            if self.bot_max(team_index, player) > current:
                hopefuls.append(team_index)
        if not hopefuls:
            return None
        return hopefuls[len(self.picks) % len(hopefuls)]

    def _sell(self) -> None:
        if not self.on_block:
            return
        player = self.players[self.on_block["player_name"]]
        team_index = int(self.on_block["high_bidder"])
        price = int(self.on_block["bid"])
        filled = self.filled_slots(team_index)
        try:
            slot_id = first_open_slot(player["positions"], filled)
        except ValueError:
            slot_id = next(slot for slot, _label in SLOTS if slot not in filled)
        labels = dict(SLOTS)
        self.picks.append(
            {
                "pick_number": len(self.picks) + 1,
                "team_index": team_index,
                "team": self.team_name(team_index),
                "player_name": player["player_name"],
                "player": dict(player),
                "slot_id": slot_id,
                "slot_label": labels[slot_id],
                "price": price,
                "auction_value": int(player.get("auction_value") or 1),
            }
        )
        self.budgets[team_index] -= price
        self.players.pop(player["player_name"], None)
        if player["player_name"] in self.queue:
            self.queue.remove(player["player_name"])
        self.on_block = None
        self.phase = "nominate"
        self.clock_ends = datetime.now(timezone.utc) + timedelta(seconds=NOMINATE_SECONDS)

    def queue_add(self, player_name: str) -> None:
        if player_name not in self.players and (not self.on_block or self.on_block["player_name"] != player_name):
            raise ValueError(f"No available player named {player_name}.")
        if player_name not in self.queue:
            self.queue.append(player_name)

    def queue_remove(self, player_name: str) -> None:
        if player_name in self.queue:
            self.queue.remove(player_name)

    def undo(self) -> None:
        if self.on_block:
            self.on_block = None
            self.phase = "nominate"
            self.clock_ends = datetime.now(timezone.utc) + timedelta(seconds=NOMINATE_SECONDS)
            return
        if not self.picks:
            raise ValueError("Nothing to undo.")
        last = self.picks.pop()
        self.budgets[last["team_index"]] += last["price"]
        player = last.get("player") or {"player_name": last["player_name"]}
        self.players[player["player_name"]] = player
        self.phase = "nominate"
        self.clock_ends = datetime.now(timezone.utc) + timedelta(seconds=NOMINATE_SECONDS)

    def suggestion(self) -> dict:
        if len(self.picks) >= self.total_picks:
            return {"mode": "done", "options": [], "paragraph": "The auction is over. Check the prices you paid against the listed value."}
        if self.phase == "bid" and self.on_block:
            return self._bid_advice()
        if self.nominator() == self.your_team:
            return self._nominate_advice()
        return self._wait_advice()

    def _wait_advice(self) -> dict:
        who = self.team_name(self.nominator()) if self.nominator() is not None else "Another manager"
        return {
            "mode": "wait",
            "options": [],
            "paragraph": (
                f"{who} has 30 seconds to nominate. The name comes up at $1. "
                f"Then everyone has 20 seconds to raise. A bid inside the last 10 seconds puts 10 seconds back on the clock."
            ),
        }

    def _nominate_advice(self) -> dict:
        available = self.available_players()
        if not available:
            return {"mode": "nominate", "options": [], "paragraph": "The board is empty."}
        first, second = available[0], available[1] if len(available) > 1 else available[0]
        first_low, first_high = typical_sale(int(first["auction_value"]))
        second_low, second_high = typical_sale(int(second["auction_value"]))
        options = [
            {**first, "action": "nominate", "percent": 62, "bid": 1, "max_bid": self.your_max(first), "typical_low": first_low, "typical_high": first_high, "label": "Nominate"},
            {**second, "action": "nominate", "percent": 38, "bid": 1, "max_bid": self.your_max(second), "typical_low": second_low, "typical_high": second_high, "label": "Nominate"},
        ]
        paragraph = (
            f"You have {self.seconds_left()} seconds to name a player. That opens the bidding at $1. "
            f"{first['player_name']} is listed at ${first['auction_value']} and usually sells ${first_low}–${first_high}. "
            f"Stay in until ${self.your_max(first)} if you want him. Paying much past that is a tax. "
            f"{second['player_name']} is the other name if you want the room to spend."
        )
        return {"mode": "nominate", "player_name": first["player_name"], "options": options, "paragraph": paragraph}

    def _bid_advice(self) -> dict:
        player = self.players[self.on_block["player_name"]]
        current = int(self.on_block["bid"])
        nxt = current + 1
        ceiling = min(self.your_max(player), self.max_offer(self.your_team))
        high = self.team_name(int(self.on_block["high_bidder"]))
        low, high_sale = typical_sale(int(player["auction_value"]))
        options = [
            {**player, "action": "bid", "percent": 70, "bid": nxt, "max_bid": ceiling, "typical_low": low, "typical_high": high_sale, "label": f"Offer ${nxt}"},
            {**player, "action": "hold", "percent": 30, "bid": current, "max_bid": ceiling, "typical_low": low, "typical_high": high_sale, "label": "Hold"},
        ]
        leftover = self.max_offer(self.your_team)
        if ceiling > current:
            why = (
                f"{player['player_name']} is at ${current}. {high} has the offer. "
                f"Listed ${player['auction_value']}; in a real $200 room this name usually goes ${low}–${high_sale}. "
                f"Stay in until ${ceiling}. Past that you are paying a tax. "
                f"You have {self.seconds_left()} seconds. Offer raises by $1. A bid inside the last 10 puts 10 seconds back."
            )
        elif leftover > current:
            why = (
                f"{player['player_name']} is at ${current}. {high} has the offer. "
                f"That is already market (${low}–${high_sale}). You can still stretch to ${leftover}, "
                f"but that is a tax. Hold unless you need him."
            )
        else:
            why = (
                f"{player['player_name']} is at ${current}. That is already at or above what you can pay "
                f"and still fill the roster at $1 a seat. Hold and let the clock run out."
            )
        return {"mode": "bid", "player_name": player["player_name"], "options": options, "paragraph": why}

    def _roster(self, team_index: int) -> dict:
        filed = {pick["slot_id"]: pick for pick in self.picks if pick["team_index"] == team_index}
        slots = []
        for slot_id, label in SLOTS:
            pick = filed.get(slot_id)
            slots.append(
                {
                    "id": slot_id,
                    "label": label,
                    "player": None
                    if pick is None
                    else {
                        "player_name": pick["player_name"],
                        "positions": (pick.get("player") or {}).get("positions") or pick.get("slot_label", ""),
                        "price": pick["price"],
                    },
                }
            )
        return {
            "name": self.team_name(team_index),
            "is_you": team_index == self.your_team,
            "budget": self.budgets[team_index],
            "slots": slots,
        }

    def state(self) -> dict:
        complete = len(self.picks) >= self.total_picks
        nom = self.nominator()
        block = None
        if self.on_block:
            player = self.players[self.on_block["player_name"]]
            block = {
                **player,
                "nominator": self.team_name(self.on_block["nominator"]),
                "bid": self.on_block["bid"],
                "high_bidder": self.team_name(self.on_block["high_bidder"]),
                "your_high": int(self.on_block["high_bidder"]) == self.your_team,
                "next_bid": int(self.on_block["bid"]) + 1,
                "your_max": self.your_max(player),
                "max_offer": self.max_offer(self.your_team),
                "typical_low": typical_sale(int(player.get("auction_value") or 1))[0],
                "typical_high": typical_sale(int(player.get("auction_value") or 1))[1],
            }
        coach = None
        if self.on_block:
            player = self.players[self.on_block["player_name"]]
            coach = build_card(
                player,
                int(self.on_block["bid"]),
                self.budgets[self.your_team],
                self.spots_left(self.your_team),
                self._owns_elite(self.your_team),
                self.available_players(),
            )
        return {
            "started": True,
            "mode": "mock",
            "complete": complete,
            "phase": self.phase if not complete else "done",
            "categories": list(ALL_CATEGORIES),
            "filters": list(FILTERS),
            "can_nominate": (not complete) and self.phase == "nominate" and self.nominator() == self.your_team,
            "your_turn": (not complete) and self.waiting_on_you(),
            "nomination_slot": self.draft_slot,
            "on_clock": None if complete else (block["high_bidder"] if block else self.team_name(nom) if nom is not None else ""),
            "round": (len(self.picks) // self.team_count) + 1 if not complete else ROUNDS,
            "pick_number": len(self.picks) + 1,
            "budget": self.budget,
            "budget_left": self.budgets[self.your_team],
            "spots_left": self.spots_left(self.your_team),
            "seconds_left": 0 if complete else self.seconds_left(),
            "on_block": block,
            "coach": coach,
            "suggestion": self.suggestion(),
            "available": self.available_players(),
            "rosters": [self._roster(index) for index in range(self.team_count)],
            "queue": [self.players[name] for name in self.queue if name in self.players],
            "log": [
                {
                    "pick_number": pick["pick_number"],
                    "team": pick["team"],
                    "player_name": pick["player_name"],
                    "slot_label": pick["slot_label"],
                    "price": pick["price"],
                }
                for pick in self.picks
            ],
            "guide": (
                "Yahoo salary cap: nominate in a circle, 1 through 16, then 1 again. "
                "30 seconds to name a player at $1. 20 seconds for everyone to raise. "
                "A bid inside the last 10 seconds puts 10 seconds back. Highest offer when the clock hits 0 wins. "
                "Leave $1 for every empty seat. Listed prices follow a real $200 room. "
                "Computers stop near 112% of listed value and will not stack two $40+ stars."
            ),
        }

    def to_json(self) -> dict:
        return {
            "mode": "mock",
            "team_count": self.team_count,
            "draft_slot": self.draft_slot,
            "punts": self.punts,
            "budget": self.budget,
            "picks": self.picks,
            "queue": self.queue,
            "budgets": self.budgets,
            "on_block": self.on_block,
            "phase": self.phase,
            "clock_ends": self.clock_ends.isoformat(),
            "clock_started": self.clock_started.isoformat(),
        }

    @classmethod
    def from_json(cls, payload: dict, players: list[dict]) -> "DraftSession":
        session = cls(
            players,
            team_count=int(payload["team_count"]),
            draft_slot=int(payload["draft_slot"]),
            punts=list(payload.get("punts") or []),
            budget=int(payload.get("budget") or DEFAULT_BUDGET),
        )
        session.picks = list(payload.get("picks") or [])
        session.queue = list(payload.get("queue") or [])
        session.budgets = list(payload.get("budgets") or [session.budget] * session.team_count)
        session.on_block = payload.get("on_block")
        session.phase = str(payload.get("phase") or ("bid" if session.on_block else "nominate"))
        if payload.get("clock_ends"):
            session.clock_ends = datetime.fromisoformat(payload["clock_ends"])
        taken = {pick["player_name"] for pick in session.picks}
        session.players = {name: player for name, player in session.players.items() if name not in taken}
        return session


def save_session(session: DraftSession | None, path: Path = SESSION_PATH) -> None:
    if session is None:
        if path.exists():
            path.unlink()
        return
    path.write_text(json.dumps(session.to_json(), indent=2))


def load_session(players: list[dict], path: Path = SESSION_PATH) -> DraftSession | None:
    if not path.exists():
        return None
    return DraftSession.from_json(json.loads(path.read_text()), players)
