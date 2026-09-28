"""Sidecar for a real Yahoo room: you type what you see, the board talks back."""

from __future__ import annotations

import json
from pathlib import Path

from coach import build_card, match_player, parse_feed, stay_price
from room import fair_marks, read_room
from draft_room import DEFAULT_BUDGET, FILTERS, HELPER_PATH, ROSTER_SIZE, SLOTS, TEAM_COUNT, first_open_slot
from math_engine import ALL_CATEGORIES


class SidecarSession:
    mode = "live"

    def __init__(
        self,
        players: list[dict],
        team_count: int = TEAM_COUNT,
        punts: list[str] | None = None,
        budget: int = DEFAULT_BUDGET,
    ) -> None:
        self.players = {player["player_name"]: dict(player) for player in players}
        self.team_count = team_count
        self.punts = list(punts or [])
        self.budget = budget
        self.budget_left = budget
        self.picks: list[dict] = []
        self.taken: list[dict] = []
        self.focus: dict | None = None
        self.queue: list[str] = []

    def spots_left(self) -> int:
        return ROSTER_SIZE - len(self.picks)

    def owns_elite(self) -> bool:
        return any(int(pick.get("auction_value") or 0) >= 40 for pick in self.picks)

    def available_players(self) -> list[dict]:
        gone = {item["player_name"] for item in self.taken}
        return [
            player
            for player in sorted(
                self.players.values(),
                key=lambda item: (-item["auction_value"], -(item["total_value"] or -999)),
            )
            if player["player_name"] not in gone
        ]

    def feed(self, line: str) -> None:
        command = parse_feed(line)
        pool = self.available_players() + [item["player"] for item in self.taken if item.get("player")]
        player = match_player(command["query"], pool)
        name = player["player_name"]
        already = next((item for item in self.taken if item["player_name"] == name), None)
        if already and command["action"] == "lookup":
            self.focus = {"player_name": name, "bid": already["price"]}
            return
        if already:
            raise ValueError(f"{name} is already logged at ${already['price']}.")
        if command["action"] == "lookup":
            self.focus = {"player_name": name, "bid": command["amount"]}
            return
        self.focus = {"player_name": name, "bid": command["amount"]}
        self.close(command["action"], command["amount"])

    def pick(self, query: str, amount: int | None = None) -> None:
        self.feed(" ".join(part for part in [query, str(amount) if amount is not None else ""] if part))

    def set_bid(self, amount: int) -> None:
        if not self.focus:
            raise ValueError("Pick a name first.")
        self.focus["bid"] = max(1, int(amount))

    def close_price(self, amount: int | None = None) -> int:
        if not self.focus:
            raise ValueError("Pick a name first.")
        player = self.players[self.focus["player_name"]]
        if amount is not None:
            return max(1, int(amount))
        if self.focus.get("bid") is not None:
            return max(1, int(self.focus["bid"]))
        listed = int(player.get("yahoo_listed") or player.get("auction_value") or 1)
        return stay_price(listed, self.budget_left, self.spots_left(), self.owns_elite(), player)

    def close(self, action: str, amount: int | None = None) -> None:
        if action not in {"sold", "me", "keep", "locked"}:
            raise ValueError("Tap Sold, Me, Keep, or Locked.")
        if not self.focus:
            raise ValueError("Pick a name first.")
        name = self.focus["player_name"]
        already = next((item for item in self.taken if item["player_name"] == name), None)
        if already:
            raise ValueError(f"{name} is already logged at ${already['price']}.")
        player = self.players[name]
        listed = int(player.get("yahoo_listed") or player.get("auction_value") or 1)
        dynasty = action in {"keep", "locked"}
        if dynasty and player.get("superstar"):
            raise ValueError("Pilsner superstars cannot be dynasty. Log Sold or Me.")
        price = listed if dynasty else self.close_price(amount)
        stay, stretch = fair_marks(player, listed, self.budget)
        stamp = {
            "player_name": name,
            "player": dict(player),
            "price": price,
            "auction_value": int(player.get("auction_value") or 1),
            "listed": listed,
            "fair_stay": stay,
            "fair_stretch": stretch,
            "yours": action in {"me", "keep"},
            "kind": "dynasty" if dynasty else "sale",
        }
        if stamp["yours"]:
            if self.spots_left() <= 0:
                raise ValueError("Your ten seats are full.")
            ceiling = self.budget_left - max(0, self.spots_left() - 1)
            if price > ceiling:
                raise ValueError(f"That leaves empty seats unpaid. Most you can log is ${ceiling}.")
            filled = {pick["slot_id"] for pick in self.picks}
            try:
                slot_id = first_open_slot(player["positions"], filled)
            except ValueError:
                slot_id = next(slot for slot, _label in SLOTS if slot not in filled)
            stamp["slot_id"] = slot_id
            stamp["slot_label"] = dict(SLOTS)[slot_id]
            self.picks.append(stamp)
            self.taken.append(stamp)
            self.budget_left -= price
        else:
            self.taken.append(stamp)
        self.focus = None

    def undo(self) -> None:
        if self.focus is not None:
            self.focus = None
            return
        if not self.taken:
            raise ValueError("Nothing to undo.")
        last = self.taken.pop()
        if last.get("yours"):
            self.picks = [pick for pick in self.picks if pick["player_name"] != last["player_name"]]
            self.budget_left += int(last["price"])

    def queue_add(self, player_name: str) -> None:
        if player_name not in {player["player_name"] for player in self.available_players()}:
            raise ValueError(f"No available player named {player_name}.")
        if player_name not in self.queue:
            self.queue.append(player_name)

    def queue_remove(self, player_name: str) -> None:
        if player_name in self.queue:
            self.queue.remove(player_name)

    def tick(self) -> None:
        return

    def _coach(self) -> dict | None:
        if not self.focus:
            return None
        player = self.players.get(self.focus["player_name"])
        if player is None:
            return None
        return build_card(
            player,
            self.focus.get("bid"),
            self.budget_left,
            self.spots_left(),
            self.owns_elite(),
            self.available_players(),
            self.room(),
        )

    def room(self) -> dict:
        return read_room(self.taken, self.team_count, self.budget)

    def _roster(self) -> dict:
        filed = {pick["slot_id"]: pick for pick in self.picks}
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
        return {"name": "You", "is_you": True, "budget": self.budget_left, "slots": slots}

    def state(self) -> dict:
        coach = self._coach()
        focused = None
        if self.focus and self.focus["player_name"] in self.players:
            focused = {**self.players[self.focus["player_name"]], "bid": self.focus.get("bid")}
        return {
            "started": True,
            "mode": "live",
            "complete": len(self.picks) >= ROSTER_SIZE,
            "phase": "live",
            "categories": list(ALL_CATEGORIES),
            "filters": list(FILTERS),
            "can_nominate": False,
            "your_turn": False,
            "nomination_slot": None,
            "on_clock": "",
            "budget": self.budget,
            "budget_left": self.budget_left,
            "spots_left": self.spots_left(),
            "seconds_left": 0,
            "on_block": None,
            "coach": coach,
            "room": self.room(),
            "focus": focused,
            "suggestion": {
                "mode": "live",
                "options": [],
                "paragraph": coach["why"] if coach else "Tap a name. Sold is the room. Me is you. The dollar starts at Stay.",
            },
            "available": self.available_players(),
            "rosters": [self._roster()],
            "queue": [self.players[name] for name in self.queue if name in self.players],
            "log": [
                {
                    "pick_number": index + 1,
                    "team": "You" if item.get("yours") else ("Locked" if item.get("kind") == "dynasty" else "Room"),
                    "player_name": item["player_name"],
                    "slot_label": item.get("slot_label") or "—",
                    "price": item["price"],
                }
                for index, item in enumerate(self.taken)
            ],
            "guide": (
                "This tab does not touch Yahoo. Type the name and the dollar you see. "
                "Stay is market. Stretch is the last dollar that does not wreck the roster. After that, pass. "
                "Keep is your dynasty at Yahoo list. Locked is someone else's. Neither teaches heat."
            ),
        }

    def to_json(self) -> dict:
        return {
            "mode": "live",
            "team_count": self.team_count,
            "punts": self.punts,
            "budget": self.budget,
            "budget_left": self.budget_left,
            "picks": self.picks,
            "taken": self.taken,
            "focus": self.focus,
            "queue": self.queue,
        }

    @classmethod
    def from_json(cls, payload: dict, players: list[dict]) -> "SidecarSession":
        session = cls(
            players,
            team_count=int(payload.get("team_count") or TEAM_COUNT),
            punts=list(payload.get("punts") or []),
            budget=int(payload.get("budget") or DEFAULT_BUDGET),
        )
        session.budget_left = int(payload.get("budget_left") or session.budget)
        session.picks = list(payload.get("picks") or [])
        session.taken = list(payload.get("taken") or [])
        session.focus = payload.get("focus")
        session.queue = list(payload.get("queue") or [])
        gone = {item["player_name"] for item in session.taken}
        session.players = {name: player for name, player in session.players.items() if name not in gone}
        for item in session.taken:
            player = item.get("player")
            if player:
                session.players[player["player_name"]] = player
        return session


def save_sidecar(session: SidecarSession | None, path: Path = HELPER_PATH) -> None:
    if session is None:
        if path.exists():
            path.unlink()
        return
    path.write_text(json.dumps(session.to_json(), indent=2))


def load_sidecar(players: list[dict], path: Path = HELPER_PATH) -> SidecarSession | None:
    if not path.exists():
        return None
    return SidecarSession.from_json(json.loads(path.read_text()), players)
