"""Games-played forecasts stay out of the draft score."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from availability import attach_games_forecast, predict_games
from math_engine import FantasyMathEngine


def test_prediction_lands_between_recent_seasons() -> None:
    history = pd.DataFrame(
        [
            {"player_name": "Kawhi Leonard", "season": "2023-24", "gp": 50},
            {"player_name": "Kawhi Leonard", "season": "2024-25", "gp": 52},
            {"player_name": "Kawhi Leonard", "season": "2025-26", "gp": 60},
        ]
    )
    forecast = predict_games(history)
    predicted = int(forecast.loc[0, "predicted_games"])
    assert 50 <= predicted <= 60
    assert forecast.loc[0, "gp_2022"] is pd.NA or pd.isna(forecast.loc[0, "gp_2022"])


def test_missing_season_is_not_counted_as_zero() -> None:
    history = pd.DataFrame(
        [
            {"player_name": "Steady", "season": "2025-26", "gp": 75},
        ]
    )
    forecast = predict_games(history)
    assert int(forecast.loc[0, "predicted_games"]) == 75


def test_forecast_does_not_change_rank_or_value(tmp_path: Path) -> None:
    rows = [
        "player_name,positions,pts,reb,ast,stl,blk,fg3m,fg_pct,fga,ft_pct,fta,to",
        "Star,C,30,12,8,1.5,1.2,1,0.55,20,0.85,8,3",
        "Fragile,SF,28,7,4,1.6,0.6,2,0.50,19,0.88,6,2",
        "Role,PG,14,3,6,1,0.2,2,0.44,12,0.80,3,2",
    ]
    path = tmp_path / "pool.csv"
    path.write_text("\n".join(rows))
    engine = FantasyMathEngine()
    engine.load_data(path)
    ranked = engine.get_ranked_players()

    forecast = predict_games(
        pd.DataFrame(
            [
                {"player_name": "Star", "season": "2025-26", "gp": 70},
                {"player_name": "Fragile", "season": "2024-25", "gp": 30},
                {"player_name": "Fragile", "season": "2025-26", "gp": 35},
                {"player_name": "Role", "season": "2025-26", "gp": 80},
            ]
        )
    )
    combined = attach_games_forecast(ranked, forecast)
    assert combined["player_name"].tolist() == ranked["player_name"].tolist()
    assert combined["total_value"].tolist() == ranked["total_value"].tolist()
    fragile = combined.loc[combined["player_name"] == "Fragile"].iloc[0]
    role = combined.loc[combined["player_name"] == "Role"].iloc[0]
    assert int(fragile["predicted_games"]) < int(role["predicted_games"])
