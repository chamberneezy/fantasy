"""One fantasy week, simulated: both teams' totals in the 12 cats and who wins each.

A player-game is drawn from that player's own past games, rescaled so the
average equals tonight's expected line. That keeps the real spread and the
real ties between stats (shots and makes, points and turnovers). A player
with no past games is drawn around his line instead.
"""

from __future__ import annotations

import math

import numpy as np

from math_engine import ALL_CATEGORIES, NEGATIVE_CATEGORIES

STATS: tuple[str, ...] = ("mp", "fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd")
AT = {stat: index for index, stat in enumerate(STATS)}
COUNTING = {"MIN": "mp", "3PM": "fg3m", "PTS": "pts", "REB": "reb", "AST": "ast", "STL": "stl", "BLK": "blk", "TO": "to", "PF": "pf", "DD": "dd"}
RATIOS = {"FG%": ("fgm", "fga"), "FT%": ("ftm", "fta")}
RUNS = 20000
SEED = 51867


def line_vector(line: dict) -> np.ndarray:
    return np.array([float(line.get(stat) or 0.0) for stat in STATS])


def draw(entry: dict, runs: int, rng: np.random.Generator) -> np.ndarray:
    """``runs`` versions of one player-game, as rows of ``STATS``."""
    if entry.get("fixed") is not None:
        return np.tile(entry["fixed"], (runs, 1))
    mean = entry["mean"]
    history = entry.get("hist")
    if history is not None and len(history):
        typical = history.mean(axis=0)
        scale = np.divide(mean, typical, out=np.zeros_like(mean), where=typical > 0)
        games = history[rng.integers(0, len(history), runs)] * scale
        games[:, typical <= 0] = mean[typical <= 0]
    else:
        games = rng.poisson(np.tile(mean, (runs, 1))).astype(float)
        games[:, AT["mp"]] = mean[AT["mp"]]
        for made, tried in RATIOS.values():
            rate = mean[AT[made]] / mean[AT[tried]] if mean[AT[tried]] else 0.0
            games[:, AT[made]] = rng.binomial(games[:, AT[tried]].astype(int), min(1.0, rate))
        games[:, AT["dd"]] = rng.random(runs) < mean[AT["dd"]]
    plays = rng.random(runs) < entry.get("p", 1.0)
    return games * plays[:, None]


def team_totals(entries: list[dict], runs: int, rng: np.random.Generator) -> np.ndarray:
    totals = np.zeros((runs, len(STATS)))
    for entry in entries:
        totals += draw(entry, runs, rng)
    return totals


def category_values(totals: np.ndarray) -> dict[str, np.ndarray]:
    values = {category: totals[:, AT[stat]] for category, stat in COUNTING.items()}
    for category, (made, tried) in RATIOS.items():
        attempts = totals[:, AT[tried]]
        values[category] = np.divide(totals[:, AT[made]], attempts, out=np.zeros(len(totals)), where=attempts > 0)
    return values


def compare(mine: np.ndarray, theirs: np.ndarray) -> dict:
    """Chance of each category and of the week. A tied category is half a win."""
    my_values = category_values(mine)
    their_values = category_values(theirs)
    runs = len(mine)
    won = np.zeros(runs)
    lost = np.zeros(runs)
    cats = []
    for category in ALL_CATEGORIES:
        sign = -1.0 if category in NEGATIVE_CATEGORIES else 1.0
        gap = sign * (my_values[category] - their_values[category])
        ahead = gap > 1e-9
        behind = gap < -1e-9
        won += ahead
        lost += behind
        cats.append(
            {
                "cat": category,
                "mine": float(my_values[category].mean()),
                "theirs": float(their_values[category].mean()),
                "win": float(ahead.mean()),
                "tie": float(1.0 - ahead.mean() - behind.mean()),
            }
        )
    return {
        "cats": cats,
        "expected": float(sum(row["win"] + 0.5 * row["tie"] for row in cats)),
        "win": float((won > lost).mean()),
        "tie": float((won == lost).mean()),
        "lose": float((won < lost).mean()),
    }


def swing_weights(mine: np.ndarray, theirs: np.ndarray) -> dict:
    """How much one more unit of each stat moves the chance of its category.

    A category already won or lost by a mile weighs nothing; a coin-flip one
    weighs most. Shooting categories also carry my rate and my attempts, so a
    game can be scored by makes above or below that rate.
    """
    my_values = category_values(mine)
    their_values = category_values(theirs)
    weights: dict = {}
    for category in ALL_CATEGORIES:
        sign = -1.0 if category in NEGATIVE_CATEGORIES else 1.0
        gap = sign * (my_values[category] - their_values[category])
        spread = float(gap.std())
        if spread <= 0:
            weights[category] = 0.0
            continue
        centre = float(gap.mean()) / spread
        weights[category] = sign * math.exp(-0.5 * centre * centre) / (spread * math.sqrt(2 * math.pi))
    for category, (made, tried) in RATIOS.items():
        attempts = float(mine[:, AT[tried]].mean())
        weights[f"{category} rate"] = float(mine[:, AT[made]].mean()) / attempts if attempts else 0.0
        weights[f"{category} attempts"] = attempts
    return weights


def game_swing(entry: dict, weights: dict) -> dict[str, float]:
    """Categories-won this one player-game adds, by category. Negative means it costs."""
    mean = entry["mean"]
    chance = entry.get("p", 1.0)
    swing = {category: chance * weights[category] * mean[AT[stat]] for category, stat in COUNTING.items()}
    for category, (made, tried) in RATIOS.items():
        attempts = weights[f"{category} attempts"]
        above = mean[AT[made]] - weights[f"{category} rate"] * mean[AT[tried]]
        swing[category] = chance * weights[category] * above / attempts if attempts else 0.0
    return swing
