"""Season schedule: fantasy weeks, the week grid, back-to-backs."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_feed import shape_logs, shape_schedule
from schedule import fantasy_weeks, nba_team, team_games, week_for, week_grid


def _schedule() -> pd.DataFrame:
    rows = [
        ("0022600001", "2026-10-20", "2026-10-20T23:30:00Z", "DEN", "UTA"),
        ("0022600002", "2026-10-21", "2026-10-22T02:00:00Z", "LAL", "DEN"),
        ("0022600003", "2026-10-23", "2026-10-23T23:00:00Z", "DEN", "BOS"),
        ("0022600004", "2026-10-23", "2026-10-24T00:00:00Z", "UTA", "PHX"),
        ("0022600005", "2026-10-26", "2026-10-26T23:00:00Z", "BOS", "UTA"),
        ("0022600006", "2026-11-01", "2026-11-01T23:00:00Z", "DEN", "PHX"),
    ]
    frame = pd.DataFrame(rows, columns=["game_id", "date", "tip_utc", "home", "away"])
    frame["label"] = ""
    return frame


def test_default_weeks_open_short_then_run_monday_to_sunday() -> None:
    weeks = fantasy_weeks(_schedule())
    assert weeks[0] == {"week": 1, "start": date(2026, 10, 20), "end": date(2026, 10, 25)}
    assert weeks[1] == {"week": 2, "start": date(2026, 10, 26), "end": date(2026, 11, 1)}
    assert len(weeks) == 2
    assert week_for(date(2026, 10, 25), weeks)["week"] == 1
    assert week_for(date(2026, 10, 26), weeks)["week"] == 2
    assert week_for(date(2026, 10, 5), weeks)["week"] == 1
    assert week_for(date(2027, 6, 1), weeks)["week"] == 2


def test_yahoo_week_file_replaces_the_default() -> None:
    yahoo = pd.DataFrame(
        [{"week": 1, "start": "2026-10-20", "end": "2026-11-01"}, {"week": 2, "start": "2026-11-02", "end": "2026-11-08"}]
    )
    weeks = fantasy_weeks(_schedule(), yahoo)
    assert weeks[0]["end"] == date(2026, 11, 1)
    assert week_for(date(2026, 10, 28), weeks)["week"] == 1


def test_team_games_mark_the_second_night_only() -> None:
    games = team_games(_schedule(), "DEN", date(2026, 10, 20), date(2026, 10, 25))
    assert [(game["date"], game["opp"], game["home"], game["b2b"]) for game in games] == [
        ("2026-10-20", "UTA", True, False),
        ("2026-10-21", "LAL", False, True),
        ("2026-10-23", "BOS", True, False),
    ]
    assert team_games(_schedule(), "", date(2026, 10, 20), date(2026, 10, 25)) == []


def test_reference_team_codes_map_to_the_nba_feed() -> None:
    assert nba_team("PHO") == "PHX"
    assert nba_team("BRK") == "BKN"
    assert nba_team("CHO") == "CHA"
    assert nba_team("DEN") == "DEN"
    assert nba_team(None) == ""
    assert len(team_games(_schedule(), "PHO", date(2026, 10, 20), date(2026, 11, 1))) == 2


def test_week_grid_counts_games_left_and_crowded_days() -> None:
    schedule = _schedule()
    weeks = fantasy_weeks(schedule)
    roster = [{"player_name": f"Nugget {n}", "team": "DEN"} for n in range(6)]
    roster.append({"player_name": "Jazz", "team": "UTA"})
    roster.append({"player_name": "Nobody", "team": ""})
    grid = week_grid(schedule, roster, weeks[0], today=date(2026, 10, 21))
    assert [day["date"] for day in grid["days"]][0] == "2026-10-20"
    assert len(grid["days"]) == 6
    by_date = {day["date"]: day for day in grid["days"]}
    assert by_date["2026-10-20"]["mine"] == 7
    assert by_date["2026-10-20"]["over"] is True
    assert by_date["2026-10-20"]["past"] is True
    assert by_date["2026-10-21"]["mine"] == 6
    assert by_date["2026-10-22"]["mine"] == 0
    assert by_date["2026-10-22"]["open"] is True
    assert by_date["2026-10-23"]["league_games"] == 2
    nugget = grid["rows"][0]
    assert nugget["games"] == 3
    assert nugget["left"] == 2
    assert grid["rows"][-1]["games"] == 0
    # Oct 21 and Oct 23 remain: six and seven with a game, five seats each night.
    assert grid["starts_left"] == 10


def test_feed_keeps_regular_season_games_with_both_teams() -> None:
    raw = pd.DataFrame(
        {
            "gameId": ["0012600001", "0022600010", "0022600011", "0062600001"],
            "gameDateEst": ["2026-10-03T00:00:00Z", "2026-10-24T00:00:00Z", "2026-12-08T00:00:00Z", "2026-12-11T00:00:00Z"],
            "gameDateTimeUTC": ["2026-10-03T23:00:00Z", "2026-10-25T00:00:00Z", "2026-12-09T00:00:00Z", "2026-12-12T01:30:00Z"],
            "homeTeam_teamTricode": ["TOR", "DAL", None, None],
            "awayTeam_teamTricode": ["MIA", "SAS", None, None],
            "postponedStatus": ["N", "N", "N", "N"],
            "gameLabel": ["Preseason", "", "Emirates NBA Cup", "Emirates NBA Cup"],
        }
    )
    shaped = shape_schedule(raw)
    assert shaped["game_id"].tolist() == ["0022600010"]
    # A 20:00 Eastern tip is the next day in UTC. The fantasy day stays Eastern.
    assert shaped.iloc[0]["date"] == "2026-10-24"
    assert shaped.iloc[0]["tip_utc"] == "2026-10-25T00:00:00Z"


def test_feed_logs_read_side_and_opponent_and_skip_dnp() -> None:
    raw = pd.DataFrame(
        {
            "PLAYER_ID": [1, 1, 1],
            "PLAYER_NAME": ["A B"] * 3,
            "TEAM_ABBREVIATION": ["DEN"] * 3,
            "GAME_ID": ["0022600001", "0022600002", "0022600003"],
            "GAME_DATE": ["2026-10-20T00:00:00", "2026-10-21T00:00:00", "2026-10-23T00:00:00"],
            "MATCHUP": ["DEN vs. UTA", "DEN @ LAL", "DEN vs. BOS"],
            "MIN": [30.5, 0.0, 28.0],
            **{col: [1, 0, 2] for col in ("FGM", "FGA", "FTM", "FTA", "FG3M", "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "DD2")},
        }
    )
    shaped = shape_logs(raw)
    assert shaped["date"].tolist() == ["2026-10-20", "2026-10-23"]
    assert shaped["opp"].tolist() == ["UTA", "BOS"]
    assert shaped["home"].tolist() == [1, 1]
    assert shaped["to"].tolist() == [1.0, 2.0]
