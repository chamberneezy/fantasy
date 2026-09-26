"""Load projections, rank them, and attach one fantasy week's game counts."""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from availability import GamesForecast, attach_games_forecast
from data_loader import NBAScheduleFetcher, ProjectionLoader
from math_engine import FantasyMathEngine
from rookies import ROOKIE_PATH, RookieBoard

ROOT = Path(__file__).resolve().parents[1]
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def main() -> None:
    warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

    loader = ProjectionLoader(ROOT / "data" / "projections.csv")
    engine = FantasyMathEngine()
    pool = engine.load_data(loader)
    ranked = attach_games_forecast(engine.get_ranked_players(), GamesForecast().build())
    top = ranked.head(5).copy()

    schedule = NBAScheduleFetcher().get_weekly_schedule_matrix("2026-27")
    week_start = schedule["week_start"].min()
    week = schedule.loc[schedule["week_start"] == week_start].set_index("team")

    print(f"Loaded {len(pool)} players")
    print(f"Fantasy week of {pd_date(week_start)} (Mon-Sun regular-season games)")
    print()
    print("Value ignores games played. Predicted games are there for the choice between similar players.")
    header = (
        f"{'Player':<28} {'Pos':<6} {'Tm':<5} {'Value':>7} {'Pred':>5} "
        + " ".join(f"{day:>3}" for day in WEEKDAYS)
        + f" {'Wk':>3}"
    )
    print(header)
    for _, player in top.iterrows():
        team = str(player.get("team", ""))
        counts = week.loc[team] if team in week.index else None
        day_counts = [int(counts[day]) if counts is not None else 0 for day in WEEKDAYS]
        games = int(counts["games"]) if counts is not None else 0
        days = " ".join(f"{count:>3}" for count in day_counts)
        predicted = player["predicted_games"]
        predicted_text = f"{int(predicted):>5}" if pd.notna(predicted) else "    -"
        print(
            f"{player['player_name']:<28} {player['positions']:<6} {team:<5} "
            f"{player['total_value']:>7.2f} {predicted_text} {days} {games:>3}"
        )

    print()
    print("Games history (blank = not in the league that season):")
    watch = ["Kawhi Leonard", "Paul George", "Joel Embiid", "Cooper Flagg"]
    watched = ranked[ranked["player_name"].isin(watch)]
    print(f"{'Player':<20} {'Value':>7} {'22':>4} {'23':>4} {'24':>4} {'25':>4} {'Pred':>5}")
    for _, player in watched.iterrows():
        print(
            f"{player['player_name']:<20} {player['total_value']:>7.2f} "
            f"{_gp(player['gp_2022']):>4} {_gp(player['gp_2023']):>4} "
            f"{_gp(player['gp_2024']):>4} {_gp(player['gp_2025']):>4} "
            f"{int(player['predicted_games']):>5}"
        )

    print()
    rookies = RookieBoard().load() if ROOKIE_PATH.exists() else RookieBoard().build(pool)
    translated = rookies[rookies["translation"] == "college_to_nba"]
    scored = engine.score_with_baselines(translated, engine.category_baselines())
    scored = scored.sort_values(["overall_pick"]).head(10)
    print("2026 rookies, college line translated onto the veteran scale. Games are the draft-slot forecast, not college games.")
    print(f"{'Pk':>3} {'Player':<22} {'Tm':<5} {'Value':>7} {'Pred':>5} {'PTS':>5} {'REB':>5} {'AST':>5}")
    for _, player in scored.iterrows():
        print(
            f"{int(player['overall_pick']):>3} {player['player_name']:<22} {player['team']:<5} "
            f"{player['total_value']:>7.2f} {int(player['predicted_games']):>5} "
            f"{player['pts']:>5.1f} {player['reb']:>5.1f} {player['ast']:>5.1f}"
        )


def _gp(value: object) -> str:
    if pd.isna(value):
        return "-"
    return str(int(value))


def pd_date(value: object) -> str:
    timestamp = getattr(value, "date", None)
    if callable(timestamp):
        return str(timestamp())
    return str(value)


if __name__ == "__main__":
    main()
