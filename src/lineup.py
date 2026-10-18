"""Who starts: the legal five for a day, and the week plan against an opponent.

Seats are strict: PG, SG, SF, PF, C. There is no G, F or UTIL in this league.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

import matchup

SEATS: tuple[str, ...] = ("PG", "SG", "SF", "PF", "C")
_BLOCKED = -1e9
# Added to every real player when the five must be filled, so an empty seat never wins.
_FILL = 1e4
PASSES = 2


def best_five(candidates: list[tuple[str, set[str], float]], must_fill: bool) -> dict[str, str]:
    """Seat → name for the highest total score. One seat per player.

    With ``must_fill`` every seat that can be filled is. Without it a player
    whose score is not above zero sits, even if that leaves a seat empty.
    """
    if not candidates:
        return {}
    width = len(candidates) + len(SEATS)
    scores = np.zeros((len(SEATS), width))
    for column, (_, positions, score) in enumerate(candidates):
        for row, seat in enumerate(SEATS):
            scores[row, column] = (score + (_FILL if must_fill else 0.0)) if seat in positions else _BLOCKED
    rows, columns = linear_sum_assignment(scores, maximize=True)
    chosen = {}
    for row, column in zip(rows, columns):
        if column < len(candidates) and scores[row, column] > 0:
            chosen[SEATS[row]] = candidates[column][0]
    return chosen


def by_value(day_entries: list[dict]) -> dict[str, str]:
    return best_five([(entry["name"], entry["positions"], entry["value"]) for entry in day_entries], must_fill=True)


def by_swing(day_entries: list[dict], weights: dict) -> dict[str, str]:
    scored = [
        (entry["name"], entry["positions"], sum(matchup.game_swing(entry, weights).values())) for entry in day_entries
    ]
    return best_five(scored, must_fill=False)


def started(by_day: dict[str, list[dict]], lineups: dict[str, dict[str, str]]) -> list[dict]:
    entries = []
    for day, day_entries in by_day.items():
        names = set(lineups.get(day, {}).values())
        entries.extend(entry for entry in day_entries if entry["name"] in names)
    return entries


def simulate(mine: list[dict], theirs: list[dict], runs: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return matchup.team_totals(mine, runs, rng), matchup.team_totals(theirs, runs, rng)


def plan_week(
    mine: dict[str, list[dict]],
    theirs: dict[str, list[dict]],
    today: str,
    runs: int = matchup.RUNS,
    seed: int = matchup.SEED,
) -> dict:
    """Pick my five for each day still to play, to win the most categories.

    The opponent is assumed to start his best legal five by value every day.
    Days already played keep the best-by-value five: the pad does not know
    who was really started. From today on, each game is scored by how much it
    moves the categories still in play, and the fives are picked on that.
    """
    their_lineups = {day: by_value(entries) for day, entries in theirs.items()}
    their_games = started(theirs, their_lineups)
    lineups = {day: by_value(entries) for day, entries in mine.items()}
    weights: dict = {}
    for _ in range(PASSES):
        my_totals, their_totals = simulate(started(mine, lineups), their_games, runs, seed)
        weights = matchup.swing_weights(my_totals, their_totals)
        for day, entries in mine.items():
            if day >= today:
                lineups[day] = by_swing(entries, weights)
    my_totals, their_totals = simulate(started(mine, lineups), their_games, runs, seed)
    return {
        "lineups": lineups,
        "their_lineups": their_lineups,
        "weights": weights,
        "result": matchup.compare(my_totals, their_totals),
        "their_games": their_games,
    }


def swing_total(by_day: dict[str, list[dict]], weights: dict, today: str) -> float:
    """Categories-won the best fives from today on add, at fixed weights."""
    total = 0.0
    for day, entries in by_day.items():
        if day < today:
            continue
        seated = set(by_swing(entries, weights).values())
        total += sum(sum(matchup.game_swing(entry, weights).values()) for entry in entries if entry["name"] in seated)
    return total
