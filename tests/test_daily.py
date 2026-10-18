"""Daily line: recency, the season anchor, and the season pad's day card."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import daily
import nba_feed
import season_data
from daily import anchor_from_games, anchor_from_row, project_line, recency_weights
from draft_room import build_pool
from season import SeasonSession

ANCHOR_ROW = {
    "mp": 30.0, "pts": 15.0, "reb": 6.0, "ast": 3.0, "stl": 1.0, "blk": 0.5, "fg3m": 1.5,
    "to": 2.0, "pf": 2.5, "dd": 0.2, "fg_pct": 0.5, "fga": 12.0, "ft_pct": 0.8, "fta": 5.0,
}


def _games(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in (*daily.STAT_COLUMNS, "min", "dd"):
        if column not in frame.columns:
            frame[column] = 0.0
    return frame


def test_recency_weights_halve_at_the_half_life() -> None:
    weights = recency_weights(13, 12.0)
    assert weights[-1] == 1.0
    assert weights[0] == pytest.approx(0.5)
    assert weights == sorted(weights)
    assert recency_weights(0, 12.0) == []


def test_no_games_returns_the_season_line() -> None:
    line = project_line(anchor_from_row(ANCHOR_ROW))
    assert line["mp"] == pytest.approx(30.0)
    assert line["pts"] == pytest.approx(15.0)
    assert line["fgm"] == pytest.approx(6.0)
    assert line["ftm"] == pytest.approx(4.0)
    assert line["fg_pct"] == pytest.approx(0.5)
    assert line["dd"] == pytest.approx(0.2)
    assert line["games"] == 0


def test_no_anchor_and_no_games_is_no_line() -> None:
    assert project_line(None) is None
    assert anchor_from_row({"mp": 0, "pts": 10}) is None
    assert anchor_from_games(_games([]).iloc[0:0]) is None


def test_one_game_blends_minutes_and_rates_with_the_anchor() -> None:
    game = _games([{"min": 20.0, "pts": 20.0, "fgm": 8.0, "fga": 10.0, "dd": 1.0}])
    line = project_line(anchor_from_row(ANCHOR_ROW), game)
    # Minutes: (20 + 4 anchor games x 30) / 5.
    assert line["mp"] == pytest.approx(28.0)
    # Points per minute: (20 + 10 x 15) / (20 + 10 x 30), times 28 minutes.
    assert line["pts"] == pytest.approx(28.0 * 170.0 / 320.0)
    assert line["fg_pct"] == pytest.approx((8.0 + 60.0) / (10.0 + 120.0))
    assert line["dd"] == pytest.approx((1.0 + 10 * 0.2) / 11.0)
    assert line["games"] == 1


def test_latest_games_outweigh_older_ones() -> None:
    rising = _games([{"min": 30.0, "pts": 10.0}] * 10 + [{"min": 30.0, "pts": 30.0}] * 10)
    falling = _games([{"min": 30.0, "pts": 30.0}] * 10 + [{"min": 30.0, "pts": 10.0}] * 10)
    up = project_line(None, rising)["pts"]
    down = project_line(None, falling)["pts"]
    assert up > 20.0 > down
    assert up + down == pytest.approx(40.0)


def test_minutes_move_faster_than_rates() -> None:
    games = _games([{"min": 30.0, "pts": 15.0}] * 15 + [{"min": 15.0, "pts": 7.5}] * 5)
    line = project_line(None, games)
    plain_average = (15 * 30.0 + 5 * 15.0) / 20
    assert line["mp"] < plain_average
    assert line["pts"] / line["mp"] == pytest.approx(0.5)


def test_anchor_from_games_is_the_plain_average() -> None:
    anchor = anchor_from_games(_games([{"min": 20.0, "pts": 10.0, "dd": 1.0}, {"min": 30.0, "pts": 20.0, "dd": 0.0}]))
    assert anchor["mp"] == pytest.approx(25.0)
    assert anchor["pts"] == pytest.approx(15.0)
    assert anchor["dd"] == pytest.approx(0.5)


def _write_feed(folder: Path) -> None:
    pd.DataFrame(
        [
            ("0022600001", "2026-10-20", "2026-10-20T23:30:00Z", "DEN", "UTA", ""),
            ("0022600002", "2026-10-21", "2026-10-22T02:00:00Z", "LAL", "DEN", ""),
            ("0022600003", "2026-10-23", "2026-10-23T23:00:00Z", "TOR", "BOS", ""),
        ],
        columns=list(nba_feed.SCHEDULE_COLUMNS),
    ).to_csv(folder / "schedule.csv", index=False)
    pd.DataFrame(
        [
            (203999, "Nikola Jokić", "DEN", "C"),
            (1641718, "Keyonte George", "UTA", "G"),
            (202695, "Kawhi Leonard", "TOR", "F"),
            (1626209, "Mario Hezonja", "CLE", "F-G"),
        ],
        columns=list(nba_feed.PLAYER_COLUMNS),
    ).to_csv(folder / "players.csv", index=False)
    last = {column: 0.0 for column in nba_feed.LOG_COLUMNS}
    last.update({"player_id": 202695, "player_name": "Kawhi Leonard", "team": "LAC", "game_id": "0022500001", "date": "2026-04-01", "opp": "DEN", "home": 1, "min": 30.0})
    pd.DataFrame([last]).to_csv(folder / "gamelogs_2025-26.csv", index=False)


def test_day_card_uses_feed_team_and_orders_by_value(tmp_path) -> None:
    _write_feed(tmp_path)
    data = season_data.SeasonData(tmp_path)
    session = SeasonSession(build_pool(), data=data)
    assert data.team_of("Kawhi Leonard", "LAC") == "TOR"
    assert data.team_of("Dillon Brooks", "PHO") == "PHX"

    opener = session.calendar(day=date(2026, 10, 20), today=date(2026, 10, 5))
    assert opener["week"] == 1
    assert opener["start"] == "2026-10-20"
    card = opener["day"]
    # No opponent on file: both start, listed in seat order.
    assert [(row["seat"], row["player_name"]) for row in card["playing"]] == [("PG", "Keyonte George"), ("C", "Nikola Jokić")]
    assert card["matchup_aware"] is False
    jokic = card["playing"][1]
    assert jokic["home"] is True and jokic["opp"] == "UTA" and jokic["b2b"] is False
    assert jokic["line"]["basis"] == "season line"
    assert jokic["line"]["value"] > card["playing"][0]["line"]["value"]
    assert set(jokic["line"]["z"]) == set(session.state()["categories"])
    assert "Mario Hezonja" in card["off"]

    # Before opening night with no date asked for, the pad opens on week 1.
    assert session.calendar(today=date(2026, 10, 5))["day"]["date"] == "2026-10-20"

    second = session.calendar(day=date(2026, 10, 21), today=date(2026, 10, 5))["day"]
    assert second["playing"][0]["b2b"] is True and second["playing"][0]["home"] is False

    kawhi = session.calendar(day=date(2026, 10, 23), today=date(2026, 10, 5))["day"]["playing"][0]
    assert kawhi["player_name"] == "Kawhi Leonard"
    assert kawhi["line"]["new_team"] is True


def test_this_season_games_move_the_line(tmp_path) -> None:
    _write_feed(tmp_path)
    before = season_data.SeasonData(tmp_path).line_for("Nikola Jokić")
    game = {column: 0.0 for column in nba_feed.LOG_COLUMNS}
    game.update({"player_id": 203999, "player_name": "Nikola Jokić", "team": "DEN", "game_id": "0022600001", "date": "2026-10-20", "opp": "UTA", "home": 1, "min": 20.0, "pts": 4.0})
    pd.DataFrame([game]).to_csv(tmp_path / "gamelogs_2026-27.csv", index=False)
    after = season_data.SeasonData(tmp_path).line_for("Nikola Jokić")
    assert after["games"] == 1
    assert after["basis"] == "1 g this season"
    assert after["mp"] < before["mp"]
    assert after["pts"] < before["pts"]
    assert after["value"] < before["value"]


def test_pad_opens_without_a_feed(tmp_path) -> None:
    session = SeasonSession(build_pool(), data=season_data.SeasonData(tmp_path))
    state = session.state()
    assert state["calendar"] is None
    assert state["feed"]["fetched_at"] is None
    assert state["streamers"]
    assert session.data.line_for("Mario Hezonja") is None


def test_refresh_keeps_the_old_file_when_a_pull_fails(tmp_path, monkeypatch) -> None:
    _write_feed(tmp_path)

    def down(*args, **kwargs):
        raise RuntimeError("feed down")

    monkeypatch.setattr(nba_feed, "fetch_schedule", down)
    monkeypatch.setattr(nba_feed, "fetch_players", down)
    monkeypatch.setattr(nba_feed, "fetch_logs", down)
    monkeypatch.setattr(nba_feed.injuries, "fetch_injuries", down)
    monkeypatch.setattr(nba_feed, "PAUSE_SECONDS", 0)
    report = nba_feed.refresh(tmp_path)
    assert set(report["errors"]) == {"schedule", "players", "logs 2026-27", "injuries"}
    assert report["rows"] == {}
    assert len(pd.read_csv(tmp_path / "schedule.csv")) == 3


def test_a_player_who_missed_last_year_uses_the_older_season_he_was_given(tmp_path) -> None:
    _write_feed(tmp_path)
    players = pd.read_csv(tmp_path / "players.csv")
    players.loc[len(players)] = [1630169, "Tyrese Haliburton", "IND", "G"]
    players.to_csv(tmp_path / "players.csv", index=False)
    assert season_data.SeasonData(tmp_path).line_for("Tyrese Haliburton") is None
    games = []
    for number in range(6):
        game = {column: 0.0 for column in nba_feed.LOG_COLUMNS}
        game.update({"season": "2024-25", "player_id": 1630169, "player_name": "Tyrese Haliburton", "team": "IND", "game_id": f"002240000{number}", "date": f"2025-01-0{number + 1}", "opp": "DEN", "home": 1, "min": 30.0, "pts": 18.0, "ast": 9.0})
        games.append(game)
    pd.DataFrame(games).to_csv(tmp_path / "gamelogs_older.csv", index=False)
    data = season_data.SeasonData(tmp_path)
    line = data.line_for("Tyrese Haliburton")
    assert line["pts"] == pytest.approx(18.0)
    assert line["ast"] == pytest.approx(9.0)
    assert line["basis"] == "2024-25 season, missed last year"
    assert data.history("Tyrese Haliburton").shape[0] == 6
