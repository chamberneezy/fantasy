"""One player's expected line for one game.

Per-minute rates times expected minutes. This season's games count most
recent first; the season line (last year's per-game, or the rookie
translation) is the anchor until enough games are in. Opponent, rest and
injury news are not in this number yet.
"""

from __future__ import annotations

import pandas as pd

from math_engine import ALL_CATEGORIES, FantasyMathEngine

STAT_COLUMNS: tuple[str, ...] = (
    "fgm",
    "fga",
    "ftm",
    "fta",
    "fg3m",
    "pts",
    "reb",
    "ast",
    "stl",
    "blk",
    "to",
    "pf",
)

# A game this many games back counts half as much as the latest one.
RATE_HALF_LIFE = 12.0
MINUTES_HALF_LIFE = 5.0
# The season line counts as this many of the latest game. Role changes show
# up in minutes first, so minutes lean on the anchor less than rates do.
ANCHOR_GAMES = 10.0
MINUTES_ANCHOR_GAMES = 4.0


def recency_weights(count: int, half_life: float) -> list[float]:
    """Weights for games in date order, oldest first. The latest game is 1."""
    return [0.5 ** ((count - 1 - index) / half_life) for index in range(count)]


def anchor_from_row(row: dict) -> dict | None:
    """Season line as per-game makes and attempts. ``None`` without minutes."""
    minutes = _number(row.get("mp"))
    if minutes <= 0:
        return None
    anchor = {"mp": minutes, "dd": _number(row.get("dd"))}
    fga = _number(row.get("fga"))
    fta = _number(row.get("fta"))
    anchor["fga"] = fga
    anchor["fta"] = fta
    anchor["fgm"] = _number(row.get("fg_pct")) * fga
    anchor["ftm"] = _number(row.get("ft_pct")) * fta
    for column in ("fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf"):
        anchor[column] = _number(row.get(column))
    return anchor


def anchor_from_games(games: pd.DataFrame) -> dict | None:
    """Plain per-game average of a set of games, for a player with no season line."""
    if games.empty:
        return None
    anchor = {"mp": float(games["min"].mean()), "dd": float(games["dd"].mean())}
    if anchor["mp"] <= 0:
        return None
    for column in STAT_COLUMNS:
        anchor[column] = float(games[column].mean())
    return anchor


def project_line(anchor: dict | None, games: pd.DataFrame | None = None) -> dict | None:
    """Expected line for the next game. ``games`` are this season's, oldest first."""
    played = games if games is not None else pd.DataFrame()
    count = len(played)
    if anchor is None and count == 0:
        return None
    rate_weights = recency_weights(count, RATE_HALF_LIFE)
    minute_weights = recency_weights(count, MINUTES_HALF_LIFE)
    minutes_played = [float(value) for value in played["min"]] if count else []
    rate_anchor = ANCHOR_GAMES if anchor else 0.0
    minute_anchor = MINUTES_ANCHOR_GAMES if anchor else 0.0
    anchor_minutes = anchor["mp"] if anchor else 0.0

    weighted_minutes = sum(weight * value for weight, value in zip(rate_weights, minutes_played))
    rate_minutes = weighted_minutes + rate_anchor * anchor_minutes
    minutes = (
        sum(weight * value for weight, value in zip(minute_weights, minutes_played))
        + minute_anchor * anchor_minutes
    ) / (sum(minute_weights) + minute_anchor)

    line = {"mp": minutes}
    for column in STAT_COLUMNS:
        made = sum(weight * float(value) for weight, value in zip(rate_weights, played[column])) if count else 0.0
        made += rate_anchor * (anchor[column] if anchor else 0.0)
        line[column] = minutes * made / rate_minutes if rate_minutes else 0.0
    doubles = sum(weight * float(value) for weight, value in zip(rate_weights, played["dd"])) if count else 0.0
    doubles += rate_anchor * (anchor["dd"] if anchor else 0.0)
    line["dd"] = doubles / (sum(rate_weights) + rate_anchor)
    line["fg_pct"] = line["fgm"] / line["fga"] if line["fga"] else 0.0
    line["ft_pct"] = line["ftm"] / line["fta"] if line["fta"] else 0.0
    line["games"] = count
    return line


def score_lines(lines: list[dict], baselines: dict) -> list[dict]:
    """12-cat z for each line against the season pool. ``value`` is the plain sum."""
    if not lines:
        return []
    frame = pd.DataFrame(lines)
    frame["positions"] = ""
    scored = FantasyMathEngine().score_with_baselines(frame, baselines)
    results = []
    for _, row in scored.iterrows():
        z_scores = {category: round(float(row[f"z_{category}"]), 2) for category in ALL_CATEGORIES}
        results.append({"z": z_scores, "value": round(sum(z_scores.values()), 2)})
    return results


def _number(value: object) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)
