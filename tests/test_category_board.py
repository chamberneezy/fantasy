import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import category_board as board  # noqa: E402
import matchup  # noqa: E402
from math_engine import ALL_CATEGORIES  # noqa: E402


def _logs(rows: list[dict]) -> pd.DataFrame:
    base = {"date": "2026-10-20", "min": 30.0, "fgm": 5, "fga": 10, "ftm": 2, "fta": 2, "fg3m": 1, "pts": 13.0, "reb": 4.0, "ast": 3.0, "stl": 1.0, "blk": 0.0, "to": 2.0, "pf": 2.0, "dd": 0}
    return pd.DataFrame([{**base, **row} for row in rows])


def _three_players() -> pd.DataFrame:
    rows = []
    for day in ("2026-10-20", "2026-10-21", "2026-10-22"):
        rows.append({"player_name": "Careful", "date": day, "to": 0.0, "pf": 0.0, "stl": 3.0})
        rows.append({"player_name": "Scorer", "date": day, "pts": 30.0, "to": 5.0, "pf": 5.0})
        rows.append({"player_name": "Middle", "date": day})
    return _logs(rows)


def test_value_is_the_plain_sum_of_all_twelve_categories() -> None:
    values = board.player_values(_three_players(), {"Careful": "A", "Scorer": "B", "Middle": "A"})
    row = values[values["player_name"] == "Scorer"].iloc[0]
    assert row["total"] == pytest.approx(sum(row[f"z_{category}"] for category in ALL_CATEGORIES))


def test_points_do_not_beat_the_other_categories() -> None:
    values = board.player_values(_three_players(), {"Careful": "A", "Scorer": "B", "Middle": "A"}).set_index("player_name")
    assert values.loc["Careful", "z_TO"] > 0 > values.loc["Scorer", "z_TO"]
    assert values.loc["Careful", "z_PF"] > 0 > values.loc["Scorer", "z_PF"]
    assert values.loc["Scorer", "rank_PTS"] == 1
    assert values.loc["Careful", "rank_STL"] == 1


def test_free_agent_is_scored_against_rostered_without_moving_their_ranks() -> None:
    logs = _three_players()
    logs = pd.concat([logs, _logs([{"player_name": "Free", "date": day, "pts": 50.0} for day in ("2026-10-20", "2026-10-21", "2026-10-22")])], ignore_index=True)
    rostered = {"Careful": "A", "Scorer": "B", "Middle": "A"}
    alone = board.player_values(_three_players(), rostered).set_index("player_name")
    joined = board.player_values(logs, rostered, extra=["Free"]).set_index("player_name")
    assert joined.loc["Free", "team"] == ""
    for name in rostered:
        assert joined.loc[name, "rank"] == alone.loc[name, "rank"]


def test_too_few_games_are_not_ranked() -> None:
    logs = _three_players().iloc[:-1]
    values = board.player_values(logs, {"Careful": "A", "Scorer": "B", "Middle": "A"})
    assert "Middle" not in set(values["player_name"])


def test_team_values_rank_each_category() -> None:
    values = board.player_values(_three_players(), {"Careful": "A", "Scorer": "B", "Middle": "A"})
    teams = board.team_values(values)
    assert teams.loc["B", "rank_PTS"] == 1
    assert teams.loc["A", "rank_TO"] == 1


def test_fair_chance_pulls_toward_even_and_keeps_order() -> None:
    assert board.fair_chance(0.9) < 0.9
    assert board.fair_chance(0.1) > 0.1
    assert board.fair_chance(0.5) == pytest.approx(0.5)
    assert board.fair_chance(0.8) < board.fair_chance(0.9)


def test_category_word_names_locked_and_gone() -> None:
    assert board.category_word(1.0) == "locked yours"
    assert board.category_word(0.0) == "gone"
    assert board.category_word(0.5) == "coin flip"
    assert "his" not in board.category_word(0.2)


def test_day_grid_shows_bench_games_and_empty_seats() -> None:
    entries = [{"name": name, "p": 1.0} for name in ("A", "B")]
    grid = board.day_grid({"2026-11-05": entries}, {"2026-11-05": {"PG": "A"}})[0]
    assert (grid["plays"], grid["starts"]) == (2, 1)
    assert grid["sits"] == ["B"]
    assert grid["empty"] == ["SG", "SF", "PF", "C"]


def _totals(**stats: float) -> np.ndarray:
    vector = np.zeros(len(matchup.STATS))
    for stat, value in stats.items():
        vector[matchup.AT[stat]] = value
    return vector


def test_category_results_count_low_turnovers_as_a_win_and_ties_as_half() -> None:
    results = board.category_results(_totals(to=10.0, pts=5.0, reb=7.0), _totals(to=20.0, pts=9.0, reb=7.0))
    assert results["TO"] == 1.0
    assert results["PTS"] == 0.0
    assert results["REB"] == 0.5


def test_grade_uses_the_first_forecast_of_the_week() -> None:
    forecasts = pd.DataFrame(
        [
            {"made_on": "2026-11-02", "week": 3, "opponent": "X", "cat": "PTS", "chance": 0.9, "fair": 0.8},
            {"made_on": "2026-11-03", "week": 3, "opponent": "X", "cat": "PTS", "chance": 0.1, "fair": 0.2},
        ]
    )
    graded = board.grade_forecasts(forecasts, {3: {"PTS": 1.0}})
    assert graded.iloc[0]["made_on"] == "2026-11-02"
    assert graded.iloc[0]["brier"] == pytest.approx(0.04)


def test_record_forecast_replaces_the_same_morning(tmp_path) -> None:
    path = tmp_path / "forecasts.csv"
    report = {"date": "2026-11-02", "week": 3, "opponent": "X", "categories": [{"cat": "PTS", "chance": 0.6, "fair": 0.56}]}
    board.record_forecast(path, report)
    report["categories"][0]["chance"] = 0.7
    board.record_forecast(path, report)
    saved = pd.read_csv(path)
    assert len(saved) == 1
    assert saved.iloc[0]["chance"] == 0.7


def test_free_agents_appear_once_whatever_the_spellings() -> None:
    class Data:
        free_agents = {"Tristan da Silva": {"player_name": "Tristan da Silva", "yahoo_status": ""}, "tristan da silva": {"player_name": "Tristan da Silva", "yahoo_status": ""}, "Out Guy": {"player_name": "Out Guy", "yahoo_status": "O"}, "Gone Guy": {"player_name": "Gone Guy", "yahoo_status": ""}}
        logs = pd.DataFrame({"team": ["ORL"] * 5, "date": ["2026-10-21", "2026-10-23", "2026-10-25", "2026-10-28", "2026-10-30"]})

        def line_for(self, name: str) -> dict:
            return {"value": 1.0}

        def season_games(self, name: str) -> pd.DataFrame:
            return self.logs.head(3) if name == "Gone Guy" else self.logs.tail(3)

        def positions_for(self, name: str) -> tuple[str, bool]:
            return "SF/PF", True

        def team_of(self, name: str) -> str:
            return "ORL"

    class Session:
        data = Data()

    assert board.free_agents(Session()) == [("Tristan da Silva", "SF/PF", "ORL")]
