"""College lines translate onto the veteran scale without moving veteran ranks."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from math_engine import FantasyMathEngine
from rookies import fit_translation, predict_rookie_games, translate_college_line


def test_translation_scales_counting_stats_and_shifts_percentages() -> None:
    pairs = pd.DataFrame(
        {
            "college_pts": [20, 10, 30, 16, 24],
            "nba_pts": [10, 5, 15, 8, 12],
            "college_reb": [10, 8, 6, 4, 12],
            "nba_reb": [5, 4, 3, 2, 6],
            "college_ast": [4, 4, 4, 4, 4],
            "nba_ast": [2, 2, 2, 2, 2],
            "college_stl": [2, 2, 2, 2, 2],
            "nba_stl": [1, 1, 1, 1, 1],
            "college_blk": [1, 1, 1, 1, 1],
            "nba_blk": [0.5, 0.5, 0.5, 0.5, 0.5],
            "college_fg3m": [2, 2, 2, 2, 2],
            "nba_fg3m": [1, 1, 1, 1, 1],
            "college_fga": [16, 16, 16, 16, 16],
            "nba_fga": [8, 8, 8, 8, 8],
            "college_fta": [6, 6, 6, 6, 6],
            "nba_fta": [3, 3, 3, 3, 3],
            "college_to": [3, 3, 3, 3, 3],
            "nba_to": [1.5, 1.5, 1.5, 1.5, 1.5],
            "college_fg_pct": [0.50, 0.48, 0.52, 0.46, 0.54],
            "nba_fg_pct": [0.45, 0.43, 0.47, 0.41, 0.49],
            "college_ft_pct": [0.80, 0.78, 0.82, 0.76, 0.84],
            "nba_ft_pct": [0.75, 0.73, 0.77, 0.71, 0.79],
        }
    )
    ratios, deltas = fit_translation(pairs)
    line = translate_college_line(
        {"pts": 20, "reb": 10, "ast": 4, "stl": 2, "blk": 1, "fg3m": 2, "fga": 16, "fta": 6, "to": 3, "fg_pct": 0.50, "ft_pct": 0.80},
        ratios,
        deltas,
    )
    assert line["pts"] == 10
    assert line["fg_pct"] == 0.45
    assert line["ft_pct"] == 0.75


def test_rookie_games_follow_the_draft_slot_not_a_fixed_season() -> None:
    bands = {"1-5": 70, "6-14": 62, "15-30": 48, "31-45": 35, "46-60": 20}
    assert predict_rookie_games(1, bands) == 70
    assert predict_rookie_games(28, bands) == 48
    assert predict_rookie_games(55, bands) == 20


def test_scoring_a_rookie_does_not_change_the_veteran_board(tmp_path: Path) -> None:
    pool = pd.DataFrame(
        [
            {"player_name": "Star", "positions": "C", "pts": 30, "reb": 12, "ast": 8, "stl": 1.5, "blk": 1.2, "fg3m": 1, "fg_pct": 0.55, "fga": 20, "ft_pct": 0.85, "fta": 8, "to": 3},
            {"player_name": "Wing", "positions": "SF", "pts": 22, "reb": 6, "ast": 4, "stl": 1.2, "blk": 0.5, "fg3m": 2.5, "fg_pct": 0.46, "fga": 18, "ft_pct": 0.84, "fta": 5, "to": 2},
            {"player_name": "Guard", "positions": "PG", "pts": 14, "reb": 3, "ast": 7, "stl": 1.1, "blk": 0.2, "fg3m": 2, "fg_pct": 0.43, "fga": 13, "ft_pct": 0.88, "fta": 3, "to": 2.4},
        ]
    )
    engine = FantasyMathEngine()
    engine.load_data(pool)
    before = engine.get_ranked_players()
    rookie = pd.DataFrame(
        [
            {"player_name": "Prospect", "positions": "SF", "pts": 16, "reb": 6, "ast": 3, "stl": 1, "blk": 0.6, "fg3m": 1.5, "fg_pct": 0.45, "fga": 14, "ft_pct": 0.78, "fta": 4, "to": 2},
        ]
    )
    scored = engine.score_with_baselines(rookie, engine.category_baselines())
    after = engine.get_ranked_players()
    assert after["total_value"].tolist() == before["total_value"].tolist()
    assert "total_value" in scored.columns
