"""Yahoo's real week score replaces the simulated past days."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import lineup  # noqa: E402
import matchup  # noqa: E402


def _game(name: str, points: float) -> dict:
    mean = np.zeros(len(matchup.STATS))
    mean[matchup.AT["mp"]] = 30
    mean[matchup.AT["pts"]] = points
    return {"name": name, "positions": {"C"}, "value": points, "mean": mean, "fixed": mean, "p": 1.0}


def _vector(points: float) -> np.ndarray:
    vector = np.zeros(len(matchup.STATS))
    vector[matchup.AT["pts"]] = points
    return vector


def test_banked_days_use_yahoo_and_later_days_still_count():
    mine = {"2026-10-23": [_game("Me", 10)], "2026-10-24": [_game("Me", 10)]}
    theirs = {"2026-10-23": [_game("Him", 30)], "2026-10-24": [_game("Him", 10)]}
    # Without Yahoo: he leads points 40 to 20.
    plain = lineup.plan_week(mine, theirs, "2026-10-25", runs=10)
    assert {row["cat"]: row["win"] for row in plain["result"]["cats"]}["PTS"] == 0.0
    # Yahoo says I really led 100 to 30 through the 23rd; the 24th is added on top: 110 to 40.
    banked = {"through": "2026-10-23", "mine": _vector(100), "theirs": _vector(30)}
    real = lineup.plan_week(mine, theirs, "2026-10-25", runs=10, banked=banked)
    points = {row["cat"]: row for row in real["result"]["cats"]}["PTS"]
    assert (points["mine"], points["theirs"], points["win"]) == (110.0, 40.0, 1.0)
    # His start count is real games only, not the Yahoo block.
    assert len(real["their_games"]) == 2


def test_a_past_day_uses_the_roster_of_that_day():
    import season

    session = season.SeasonSession.__new__(season.SeasonSession)
    session.moves = [
        {"date": "2026-10-21", "drop": "Jrue Holiday"},
        {"date": "2026-10-21", "add": "Jalen Smith"},
        {"date": "2026-10-25", "drop": "Anfernee Simons"},
        {"date": "2026-10-25", "add": "Tristan Da Silva"},
    ]
    assert session._on_roster("Jrue Holiday", "2026-10-20")
    assert not session._on_roster("Jrue Holiday", "2026-10-21")
    assert not session._on_roster("Jalen Smith", "2026-10-20")
    assert session._on_roster("Jalen Smith", "2026-10-21")
    assert session._on_roster("Anfernee Simons", "2026-10-24")
    assert not session._on_roster("Anfernee Simons", "2026-10-25")
    assert not session._on_roster("Tristan Da Silva", "2026-10-24")
    assert session._on_roster("Nikola Jokić", "2026-10-20")


def test_a_team_folder_brings_its_own_name_protected_list_and_files(tmp_path):
    import json

    import season

    (tmp_path / "session.json").write_text(json.dumps({
        "mode": "season", "team": "Other Team", "protected": [], "week": 2, "adds_used": 1,
        "roster": [], "il": [], "status": {}, "moves": [],
    }))
    from draft_room import build_pool

    session = season.load_season(build_pool([]), team_dir=tmp_path)
    assert session.team == "Other Team"
    assert session.protected == frozenset()
    assert (session.week, session.adds_used) == (2, 1)
    assert session.team_dir == tmp_path
    # Without a team folder the pad stays mine: Lipicaneri, Hezonja protected.
    assert "Mario Hezonja" in season.PROTECTED
