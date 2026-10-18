"""Matchup detail: opponent ranks by position group, pace, history, splits, role."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_feed import LOG_COLUMNS
from scouting import Scout

TEAMS = [f"T{i:02d}" for i in range(30)]
GUARD, CENTRE = 1, 2


def _row(player_id, team, opp, game_id, day, home, **stats) -> dict:
    row = {column: 0 for column in LOG_COLUMNS}
    row.update(
        player_id=player_id, player_name=f"P{player_id}", team=team, opp=opp, game_id=game_id,
        date=day, home=home, min=30, fgm=5, fga=10, ftm=2, fta=2, fg3m=1, pts=13, reb=5, ast=3,
        stl=1, blk=1, to=2, pf=2, dd=0,
    )
    row.update(stats)
    return row


def _season(soft_on_centres: str = "T00", extra_rows=()) -> pd.DataFrame:
    """Every team plays every other once. ``soft_on_centres`` gives centres double points."""
    rows = []
    game = 0
    for a, team in enumerate(TEAMS):
        for opp in TEAMS[a + 1:]:
            game += 1
            gid = f"g{game:04d}"
            day = f"2025-11-{(game % 28) + 1:02d}"
            for side, other, home in ((team, opp, 1), (opp, team, 0)):
                base = 1000 * (TEAMS.index(side) + 1)
                rows.append(_row(base + GUARD, side, other, gid, day, home))
                pts = 26 if other == soft_on_centres else 13
                rows.append(_row(base + CENTRE, side, other, gid, day, home, pts=pts))
    rows.extend(extra_rows)
    return pd.DataFrame(rows)


def _groups(frame: pd.DataFrame) -> dict[int, str]:
    return {int(pid): ("C" if pid % 1000 == CENTRE else "G") for pid in frame["player_id"].unique()}


def _scout(last: pd.DataFrame, current: pd.DataFrame | None = None, older: pd.DataFrame | None = None) -> Scout:
    empty = pd.DataFrame(columns=list(LOG_COLUMNS))
    return Scout(
        current if current is not None else empty,
        last,
        older if older is not None else pd.DataFrame(),
        _groups(last),
        "2026-27",
        "2025-26",
    )


def test_soft_opponent_ranks_first_for_its_position_only() -> None:
    scout = _scout(_season(soft_on_centres="T05"))
    centre = {row["cat"]: row for row in scout.detail(1000 + CENTRE, "T05", True)["allowed"]}
    guard = {row["cat"]: row for row in scout.detail(1000 + GUARD, "T05", True)["allowed"]}
    assert centre["PTS"]["rank"] == 1
    assert centre["PTS"]["ratio"] > 0.5
    assert guard["PTS"]["ratio"] == pytest.approx(0.0)


def test_turnovers_forced_rank_last_for_you() -> None:
    last = _season()
    last.loc[last["opp"] == "T07", "to"] = 6
    detail = _scout(last).detail(1000 + GUARD, "T07", False)
    to = next(row for row in detail["allowed"] if row["cat"] == "TO")
    assert to["rank"] == 30


def test_last_season_until_every_team_has_ten_games() -> None:
    last = _season()
    current = last.loc[last["game_id"] <= "g0005"].copy()
    detail = _scout(last, current).detail(1000 + GUARD, "T01", True)
    assert detail["team_basis"] == "2025-26"
    assert detail["early"] is True
    assert _scout(last, last.copy()).detail(1000 + GUARD, "T01", True)["early"] is False


def test_pace_ranks_the_fastest_team_first() -> None:
    last = _season()
    last.loc[last["team"] == "T09", "fga"] = 30
    team = _scout(last).detail(1000 + GUARD, "T09", True)["team"]
    assert team["pace_rank"] == 1
    assert team["games"] == 29


def test_history_against_one_team_spans_older_seasons() -> None:
    last = _season()
    older = last.assign(season="2024-25", game_id="old" + last["game_id"], date=last["date"].str.replace("2025", "2024"))
    older.loc[(older["player_id"] == 1000 + GUARD) & (older["opp"] == "T03"), "pts"] = 40
    detail = _scout(last, older=older).detail(1000 + GUARD, "T03", True)
    history = detail["history"]
    assert history["seasons"] == ["2024-25", "2025-26"]
    assert history["versus"]["games"] == 2
    assert history["versus"]["pts"] == pytest.approx(26.5)
    assert history["overall"]["pts"] > 13
    assert len(detail["meetings"]) == 2
    assert detail["meetings"][0]["date"] > detail["meetings"][1]["date"]


def test_home_away_split_and_role() -> None:
    last = _season()
    # T15 is home against the teams after it and away against those before it.
    guard = 16000 + GUARD
    mine = last["player_id"] == guard
    last.loc[mine & (last["home"] == 1), "pts"] = 20
    detail = _scout(last).detail(guard, "T04", True)
    assert detail["splits"]["home"]["pts"] > detail["splits"]["away"]["pts"]
    assert detail["splits"]["tonight"] == "home"
    # Two players, 30 min each: team minutes 60, so "five on the floor" is 12 min;
    # he uses half the possessions in 30 of those 12 → 100 · ½ · 12/30 = 20.
    assert detail["role"]["usage"] == pytest.approx(20.0)
    assert 0 < detail["role"]["ts"] < 1


def test_unknown_player_still_gets_the_opponent() -> None:
    detail = _scout(_season()).detail(None, "T02", True)
    # No position known: forwards, which this fixture has none of.
    assert detail["group"] == "F"
    assert detail["team"]["games"] == 29
    assert detail["history"] is None and detail["role"] is None
