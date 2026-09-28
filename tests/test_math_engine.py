"""Tests for 9-category z-scores and punt rankings."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from math_engine import ALL_CATEGORIES, DUAL_POSITION_MULTIPLIER, FantasyMathEngine

COLUMNS = [
    "player_name",
    "positions",
    "pts",
    "reb",
    "ast",
    "stl",
    "blk",
    "fg3m",
    "fg_pct",
    "fga",
    "ft_pct",
    "fta",
    "to",
    "mp",
    "pf",
    "dd",
]


def _player(name: str, positions: str = "C", **overrides: float) -> dict:
    row: dict = {
        "player_name": name,
        "positions": positions,
        "pts": 20.0,
        "reb": 5.0,
        "ast": 3.0,
        "stl": 1.0,
        "blk": 1.0,
        "fg3m": 1.0,
        "fg_pct": 0.50,
        "fga": 10.0,
        "ft_pct": 0.75,
        "fta": 5.0,
        "to": 2.0,
        "mp": 30.0,
        "pf": 2.0,
        "dd": 0.1,
    }
    row.update(overrides)
    return row


def _write_projections(path: Path, rows: list[dict]) -> Path:
    pd.DataFrame(rows, columns=COLUMNS).to_csv(path, index=False)
    return path


def _engine_from(path: Path, rows: list[dict]) -> tuple[FantasyMathEngine, pd.DataFrame]:
    engine = FantasyMathEngine()
    engine.load_data(_write_projections(path, rows))
    return engine, engine.calculate_z_scores(engine.df)


def test_counting_z_score_uses_population_std(tmp_path: Path) -> None:
    rows = [
        _player("A", pts=10),
        _player("B", pts=20),
        _player("C", pts=30),
    ]
    _, scored = _engine_from(tmp_path / "counting.csv", rows)

    pts = scored["pts"]
    expected = (pts - pts.mean()) / pts.std(ddof=0)
    pd.testing.assert_series_equal(
        scored["z_PTS"],
        expected,
        check_names=False,
    )
    assert (scored["z_REB"] == 0).all()


def test_turnover_z_score_is_inverted(tmp_path: Path) -> None:
    rows = [
        _player("A", to=1),
        _player("B", to=3),
        _player("C", to=5),
    ]
    _, scored = _engine_from(tmp_path / "turnovers.csv", rows)

    turnovers = scored["to"]
    raw_z = (turnovers - turnovers.mean()) / turnovers.std(ddof=0)
    pd.testing.assert_series_equal(
        scored["z_TO"],
        -1 * raw_z,
        check_names=False,
    )
    low_turnover = scored.loc[scored["player_name"] == "A", "z_TO"].iloc[0]
    high_turnover = scored.loc[scored["player_name"] == "C", "z_TO"].iloc[0]
    assert low_turnover > high_turnover


def test_fg_percentage_is_volume_weighted(tmp_path: Path) -> None:
    rows = [
        _player("Volume", fg_pct=0.55, fga=20),
        _player("Sniper", fg_pct=0.70, fga=4),
        _player("Average", fg_pct=0.48, fga=16),
        _player("Inefficient", fg_pct=0.40, fga=18),
    ]
    _, scored = _engine_from(tmp_path / "shooting.csv", rows)

    mean_fg = (scored["fg_pct"] * scored["fga"]).sum() / scored["fga"].sum()
    expected_impact = (scored["fg_pct"] - mean_fg) * scored["fga"]
    expected_z = (expected_impact - expected_impact.mean()) / expected_impact.std(ddof=0)

    pd.testing.assert_series_equal(
        scored["impact_FG%"],
        expected_impact,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        scored["z_FG%"],
        expected_z,
        check_names=False,
    )


def test_ft_punt_reverses_rankings(tmp_path: Path) -> None:
    rows = [
        _player("Ace", pts=21, ft_pct=0.95, fta=12),
        _player("Big", pts=28, ft_pct=0.50, fta=12),
        _player("Mid", pts=22, ft_pct=0.75, fta=6),
        _player("Role", pts=19, ft_pct=0.75, fta=6),
    ]
    engine, _ = _engine_from(tmp_path / "punts.csv", rows)

    baseline = engine.get_ranked_players()
    punted = engine.get_ranked_players(active_punts=["FT%"])

    base_order = baseline["player_name"].tolist()
    punt_order = punted["player_name"].tolist()
    assert base_order.index("Ace") < base_order.index("Big")
    assert punt_order.index("Big") < punt_order.index("Ace")

    base_ft = baseline.set_index("player_name")["z_FT%"].sort_index()
    punt_ft = punted.set_index("player_name")["z_FT%"].sort_index()
    pd.testing.assert_series_equal(base_ft, punt_ft)

    def summed_value(frame: pd.DataFrame, name: str, punts: list[str]) -> float:
        row = frame.loc[frame["player_name"] == name].iloc[0]
        kept = [f"z_{category}" for category in ALL_CATEGORIES if category not in punts]
        return float(row[kept].sum())

    ace_baseline = baseline.loc[baseline["player_name"] == "Ace"].iloc[0]
    ace_punted = punted.loc[punted["player_name"] == "Ace"].iloc[0]
    assert ace_baseline["total_value"] == pytest.approx(summed_value(baseline, "Ace", []))
    assert ace_punted["total_value"] == pytest.approx(summed_value(punted, "Ace", ["FT%"]))


def test_personal_foul_z_score_is_inverted(tmp_path: Path) -> None:
    rows = [
        _player("Clean", pf=1),
        _player("Average", pf=3),
        _player("Hack", pf=5),
    ]
    _, scored = _engine_from(tmp_path / "fouls.csv", rows)
    clean = scored.loc[scored["player_name"] == "Clean", "z_PF"].iloc[0]
    hack = scored.loc[scored["player_name"] == "Hack", "z_PF"].iloc[0]
    assert clean > hack


def test_unknown_punt_raises(tmp_path: Path) -> None:
    engine, _ = _engine_from(tmp_path / "unknown.csv", [_player("A"), _player("B", pts=25)])
    with pytest.raises(ValueError, match="Unknown punt categories"):
        engine.get_ranked_players(active_punts=["FT%", "PIP"])


def test_seed_projections_rank_player_pool() -> None:
    engine = FantasyMathEngine()
    loaded = engine.load_data(ROOT / "data" / "projections.csv")
    assert len(loaded) > 400
    assert loaded["player_name"].is_unique
    required = [column for column in COLUMNS if column != "dd"]
    assert set(required).issubset(loaded.columns)

    ranked = engine.get_ranked_players()
    assert len(ranked) == len(loaded)
    assert ranked["total_value"].is_monotonic_decreasing
    assert ranked["total_value"].notna().all()

    for _, row in ranked.iterrows():
        z_sum = sum(row[f"z_{category}"] for category in ALL_CATEGORIES)
        multiplier = DUAL_POSITION_MULTIPLIER if "/" in str(row["positions"]) else 1.0
        assert row["total_value"] == pytest.approx(z_sum * multiplier)

    punted = engine.get_ranked_players(active_punts=["FT%"])
    assert punted["total_value"].is_monotonic_decreasing
    assert len(punted) == len(loaded)
