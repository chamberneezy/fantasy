"""Context factors, injury chances, the legal five, and the simulated week."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import lineup
import matchup
import nba_feed
import season_data
from context import Context, position_group
from draft_room import build_pool
from injuries import play_chance, shape_injuries
from season import SeasonSession


def _log(player_id, team, day, opp, home=1, minutes=30.0, pts=15.0) -> dict:
    row = {column: 0.0 for column in nba_feed.LOG_COLUMNS}
    row.update({"player_id": player_id, "player_name": f"P{player_id}", "team": team, "game_id": f"{day}{team}", "date": day, "opp": opp, "home": home, "min": minutes, "pts": pts})
    return row


def test_position_group_reads_the_first_position() -> None:
    assert position_group("PG/SG") == "G"
    assert position_group("SF,PF") == "F"
    assert position_group("C") == "C"
    assert position_group("G-F") == "G"
    assert position_group("") == "F"


def test_soft_opponent_lifts_the_line_and_minutes_stay() -> None:
    logs = pd.DataFrame(
        [_log(1, "AAA", f"2026-01-{day:02d}", "SOFT", pts=30.0) for day in range(1, 21)]
        + [_log(2, "BBB", f"2026-01-{day:02d}", "HARD", pts=10.0) for day in range(1, 21)]
    )
    ctx = Context(logs, {1: "G", 2: "G"})
    line = {"mp": 30.0, **{stat: 10.0 for stat in ("fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf")}}
    soft = ctx.adjust(line, "SOFT", True, "G")
    hard = ctx.adjust(line, "HARD", True, "G")
    assert soft["pts"] > 10.0 > hard["pts"]
    assert soft["mp"] == 30.0
    # One opponent in a small sample is never believed past the clamp.
    assert soft["pts"] <= 11.5 and hard["pts"] >= 8.5
    assert ctx.adjust(line, "NEW", True, "G")["pts"] == pytest.approx(10.0)


def test_rest_habit_is_per_player() -> None:
    days = [f"2026-01-{day:02d}" for day in range(1, 21)]
    logs = [_log(1, "AAA", day, "X") for day in days]
    # Player 2 skips every second night: he plays odd days only.
    logs += [_log(2, "AAA", day, "X") for day in days[::2]]
    ctx = Context(pd.DataFrame(logs), {1: "G", 2: "G"})
    assert ctx.rest_chance(1) == pytest.approx(1.0)
    # He never plays one, but ten second nights are only half believed.
    assert ctx.rest_chance(2) < 0.7
    assert ctx.rest_chance(999) == 1.0
    assert ctx.rest_chance(None) == 1.0


def test_injury_chance_by_status_and_date() -> None:
    assert play_chance("Out", "2026-11-01", "2026-10-01", date(2026, 10, 25)) == 0.0
    assert play_chance("Out", "2026-11-01", "2026-10-01", date(2026, 11, 1)) == 0.6
    assert play_chance("Out", "2026-11-01", "2026-10-01", date(2026, 11, 10)) == 1.0
    assert play_chance("Out", "", "2026-10-01", date(2026, 10, 10)) == 0.0
    assert play_chance("Day-To-Day", "2026-10-10", "2026-10-03", date(2026, 10, 9)) == 0.25
    assert play_chance("Day-To-Day", "2026-10-10", "2026-10-03", date(2026, 10, 11)) == 0.6
    assert play_chance("Day-To-Day", "2026-10-10", "2026-10-03", date(2026, 10, 21)) == 0.9
    assert play_chance("", "", "", date(2026, 10, 21)) == 1.0


def test_injury_feed_shape() -> None:
    payload = {"injuries": [{"injuries": [{"athlete": {"displayName": "A B"}, "status": "Out", "date": "2026-09-21T19:50Z", "shortComment": "knee", "details": {"type": "Knee", "returnDate": "2026-11-01"}}, {"athlete": {}, "status": "Out"}]}]}
    frame = shape_injuries(payload)
    assert frame.to_dict("records") == [{"player_name": "A B", "status": "Out", "return_date": "2026-11-01", "reported": "2026-09-21", "part": "Knee", "note": "knee"}]


def test_best_five_respects_strict_seats() -> None:
    cands = [("Guard A", {"PG", "SG"}, 5.0), ("Guard B", {"PG"}, 4.0), ("Guard C", {"PG", "SG"}, 3.0), ("Big", {"C"}, 1.0)]
    five = lineup.best_five(cands, must_fill=True)
    # Only two guard seats exist, so the third guard sits. B can only play PG.
    assert five == {"PG": "Guard B", "SG": "Guard A", "C": "Big"}
    assert lineup.best_five([], must_fill=True) == {}


def test_a_player_who_costs_more_than_he_adds_sits_unless_the_five_must_fill() -> None:
    cands = [("Helps", {"PG"}, 0.2), ("Hurts", {"C"}, -0.1)]
    assert lineup.best_five(cands, must_fill=False) == {"PG": "Helps"}
    assert lineup.best_five(cands, must_fill=True) == {"PG": "Helps", "C": "Hurts"}


def _entry(name, positions, day="2026-10-20", chance=1.0, **stats) -> dict:
    line = {stat: 0.0 for stat in matchup.STATS}
    line.update(stats)
    return {"name": name, "date": day, "positions": set(positions), "mean": matchup.line_vector(line), "hist": None, "p": chance, "value": line["pts"]}


def test_simulated_week_calls_the_obvious_categories() -> None:
    rng = np.random.default_rng(1)
    strong = [_entry("A", {"PG"}, mp=35, pts=30, reb=5, fga=20, fgm=11, fta=6, ftm=5, to=2, pf=2)]
    weak = [_entry("B", {"PG"}, mp=20, pts=8, reb=12, fga=8, fgm=3, fta=2, ftm=1, to=4, pf=4)]
    result = matchup.compare(matchup.team_totals(strong, 3000, rng), matchup.team_totals(weak, 3000, rng))
    cats = {row["cat"]: row for row in result["cats"]}
    assert cats["MIN"]["win"] == 1.0
    assert cats["PTS"]["win"] > 0.99
    assert cats["REB"]["win"] < 0.1
    # Fewer turnovers and fouls win those two.
    assert cats["TO"]["win"] > 0.6 and cats["PF"]["win"] > 0.6
    assert cats["PTS"]["mine"] == pytest.approx(30.0, abs=0.5)
    assert result["win"] + result["tie"] + result["lose"] == pytest.approx(1.0)
    assert 0 <= result["expected"] <= 12


def test_a_doubtful_player_is_worth_his_chance() -> None:
    rng = np.random.default_rng(2)
    totals = matchup.team_totals([_entry("A", {"PG"}, chance=0.25, mp=30, pts=20)], 8000, rng)
    assert totals[:, matchup.AT["pts"]].mean() == pytest.approx(5.0, abs=0.4)
    assert totals[:, matchup.AT["mp"]].mean() == pytest.approx(7.5, abs=0.5)


def test_history_is_rescaled_to_tonights_line() -> None:
    rng = np.random.default_rng(3)
    entry = _entry("A", {"PG"}, mp=30, pts=20)
    past = np.zeros((2, len(matchup.STATS)))
    past[:, matchup.AT["mp"]] = [20, 40]
    past[:, matchup.AT["pts"]] = [5, 15]
    entry["hist"] = past
    games = matchup.draw(entry, 4000, rng)
    assert games[:, matchup.AT["pts"]].mean() == pytest.approx(20.0, abs=0.5)
    assert set(np.round(games[:, matchup.AT["pts"]])) == {10.0, 30.0}


def test_banked_games_do_not_vary() -> None:
    entry = _entry("A", {"PG"}, pts=20)
    entry["fixed"] = np.arange(len(matchup.STATS), dtype=float)
    games = matchup.draw(entry, 5, np.random.default_rng(4))
    assert (games == entry["fixed"]).all()


def test_plan_sits_a_foul_machine_when_fouls_are_the_swing_category() -> None:
    def big(name, **extra):
        return _entry(name, {"C"}, **{"mp": 30, "pts": 10, "reb": 8, "pf": 3, "to": 1, "fga": 8, "fgm": 4, "fta": 2, "ftm": 1, **extra})

    # Everything but fouls is decided: I am far ahead everywhere else with Star alone.
    star = _entry("Star", {"PG"}, mp=400, pts=400, reb=200, ast=90, stl=30, blk=30, fg3m=40, fga=200, fgm=120, fta=80, ftm=70, dd=5, to=1, pf=1)
    hacker = _entry("Hacker", {"C"}, mp=1, pts=0, pf=6, to=3, fga=4, fgm=0, fta=2, ftm=0)
    mine = {"2026-10-20": [star, hacker]}
    theirs = {"2026-10-20": [big("Them")]}
    plan = lineup.plan_week(mine, theirs, today="2026-10-20", runs=1500)
    assert plan["lineups"]["2026-10-20"] == {"PG": "Star"}
    # Yesterday's five is not rewritten: the day is already played.
    late = lineup.plan_week(mine, theirs, today="2026-10-21", runs=1500)
    assert late["lineups"]["2026-10-20"] == {"PG": "Star", "C": "Hacker"}


def _feed(folder: Path) -> None:
    pd.DataFrame(
        [("0022600001", "2026-10-20", "2026-10-20T23:30:00Z", "DEN", "UTA", ""), ("0022600002", "2026-10-21", "2026-10-22T02:00:00Z", "DET", "DEN", "")],
        columns=list(nba_feed.SCHEDULE_COLUMNS),
    ).to_csv(folder / "schedule.csv", index=False)
    pd.DataFrame(
        [(203999, "Nikola Jokić", "DEN", "C"), (1641718, "Keyonte George", "UTA", "G"), (1, "Jalen Duren", "DET", "C"), (2, "Jimmy Butler", "DEN", "F")],
        columns=list(nba_feed.PLAYER_COLUMNS),
    ).to_csv(folder / "players.csv", index=False)
    pd.DataFrame(
        [("Them", "X", "C", "Jalen Duren", "DET", "C"), ("Them", "X", "BN", "Jimmy Butler III", "DEN", "SF/PF"), ("Lipicaneri", "Mario", "C", "Nikola Jokić", "DEN", "C"), ("Lipicaneri", "Mario", "PG", "Keyonte George", "UTA", "PG/SG")],
        columns=["fantasy_team", "manager", "slot", "player_name", "nba_team", "positions"],
    ).to_csv(folder / season_data.ROSTERS_NAME, index=False)
    pd.DataFrame([(1, "Them")], columns=["week", "opponent"]).to_csv(folder / season_data.MATCHUPS_NAME, index=False)
    pd.DataFrame(
        [("Keyonte George", "Out", "2026-11-01", "2026-10-01", "Ankle", "")], columns=["player_name", "status", "return_date", "reported", "part", "note"]
    ).to_csv(folder / "injuries.csv", index=False)


def test_pad_reads_matchup_injuries_and_marks(tmp_path) -> None:
    _feed(tmp_path)
    data = season_data.SeasonData(tmp_path)
    assert data.rostered_by("Jimmy Butler") == "Them"
    assert data.positions_for("Jimmy Butler") == ("SF/PF", True)
    assert data.positions_for("Brook Lopez", "C") == ("C", False)
    session = SeasonSession(build_pool(), data=data)
    grid = session.calendar(day=date(2026, 10, 20), today=date(2026, 10, 5))
    card = grid["matchup"]
    assert card["opponent"] == "Them"
    assert len(card["cats"]) == 12
    # Duren once, Butler on both Denver nights.
    assert card["their_starts"] == 3
    day = grid["day"]
    assert day["matchup_aware"] is True
    george = next(row for row in day["playing"] if row["player_name"] == "Keyonte George")
    # Listed out until November: zero chance, so he is not seated.
    assert george["chance"] == 0.0 and george["seat"] is None and "Out" in george["why"]
    jokic = next(row for row in day["playing"] if row["player_name"] == "Nikola Jokić")
    assert jokic["seat"] == "C" and jokic["swing"] > 0

    session.set_status("keyonte george", "in")
    george = next(row for row in session.calendar(day=date(2026, 10, 20), today=date(2026, 10, 5))["day"]["playing"] if row["player_name"] == "Keyonte George")
    assert george["chance"] == 1.0 and george["seat"] == "PG" and george["status"] == "in"
    session.set_status("jokic", "out")
    jokic = next(row for row in session.calendar(day=date(2026, 10, 20), today=date(2026, 10, 5))["day"]["playing"] if row["player_name"] == "Nikola Jokić")
    assert jokic["seat"] is None
    session.set_status("jokic", "clear")
    assert "Nikola Jokić" not in session.status
    with pytest.raises(ValueError):
        session.set_status("jokic", "maybe")

    # Nobody the league owns is offered, and no offer drops Hezonja.
    for row in grid["plans"]:
        assert data.rostered_by(row["add"]) is None
        assert row["drop"] != "Mario Hezonja"
