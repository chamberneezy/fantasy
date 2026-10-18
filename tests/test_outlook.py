"""Season outlook: totals, features across seasons, and a fit that recovers a known rule."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import outlook

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25"]


def _totals(points_per_minute: dict[int, list[float | None]], minutes: float = 2000.0, games: float = 70.0) -> pd.DataFrame:
    rows = []
    for player_id, by_season in points_per_minute.items():
        for season, rate in zip(SEASONS, by_season):
            if rate is None:
                continue
            row = {"season": season, "player_id": player_id, "min": minutes, "g": games}
            row.update({stat: 0.1 * minutes for stat in outlook.RATE_STATS})
            row["pts"] = rate * minutes
            rows.append(row)
    return pd.DataFrame(rows)


def _ages(player_ids, age: float = 26.0) -> pd.DataFrame:
    return pd.DataFrame([{"season": season, "player_id": player_id, "age": age} for season in SEASONS for player_id in player_ids])


def test_season_totals_sum_games_and_stats() -> None:
    logs = pd.DataFrame(
        [{"season": "2024-25", "player_id": 1, "min": 30.0, **{stat: 2.0 for stat in outlook.RATE_STATS}}] * 3
    )
    totals = outlook.season_totals(logs)
    assert totals.loc[0, "g"] == 3
    assert totals.loc[0, "min"] == 90.0
    assert totals.loc[0, "pts"] == 6.0


def test_a_missed_older_season_repeats_the_nearest_one() -> None:
    totals = _totals({1: [None, None, 0.5, 0.6], 2: [0.4, 0.4, 0.4, 0.4]})
    table = outlook.feature_table(totals, _ages([1, 2]), "2024-25", SEASONS).set_index("player_id")
    assert table.loc[1, "g2"] == 0.0 and table.loc[1, "g3"] == 0.0
    assert table.loc[1, "r2_pts"] == table.loc[1, "r1_pts"] == table.loc[1, "r3_pts"]
    assert table.loc[1, "mpg"] == pytest.approx(2000.0 / 70.0)
    assert table.loc[1, "y_pts"] == pytest.approx(0.6)
    # Age is last season's plus one.
    assert table.loc[1, "age"] == 27.0


def test_short_seasons_are_left_out() -> None:
    totals = _totals({1: [0.5, 0.5, 0.5, 0.5]}, minutes=200.0, games=10.0)
    assert outlook.feature_table(totals, _ages([1]), "2024-25", SEASONS).empty


def test_fit_recovers_a_scorer_who_repeats_and_beats_nothing_it_should_not() -> None:
    rng = np.random.default_rng(0)
    rates = {player_id: [float(rate)] * 4 for player_id, rate in enumerate(rng.uniform(0.2, 0.9, 60), start=1)}
    totals = _totals(rates)
    ages = _ages(rates)
    model = outlook.fit(totals, ages, ["2023-24", "2024-25"], SEASONS)
    table = outlook.feature_table(totals, ages, "2024-25", SEASONS)
    lines = outlook.project(model, table)
    truth = np.array([rates[player_id][3] for player_id in table["player_id"]]) * (2000.0 / 70.0)
    assert np.abs(lines["pts"].to_numpy() - truth).max() < 0.05
    assert lines["mp"].to_numpy() == pytest.approx(2000.0 / 70.0, abs=0.05)
    scored = outlook.score(lines, table)
    assert scored.loc["pts", "error"] < 0.05
    same = outlook.score(outlook.naive(table, totals, "2023-24"), table)
    assert same.loc["pts", "error"] == pytest.approx(0.0, abs=1e-9)


def test_projection_for_an_unplayed_season_has_no_answers_but_has_lines() -> None:
    rates = {player_id: [0.5, 0.5, 0.5, 0.5] for player_id in range(1, 30)}
    rates[30] = [0.3, 0.4, 0.5, 0.6]
    totals = _totals(rates)
    ages = _ages(rates)
    model = outlook.fit(totals, ages, ["2023-24", "2024-25"], SEASONS)
    table = outlook.feature_table(totals, ages, "2025-26", SEASONS)
    assert "mpg" not in table.columns
    lines = outlook.project(model, table)
    assert len(lines) == 30
    assert lines["pts"].notna().all() and (lines["mp"] > 0).all()


def test_blend_is_halfway_and_recomputes_shooting() -> None:
    model = pd.DataFrame([{"player_id": 1, "mp": 30.0, **{stat: 4.0 for stat in outlook.RATE_STATS}}])
    last = pd.DataFrame([{"player_id": 1, "mp": 34.0, **{stat: 8.0 for stat in outlook.RATE_STATS}}])
    last["fgm"] = 4.0
    mixed = outlook.blend(model, last, share=0.5)
    assert mixed.loc[0, "mp"] == 32.0
    assert mixed.loc[0, "pts"] == 6.0
    assert mixed.loc[0, "fg_pct"] == pytest.approx(4.0 / 6.0)
