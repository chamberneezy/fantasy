import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import espn_feed  # noqa: E402


def test_names_match_without_accents_dots_or_suffixes():
    assert espn_feed.name_key("Nikola Jokić") == espn_feed.name_key("Nikola Jokic")
    assert espn_feed.name_key("Kelly Oubre Jr.") == espn_feed.name_key("Kelly Oubre")
    assert espn_feed.name_key("P.J. Washington") == espn_feed.name_key("PJ Washington")


def test_team_codes_follow_the_nba():
    assert [espn_feed.team_code(code) for code in ("GS", "NY", "UTAH", "WSH", "DEN")] == ["GSW", "NYK", "UTA", "WAS", "DEN"]


def test_ids_keep_known_pairs_and_skip_ambiguous_names():
    espn = pd.DataFrame({"espn_id": [1, 2, 3], "espn_name": ["Nikola Jokić", "Jalen Williams", "New Guy"]})
    known = pd.DataFrame({"espn_id": [2], "player_id": [222], "player_name": ["Jalen Williams"]})
    nba = pd.DataFrame({"player_id": [203999, 111, 222], "player_name": ["Nikola Jokić", "Jalen Williams", "Jalen Williams"]})
    ids = espn_feed.match_ids(espn, known, nba)
    assert dict(zip(ids["espn_id"], ids["player_id"])) == {1: 203999, 2: 222}
    players, unmatched = espn_feed.shape_players(
        espn.assign(team="DEN", nba_position="C"), ids
    )
    assert unmatched == ["New Guy"]
    assert espn_feed.ESPN_ID_OFFSET + 3 in set(players["player_id"])


def test_box_score_rows_split_made_attempted_and_mark_double_doubles():
    summary = {
        "boxscore": {
            "players": [
                {
                    "team": {"abbreviation": "DEN"},
                    "statistics": [
                        {
                            "labels": ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB", "PF", "+/-"],
                            "athletes": [
                                {"athlete": {"id": "1", "displayName": "Nikola Jokić"}, "stats": ["44", "35", "12-23", "3-6", "8-8", "15", "10", "6", "2", "3", "4", "11", "5", "+9"]},
                                {"athlete": {"id": "9", "displayName": "Bench Guy"}, "didNotPlay": True, "stats": []},
                            ],
                        }
                    ],
                }
            ]
        }
    }
    game = {"game_id": "401", "date": "2026-10-24", "home": "DEN", "away": "NOP"}
    rows = espn_feed.shape_box(summary, game, {1: (203999, "Nikola Jokić")})
    assert len(rows) == 1
    row = rows[0]
    assert (row["player_id"], row["opp"], row["home"]) == (203999, "NOP", 1)
    assert (row["fgm"], row["fga"], row["fg3m"], row["ftm"], row["fta"]) == (12, 23, 3, 8, 8)
    assert (row["pts"], row["reb"], row["ast"], row["to"], row["pf"], row["dd"]) == (35, 15, 10, 6, 5, 1)


def test_schedule_keeps_regular_season_and_uses_the_eastern_day():
    events = [
        {
            "id": "401",
            "date": "2026-10-23T01:30Z",
            "seasonType": {"type": 2},
            "competitions": [{"status": {"type": {"name": "STATUS_FINAL"}}, "competitors": [
                {"homeAway": "home", "team": {"abbreviation": "OKC"}}, {"homeAway": "away", "team": {"abbreviation": "DEN"}},
            ]}],
        },
        {"id": "402", "date": "2026-10-10T00:00Z", "seasonType": {"type": 1}, "competitions": [{"competitors": []}]},
    ]
    schedule = espn_feed.shape_schedule(events)
    assert list(schedule["game_id"]) == ["401"]
    assert schedule.iloc[0]["date"] == "2026-10-22"
    assert schedule.iloc[0]["tip_utc"] == "2026-10-23T01:30:00Z"
    assert bool(schedule.iloc[0]["final"])
