"""My Team: lineup moves and their reasons, bench reasons, score so far, averages."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matchup
import team_sheet
from team_sheet import average, bench_reasons, lineup_moves, score_so_far


def _entry(name: str, positions: str, value: float, p: float = 1.0, why: str = "", opp: str = "BOS") -> dict:
    return {
        "name": name,
        "date": "2026-10-23",
        "positions": set(positions.split("/")),
        "game": {"opp": opp, "home": True, "tip_utc": "2026-10-23T23:00:00Z", "b2b": False},
        "line": {"value": value},
        "value": value * p,
        "p": p,
        "why": why,
        "mean": np.zeros(len(matchup.STATS)),
    }


def test_no_moves_when_the_five_is_already_seated() -> None:
    entries = {"A": _entry("A", "PG", 1.0)}
    assert lineup_moves({"PG": "A"}, {"PG": "A"}, entries, None) == []


def test_starter_without_a_game_is_swapped_out_with_both_reasons() -> None:
    entries = {"B": _entry("B", "PG/SG", 0.8, opp="MIL")}
    moves = lineup_moves({"PG": "A", "SG": "C"}, {"PG": "B"}, entries, None)
    assert len(moves) == 1
    move = moves[0]
    assert (move["seat"], move["start"], move["sit"]) == ("PG", "B", "A")
    assert move["sit_why"] == "no game"
    assert move["start_why"].startswith("vs MIL")


def test_seat_change_says_where_he_moves() -> None:
    entries = {"K": _entry("K", "SG/SF", 2.0), "T": _entry("T", "PG/SG", 1.0)}
    moves = {m["seat"]: m for m in lineup_moves({"SG": "K"}, {"SG": "T", "SF": "K"}, entries, None)}
    assert moves["SG"]["sit_why"] == "moves to SF"
    assert "from SG" in moves["SF"]["start_why"]


def test_injured_starter_sits_for_his_chance() -> None:
    entries = {"A": _entry("A", "C", 2.0, p=0.4, why="Questionable · knee"), "B": _entry("B", "C", 0.5)}
    move = lineup_moves({"C": "A"}, {"C": "B"}, entries, None)[0]
    assert move["sit_why"] == "40% to play · Questionable · knee"


def test_bench_reason_when_his_only_seat_is_left_empty() -> None:
    entries = {"A": _entry("A", "PF", 2.0), "B": _entry("B", "C", 0.5)}
    why = bench_reasons({"PF": "A"}, entries, None)
    assert why == [{"player_name": "B", "game": "vs BOS", "why": "adds nothing tonight · every seat he fits (C) stays empty"}]


def test_bench_reason_compares_with_the_weakest_rival_seat() -> None:
    entries = {"S": _entry("S", "SG", 3.0), "P": _entry("P", "PG", 1.0), "X": _entry("X", "PG/SG", 0.5)}
    why = {row["player_name"]: row["why"] for row in bench_reasons({"SG": "S", "PG": "P"}, entries, None)}["X"]
    assert why == "+0.50 vs +1.00 value (P at PG)"


def test_score_so_far_counts_banked_starts_only() -> None:
    def banked(name: str, day: str, pts: float, reb: float) -> dict:
        row = np.zeros(len(matchup.STATS))
        row[matchup.AT["pts"]], row[matchup.AT["reb"]] = pts, reb
        row[matchup.AT["fga"]], row[matchup.AT["fgm"]] = 10, 5
        return {"name": name, "date": day, "fixed": row}

    plan = {
        "mine": {"2026-10-20": [banked("A", "2026-10-20", 30, 5), banked("Z", "2026-10-20", 99, 99)], "2026-10-21": []},
        "lineups": {"2026-10-20": {"PG": "A"}},
        "their_games": [banked("T", "2026-10-20", 20, 10)],
    }
    score = score_so_far(plan, "2026-10-21")
    calls = {row["cat"]: row["call"] for row in score["cats"]}
    assert calls["PTS"] == "win" and calls["REB"] == "hole" and calls["FG%"] == "ok"
    assert score["won"] + score["lost"] + score["tied"] == 12


def test_nothing_so_far_before_the_first_game() -> None:
    plan = {"mine": {"2026-10-20": []}, "lineups": {}, "their_games": []}
    assert score_so_far(plan, "2026-10-20") is None


def test_average_shoots_made_over_attempted() -> None:
    games = pd.DataFrame(
        [
            {**{stat: 0 for stat in ("min", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd", "ftm", "fta")}, "fgm": 1, "fga": 1},
            {**{stat: 0 for stat in ("min", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd", "ftm", "fta")}, "fgm": 1, "fga": 9},
        ]
    )
    line = average(games)
    assert line["fg_pct"] == pytest.approx(0.2)
    assert line["ft_pct"] is None
    assert line["games"] == 2


def test_set_lineup_seats_the_plan_and_benches_the_rest() -> None:
    from datetime import date

    from draft_room import build_pool
    from season import SeasonSession

    session = SeasonSession(build_pool())
    if not session.data.weeks:
        pytest.skip("no schedule on disk")
    week = session.data.weeks[0]
    # A light opening day (idle names must fill starts) and the last day of the week.
    for day in (week["start"], week["end"]):
        session.set_lineup(day, today=week["start"])
        plan = session.week_plan(week, week["start"])["lineups"][day.isoformat()]
        seated = {seat["slot_id"]: seat["player"]["player_name"] for seat in session.roster if not seat["slot_id"].startswith("BN")}
        # The plan's five sit where it says; idle names may fill the rest, as Yahoo has 5 bench spots.
        assert {seat: name for seat, name in seated.items() if seat in plan} == plan
        assert len({seat["slot_id"] for seat in session.roster}) == len(session.roster) == 10
        assert sum(seat["slot_id"].startswith("BN") for seat in session.roster) <= 5
    with pytest.raises(ValueError):
        session.set_lineup(date(2026, 10, 1), today=week["start"])
    assert team_sheet.lineup_moves(seated, plan, {}, None) == []


def test_week_totals_sum_the_box_score_and_keep_games() -> None:
    base = {stat: 0 for stat in ("min", "fg3m", "reb", "ast", "stl", "blk", "to", "pf", "dd", "ftm", "fta")}
    games = pd.DataFrame([{**base, "pts": 20, "fgm": 8, "fga": 16}, {**base, "pts": 10, "fgm": 4, "fga": 4}])
    line = team_sheet.week_totals(games)
    assert (line["pts"], line["games"]) == (30, 2)
    assert line["fg_pct"] == pytest.approx(0.6)
    assert line["per_game"]["pts"] == pytest.approx(15.0)


def test_every_view_gets_a_value_and_better_lines_score_higher() -> None:
    from season_data import season_lines

    _, baselines = season_lines()
    plain = {"mp": 30, "fgm": 6, "fga": 13, "ftm": 3, "fta": 4, "fg3m": 1.5, "pts": 16, "reb": 5, "ast": 3, "stl": 1, "blk": 0.5, "to": 2, "pf": 2, "dd": 0.1}
    great = {**plain, "pts": 30, "reb": 11, "ast": 8, "fgm": 11, "fga": 20, "dd": 0.6}
    stats = team_sheet._score(
        {"l7": team_sheet._with_rates(dict(plain)), "season": team_sheet._with_rates(dict(great)), "last": None}, baselines
    )
    assert stats["last"] is None
    assert stats["season"]["value"] > stats["l7"]["value"]
