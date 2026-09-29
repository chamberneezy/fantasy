"""Salary-cap mock: 16 teams, $200, 12 categories, 10 roster spots."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from auction import assign_auction_values, cap_bid, estimate_dd
from availability import attach_games_forecast, name_key
from data_loader import ProjectionLoader
from math_engine import ALL_CATEGORIES, DUAL_POSITION_MULTIPLIER, FantasyMathEngine
from rookies import ROOKIE_PATH

ROOT = Path(__file__).resolve().parents[1]
PROJECTIONS = ROOT / "data" / "projections.csv"
FORECAST = ROOT / "data" / "games_forecast.csv"
DOUBLES = ROOT / "data" / "double_doubles.csv"
SESSION_PATH = ROOT / "data" / "draft_session.json"
HELPER_PATH = ROOT / "data" / "helper_session.json"
LAB_PATH = ROOT / "data" / "lab_report.json"

TEAM_COUNT = 16
ROSTER_SIZE = 10
DEFAULT_BUDGET = 200
MIN_BUDGET = 160
MAX_BUDGET = 240
ROUNDS = 10
NOMINATE_SECONDS = 30
BID_SECONDS = 20
BID_RESET_SECONDS = 10
COMPUTER_VALUE_CAP = 1.20
SLOTS: tuple[tuple[str, str], ...] = (
    ("PG", "PG"),
    ("SG", "SG"),
    ("SF", "SF"),
    ("PF", "PF"),
    ("C", "C"),
    ("BN1", "BN"),
    ("BN2", "BN"),
    ("BN3", "BN"),
    ("BN4", "BN"),
    ("BN5", "BN"),
)
FLEX_SLOTS = frozenset({"BN"})
FILTERS = ("All", "PG", "SG", "SF", "PF", "C")
SUPERSTARS = frozenset(
    {
        "trae young",
        "jalen johnson",
        "cooper flagg",
        "jayson tatum",
        "lamelo ball",
        "donovan mitchell",
        "luka doncic",
        "nikola jokic",
        "cade cunningham",
        "stephen curry",
        "alperen sengun",
        "tyrese haliburton",
        "james harden",
        "anthony davis",
        "bam adebayo",
        "giannis antetokounmpo",
        "anthony edwards",
        "jalen brunson",
        "karl-anthony towns",
        "shai gilgeous-alexander",
        "paolo banchero",
        "tyrese maxey",
        "kevin durant",
        "devin booker",
        "kawhi leonard",
        "domantas sabonis",
        "victor wembanyama",
        "scottie barnes",
    }
)


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
    return slot_label in held


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


def _num(value: object, digits: int = 1) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _rate(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 3)


def _player_record(row: pd.Series, rookie: bool) -> dict:
    predicted = row.get("predicted_games")
    value = row.get("total_value")
    price = row.get("auction_value")
    return {
        "player_name": str(row["player_name"]),
        "positions": "" if pd.isna(row.get("positions")) else str(row.get("positions")),
        "team": "" if pd.isna(row.get("team")) else str(row.get("team")),
        "total_value": None if pd.isna(value) else round(float(value), 2),
        "auction_value": 1 if pd.isna(price) else int(price),
        "predicted_games": None if pd.isna(predicted) else int(predicted),
        "rookie": rookie,
        "superstar": name_key(row["player_name"]) in SUPERSTARS,
        "pts": _num(row.get("pts")),
        "reb": _num(row.get("reb")),
        "ast": _num(row.get("ast")),
        "stl": _num(row.get("stl")),
        "blk": _num(row.get("blk")),
        "fg3m": _num(row.get("fg3m")),
        "mp": _num(row.get("mp")),
        "pf": _num(row.get("pf")),
        "dd": _num(row.get("dd"), 2),
        "fg_pct": _rate(row.get("fg_pct")),
        "ft_pct": _rate(row.get("ft_pct")),
        "to": _num(row.get("to")),
    }


def _attach_double_doubles(frame: pd.DataFrame) -> pd.DataFrame:
    scored = frame.copy()
    if "dd" not in scored.columns:
        scored["dd"] = pd.NA
    if DOUBLES.exists():
        doubles = pd.read_csv(DOUBLES)
        scored["name_key"] = scored["player_name"].map(name_key)
        scored = scored.merge(doubles[["name_key", "dd"]], on="name_key", how="left", suffixes=("", "_nba"))
        if "dd_nba" in scored.columns:
            scored["dd"] = scored["dd_nba"].where(scored["dd_nba"].notna(), scored["dd"])
            scored = scored.drop(columns=["dd_nba"])
        scored = scored.drop(columns=["name_key"])
    missing = scored["dd"].isna()
    if missing.any():
        scored.loc[missing, "dd"] = [
            estimate_dd(float(row.pts or 0), float(row.reb or 0), float(row.ast or 0))
            for row in scored.loc[missing].itertuples()
        ]
    return scored


def _prepare_rookies(rookies: pd.DataFrame) -> pd.DataFrame:
    frame = rookies.copy()
    for column in ("pts", "reb", "ast", "stl", "blk", "fg3m", "fg_pct", "fga", "ft_pct", "fta", "to"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["pts", "reb", "ast", "fg_pct", "fga", "ft_pct", "fta", "to"])
    pick = pd.to_numeric(frame.get("overall_pick"), errors="coerce")
    frame["mp"] = pick.map(lambda value: 32 if value <= 5 else 28 if value <= 14 else 22)
    frame["pf"] = 2.2
    frame["dd"] = [
        estimate_dd(float(row.pts), float(row.reb), float(row.ast)) for row in frame.itertuples()
    ]
    return frame


def build_pool(
    punts: list[str] | None = None,
    team_count: int = TEAM_COUNT,
    roster_size: int = ROSTER_SIZE,
    budget: int = DEFAULT_BUDGET,
) -> list[dict]:
    """Rank the board and print a dollar price next to each name."""
    active_punts = list(punts or [])
    unknown = [category for category in active_punts if category not in ALL_CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown punt categories: {unknown}")

    engine = FantasyMathEngine()
    loaded = ProjectionLoader(PROJECTIONS).load()
    loaded = _attach_double_doubles(loaded)
    engine.load_data(loaded)
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
        rookies = _prepare_rookies(pd.read_csv(ROOKIE_PATH).query("translation == 'college_to_nba'"))
        if not rookies.empty:
            scored = engine.score_with_baselines(rookies, engine.category_baselines())
            scored["total_value"] = _value_with_punts(scored, active_punts)
            veteran_names = {player["player_name"] for player in players}
            for _, row in scored.iterrows():
                if row["player_name"] in veteran_names:
                    continue
                players.append(_player_record(row, rookie=True))

    assign_auction_values(players, team_count, roster_size, budget)
    players.sort(key=lambda player: (-player["auction_value"], -(player["total_value"] or -999), player["player_name"]))
    return players


