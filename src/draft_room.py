"""Snake draft that follows Yahoo Fantasy Basketball's live draft room.

Yahoo's default roster is PG, SG, G, SF, PF, F, two C, two Util, and three bench.
A manager drafts a player. The room files that player into the most specific
open slot they can play. Each manager keeps a queue. The clock is 60 seconds,
then the pick comes from that queue, or from the top of the board.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from availability import attach_games_forecast
from data_loader import ProjectionLoader
from math_engine import ALL_CATEGORIES, DUAL_POSITION_MULTIPLIER, FantasyMathEngine
from rookies import ROOKIE_PATH

ROOT = Path(__file__).resolve().parents[1]
PROJECTIONS = ROOT / "data" / "projections.csv"
FORECAST = ROOT / "data" / "games_forecast.csv"
SESSION_PATH = ROOT / "data" / "draft_session.json"

ROUNDS = 13
PICK_SECONDS = 60
SLOTS: tuple[tuple[str, str], ...] = (
    ("PG", "PG"),
    ("SG", "SG"),
    ("G", "G"),
    ("SF", "SF"),
    ("PF", "PF"),
    ("F", "F"),
    ("C1", "C"),
    ("C2", "C"),
    ("UTIL1", "UTIL"),
    ("UTIL2", "UTIL"),
    ("BN1", "BN"),
    ("BN2", "BN"),
    ("BN3", "BN"),
)
FLEX_SLOTS = frozenset({"UTIL", "BN"})
FILTERS = ("All", "PG", "SG", "G", "SF", "PF", "F", "C")


def snake_order(team_count: int, rounds: int = ROUNDS) -> list[int]:
    order: list[int] = []
    for round_number in range(rounds):
        seats = list(range(team_count))
        if round_number % 2 == 1:
            seats.reverse()
        order.extend(seats)
    return order


def player_positions(positions: object) -> set[str]:
    text = "" if positions is None else str(positions)
    return {part.strip().upper() for part in text.split("/") if part.strip() and part.strip().lower() != "nan"}


def eligible_for_slot(positions: object, slot_label: str) -> bool:
    held = player_positions(positions)
    if slot_label in FLEX_SLOTS:
        return True
    if slot_label == "G":
        return bool(held & {"PG", "SG", "G"})
    if slot_label == "F":
        return bool(held & {"SF", "PF", "F"})
    return slot_label in held


COMPARED_STATS: tuple[tuple[str, str, bool], ...] = (
    ("pts", "points", True),
    ("reb", "rebounds", True),
    ("ast", "assists", True),
    ("stl", "steals", True),
    ("blk", "blocks", True),
    ("fg3m", "threes", True),
    ("fg_pct", "field-goal percentage", True),
    ("ft_pct", "free-throw percentage", True),
    ("to", "turnovers", False),
)


def _edges(player: dict, other: dict) -> list[str]:
    edges: list[str] = []
    for key, label, higher in COMPARED_STATS:
        left = player.get(key)
        right = other.get(key)
        if left is None or right is None:
            continue
        if higher and left > right and left - right >= max(0.3, abs(right) * 0.1):
            edges.append(label)
        if not higher and right > left and right - left >= max(0.2, abs(right) * 0.1):
            edges.append("fewer turnovers")
    return edges[:3]


def _choice_percents(first: dict, second: dict) -> tuple[int, int]:
    """Share of the decision from the value gap, with a small games nudge.

    A gap of about 1.25 value points is a 73 / 27 split. A gap of 0.3, which
    is typical after the top of the board, is close to 56 / 44. Twenty extra
    predicted games moves a split by only a couple of points.
    """
    import math

    games_nudge = 0.0
    if first.get("predicted_games") is not None and second.get("predicted_games") is not None:
        games_nudge = (int(first["predicted_games"]) - int(second["predicted_games"])) / 200
    gap = float(first["total_value"] or 0) - float(second["total_value"] or 0) + games_nudge
    share = 1 / (1 + math.exp(-gap / 1.25))
    percent = int(round(share * 100))
    percent = min(95, max(50, percent))
    return percent, 100 - percent


def _comparison_paragraph(first: dict, second: dict, first_pct: int, second_pct: int) -> str:
    first_edges = _edges(first, second)
    second_edges = _edges(second, first)
    first_edge = ", ".join(first_edges) if first_edges else "the overall category score"
    second_edge = ", ".join(second_edges) if second_edges else "a close overall score"
    games = ""
    if first.get("predicted_games") is not None and second.get("predicted_games") is not None:
        games = (
            f" {first['player_name']} is predicted for {first['predicted_games']} games and "
            f"{second['player_name']} for {second['predicted_games']}. "
            "That does not change their rank. It is only a nudge when the values are close."
        )
    return (
        f"{first['player_name']} carries {first_pct}% of this choice and "
        f"{second['player_name']} carries {second_pct}%. "
        f"The split comes from the 9-category value, {first['total_value']} against {second['total_value']}. "
        f"A wide gap, like the top of the board, makes the first player the clear side. "
        f"A small gap, which is the rest of the draft, leaves the two sides close. "
        f"{first['player_name']} is ahead in {first_edge}. "
        f"{second['player_name']} is the better side for {second_edge}."
        f"{games} "
        f"Take {first['player_name']} for the higher category score. "
        f"Take {second['player_name']} when those specific categories, or the extra games, matter more to the roster."
    )


def first_open_slot(positions: object, filled_slot_ids: set[str]) -> str:
    for slot_id, label in SLOTS:
        if slot_id in filled_slot_ids:
            continue
        if eligible_for_slot(positions, label):
            return slot_id
    raise ValueError("This roster has no open slot for that player.")


def _value_with_punts(frame: pd.DataFrame, punts: list[str]) -> pd.Series:
    kept = [f"z_{category}" for category in ALL_CATEGORIES if category not in punts]
    base = frame[kept].sum(axis=1)
    multi = frame["positions"].astype(str).str.contains("/", regex=False)
    return base.where(~multi, base * DUAL_POSITION_MULTIPLIER)


def _player_record(row: pd.Series, rookie: bool) -> dict:
    predicted = row.get("predicted_games")
    value = row.get("total_value")
    return {
        "player_name": str(row["player_name"]),
        "positions": "" if pd.isna(row.get("positions")) else str(row.get("positions")),
        "team": "" if pd.isna(row.get("team")) else str(row.get("team")),
        "total_value": None if pd.isna(value) else round(float(value), 2),
        "predicted_games": None if pd.isna(predicted) else int(predicted),
        "rookie": rookie,
        "pts": _num(row.get("pts")),
        "reb": _num(row.get("reb")),
        "ast": _num(row.get("ast")),
        "stl": _num(row.get("stl")),
        "blk": _num(row.get("blk")),
        "fg3m": _num(row.get("fg3m")),
        "fg_pct": _rate(row.get("fg_pct")),
        "ft_pct": _rate(row.get("ft_pct")),
        "to": _num(row.get("to")),
    }


def _rate(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return None
    return round(float(value), 3)


def _num(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return None
    return round(float(value), 1)


def build_pool(punts: list[str] | None = None) -> list[dict]:
    """Rank veterans, then place translated rookies on the same scale."""
    active_punts = list(punts or [])
    unknown = [category for category in active_punts if category not in ALL_CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown punt categories: {unknown}")

    engine = FantasyMathEngine()
    engine.load_data(ProjectionLoader(PROJECTIONS))
    ranked = engine.get_ranked_players(active_punts=active_punts)
    if FORECAST.exists():
        ranked = attach_games_forecast(ranked, pd.read_csv(FORECAST))
    if "games" in ranked.columns:
        if "predicted_games" not in ranked.columns:
            ranked["predicted_games"] = ranked["games"]
        else:
            ranked["predicted_games"] = ranked["predicted_games"].fillna(ranked["games"])

    players = [_player_record(row, rookie=False) for _, row in ranked.iterrows()]
    if ROOKIE_PATH.exists():
        rookies = pd.read_csv(ROOKIE_PATH)
        rookies = rookies[rookies["translation"] == "college_to_nba"].copy()
        for column in ("pts", "reb", "ast", "stl", "blk", "fg3m", "fg_pct", "fga", "ft_pct", "fta", "to"):
            rookies[column] = pd.to_numeric(rookies[column], errors="coerce")
        rookies = rookies.dropna(subset=["pts", "reb", "ast", "fg_pct", "fga", "ft_pct", "fta", "to"])
        if not rookies.empty:
            scored = engine.score_with_baselines(rookies, engine.category_baselines())
            scored["total_value"] = _value_with_punts(scored, active_punts)
            veteran_names = {player["player_name"] for player in players}
            for _, row in scored.iterrows():
                if row["player_name"] in veteran_names:
                    continue
                players.append(_player_record(row, rookie=True))

    players.sort(key=lambda player: (-(player["total_value"] or -999), player["player_name"]))
    return players


class DraftSession:
    def __init__(
        self,
        players: list[dict],
        team_count: int,
        draft_slot: int,
        punts: list[str] | None = None,
        rounds: int = ROUNDS,
    ) -> None:
        if team_count < 2:
            raise ValueError("A draft needs at least two teams.")
        if not 1 <= draft_slot <= team_count:
            raise ValueError(f"Your pick position must be between 1 and {team_count}.")
        self.players = {player["player_name"]: player for player in players}
        self.team_count = team_count
        self.draft_slot = draft_slot
        self.punts = list(punts or [])
        self.order = snake_order(team_count, rounds)
        self.picks: list[dict] = []
        self.queue: list[str] = []
        self.clock_started = datetime.now(timezone.utc)

    @property
    def your_team(self) -> int:
        return self.draft_slot - 1

    def team_name(self, team_index: int) -> str:
        if team_index == self.your_team:
            return "You"
        if self.team_count == 2:
            return "Other manager"
        return f"Team {team_index + 1}"

    def on_clock(self) -> int | None:
        if len(self.picks) >= len(self.order):
            return None
        return self.order[len(self.picks)]

    def pick(self, player_name: str) -> None:
        team_index = self.on_clock()
        if team_index is None:
            raise ValueError("The draft is complete.")
        player = self.players.get(player_name)
        if player is None:
            raise ValueError(f"No available player named {player_name}.")
        if any(pick["player_name"] == player_name for pick in self.picks):
            raise ValueError(f"{player_name} is already drafted.")
        filled = {pick["slot_id"] for pick in self.picks if pick["team"] == team_index}
        slot_id = first_open_slot(player["positions"], filled)
        slot_label = dict(SLOTS)[slot_id]
        self.picks.append(
            {
                "team": team_index,
                "player_name": player_name,
                "slot_id": slot_id,
                "slot_label": slot_label,
            }
        )
        self.queue = [name for name in self.queue if name != player_name]
        self.clock_started = datetime.now(timezone.utc)

    def queue_add(self, player_name: str) -> None:
        if player_name not in self.players:
            raise ValueError(f"No available player named {player_name}.")
        if player_name not in self.queue:
            self.queue.append(player_name)

    def queue_remove(self, player_name: str) -> None:
        self.queue = [name for name in self.queue if name != player_name]

    def autopick(self) -> None:
        if self.on_clock() is None:
            raise ValueError("The draft is complete.")
        drafted = {pick["player_name"] for pick in self.picks}
        if self.on_clock() == self.your_team:
            for name in self.queue:
                if name not in drafted:
                    self.pick(name)
                    return
        ranked = sorted(
            (player for name, player in self.players.items() if name not in drafted),
            key=lambda player: (-(player["total_value"] or -999), player["player_name"]),
        )
        if not ranked:
            raise ValueError("No players left.")
        self.pick(ranked[0]["player_name"])

    def suggestion(self, available: list[dict] | None = None) -> dict | None:
        """The player to take on your turn, and the reason that choice was made.

        Other teams take the best value still available. Your suggestion is that
        same player while a starting slot is open, because utility can hold
        anyone. After the ten starting slots are full, it is the best player
        left for the bench. Predicted games never change the order.
        """
        if available is None:
            drafted = {pick["player_name"] for pick in self.picks}
            available = [player for name, player in self.players.items() if name not in drafted]
            available.sort(key=lambda player: (-(player["total_value"] or -999), player["player_name"]))
        if not available:
            return None
        filled = {pick["slot_id"] for pick in self.picks if pick["team"] == self.your_team}
        pair = available[:2]
        options = []
        for player in pair:
            slot_id = first_open_slot(player["positions"], filled)
            options.append(
                {
                    "player_name": player["player_name"],
                    "positions": player["positions"],
                    "team": player["team"],
                    "total_value": player["total_value"],
                    "predicted_games": player["predicted_games"],
                    "slot_label": dict(SLOTS)[slot_id],
                }
            )
        if len(options) == 1:
            only = options[0]
            return {
                "player_name": only["player_name"],
                "options": options,
                "paragraph": f"{only['player_name']} is the only player left.",
            }
        first_pct, second_pct = _choice_percents(options[0], options[1])
        options[0]["percent"] = first_pct
        options[1]["percent"] = second_pct
        return {
            "player_name": options[0]["player_name"],
            "options": options,
            "paragraph": _comparison_paragraph(options[0], options[1], first_pct, second_pct),
        }

    def undo(self) -> None:
        if not self.picks:
            raise ValueError("No pick to undo.")
        self.picks.pop()

    def state(self) -> dict:
        drafted = {pick["player_name"] for pick in self.picks}
        available = [player for name, player in self.players.items() if name not in drafted]
        available.sort(key=lambda player: (-(player["total_value"] or -999), player["player_name"]))
        clock = self.on_clock()
        pick_number = len(self.picks) + 1
        rosters = []
        for team_index in range(self.team_count):
            filled = {
                pick["slot_id"]: self.players[pick["player_name"]]
                for pick in self.picks
                if pick["team"] == team_index
            }
            rosters.append(
                {
                    "team": team_index,
                    "name": self.team_name(team_index),
                    "is_you": team_index == self.your_team,
                    "slots": [
                        {
                            "id": slot_id,
                            "label": label,
                            "player": filled.get(slot_id),
                        }
                        for slot_id, label in SLOTS
                    ],
                }
            )
        return {
            "started": True,
            "complete": clock is None,
            "team_count": self.team_count,
            "draft_slot": self.draft_slot,
            "punts": self.punts,
            "round": min(ROUNDS, ((pick_number - 1) // self.team_count) + 1),
            "pick_number": min(pick_number, len(self.order)),
            "your_turn": clock == self.your_team,
            "on_clock": None if clock is None else self.team_name(clock),
            "seconds_left": 0 if clock is None else max(0, PICK_SECONDS - int((datetime.now(timezone.utc) - self.clock_started).total_seconds())),
            "pick_seconds": PICK_SECONDS,
            "suggestion": self.suggestion(available),
            "filters": list(FILTERS),
            "queue": [self.players[name] for name in self.queue if name in self.players and name not in drafted],
            "log": [
                {
                    "team": self.team_name(pick["team"]),
                    "player_name": pick["player_name"],
                    "slot_label": pick["slot_label"],
                    "pick_number": index + 1,
                }
                for index, pick in enumerate(self.picks)
            ][-8:],
            "rosters": rosters,
            "available": available,
            "slots": [{"id": slot_id, "label": label} for slot_id, label in SLOTS],
        }

    def to_json(self) -> dict:
        return {
            "team_count": self.team_count,
            "draft_slot": self.draft_slot,
            "punts": self.punts,
            "picks": self.picks,
            "queue": self.queue,
        }

    @classmethod
    def from_json(cls, payload: dict, players: list[dict]) -> "DraftSession":
        session = cls(
            players,
            team_count=int(payload["team_count"]),
            draft_slot=int(payload["draft_slot"]),
            punts=list(payload.get("punts") or []),
        )
        session.picks = list(payload.get("picks") or [])
        session.queue = list(payload.get("queue") or [])
        return session


def save_session(session: DraftSession | None, path: Path = SESSION_PATH) -> None:
    if session is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session.to_json()), encoding="utf-8")


def load_session(players: list[dict], path: Path = SESSION_PATH) -> DraftSession | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return DraftSession.from_json(payload, players)
