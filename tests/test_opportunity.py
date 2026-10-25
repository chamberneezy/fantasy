import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import opportunity  # noqa: E402


STATS = ("fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd")


def _logs(rows):
    """(player, team, game, minutes) rows; every other stat is one per minute, so rates stay flat."""
    frame = pd.DataFrame(rows, columns=["player_id", "team", "game_id", "min"])
    for stat in STATS:
        frame[stat] = 0 if stat == "dd" else frame["min"]
    return frame


def test_minute_shift_compares_games_with_and_without():
    logs = _logs(
        [
            (1, "ORL", "g1", 34), (2, "ORL", "g1", 24),
            (1, "ORL", "g2", 34), (2, "ORL", "g2", 24),
            (2, "ORL", "g3", 30),
            (2, "ORL", "g4", 30),
        ]
    )
    shift = opportunity.minute_shift([(logs, 1.0)], "ORL", 1)
    assert shift[2]["min_with"] == 24
    assert shift[2]["min_without"] == 30
    assert shift[2]["games_without"] == 2


def test_minute_shift_skips_a_season_he_was_not_on_the_team():
    logs = _logs([(2, "ORL", "g1", 24), (2, "ORL", "g2", 30)])
    assert opportunity.minute_shift([(logs, 1.0)], "ORL", 1) == {}


def test_absent_means_out_or_a_later_return():
    today = date(2026, 10, 25)
    assert opportunity._absent({"status": "Out"}, today)
    assert opportunity._absent({"status": "Day-To-Day", "return_date": "2026-10-28"}, today)
    assert not opportunity._absent({"status": "Day-To-Day", "return_date": "2026-10-26"}, today)
    assert not opportunity._absent({"status": "Day-To-Day", "return_date": ""}, today)


def test_long_absence_with_a_free_pickup_ranks_first():
    long = {"days_out": 28, "gains": [{"owner": "free", "min_with": 24.0, "min_without": 27.0}]}
    short = {"days_out": 1, "gains": [{"owner": "free", "min_with": 5.0, "min_without": 23.0}]}
    taken = {"days_out": 40, "gains": [{"owner": "Old Stars", "min_with": 20.0, "min_without": 35.0}]}
    ranked = sorted([short, taken, long], key=opportunity._priority)
    assert ranked == [long, short, taken]


def test_bump_shrinks_the_minutes_jump_and_keeps_flat_rates(monkeypatch):
    monkeypatch.setattr(opportunity.daily, "score_lines", lambda lines, baselines: [{"z": {}, "value": 0.0}])
    logs = _logs(
        [(1, "ORL", f"w{i}", 34) for i in range(10)]
        + [(2, "ORL", f"w{i}", 24) for i in range(10)]
        + [(2, "ORL", f"o{i}", 30) for i in range(5)]
    )
    shift = opportunity.minute_shift([(logs, 1.0)], "ORL", 1)[2]
    line = {"mp": 24.0, **{stat: 24.0 for stat in STATS}, "dd": 0.0}
    bumped = opportunity.bumped_line(line, shift, {})
    # Five games without him against a prior of SHRINK_GAMES: that share of the 6-minute jump.
    expected = 24.0 + 6.0 * 5 / (5 + opportunity.SHRINK_GAMES)
    assert round(bumped["mp"], 6) == round(expected, 6)
    # One point per minute with him and without him: points follow minutes only.
    assert round(bumped["pts"], 6) == round(expected, 6)
    # Already out all season: nothing to add.
    assert opportunity.bumped_line(line, shift, {}, still_with=0.0)["mp"] == 24.0
    # The team's gains capped to the minutes he leaves.
    half = 24.0 + 3.0 * 5 / (5 + opportunity.SHRINK_GAMES)
    assert round(opportunity.bumped_line(line, shift, {}, minute_scale=0.5)["mp"], 6) == round(half, 6)


def test_already_out_all_season_means_the_bump_is_in_the_line():
    logs = _logs([(2, "MEM", "g1", 30), (2, "MEM", "g2", 30), (1, "MEM", "g0", 30)])
    assert opportunity.still_with(logs, "MEM", 1, 2, 0.0) == 0.0
    assert opportunity.still_with(logs, "MEM", 1, 2, 2.0) == 0.5


def test_certainty_needs_a_clear_jump_and_enough_games():
    logs = _logs(
        [(1, "ORL", f"w{i}", 34) for i in range(12)]
        + [(2, "ORL", f"w{i}", 20 + (i % 3)) for i in range(12)]
        + [(2, "ORL", f"o{i}", 30 + (i % 3)) for i in range(10)]
    )
    shift = opportunity.minute_shift([(logs, 1.0)], "ORL", 1)[2]
    assert opportunity.certainty(shift)["level"] == "high"
    few = _logs([(1, "ORL", "w0", 34), (2, "ORL", "w0", 20), (2, "ORL", "w1", 22), (2, "ORL", "o0", 21), (2, "ORL", "o1", 26), (2, "ORL", "o2", 19)])
    assert opportunity.certainty(opportunity.minute_shift([(few, 1.0)], "ORL", 1)[2])["level"] == "low"
