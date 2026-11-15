import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import app_feed  # noqa: E402


def test_lean_words_cover_the_range():
    assert app_feed.lean_word(0.9) == "likely yours"
    assert app_feed.lean_word(0.6) == "lean yours"
    assert app_feed.lean_word(0.5) == "coin flip"
    assert app_feed.lean_word(0.3) == "lean his"
    assert app_feed.lean_word(0.1) == "unlikely"


def test_score_counts_yahoo_categories_with_turnovers_and_fouls_reversed():
    leans = [
        {"cat": "PTS", "lean": "likely yours", "yahoo_mine": 236, "yahoo_theirs": 205},
        {"cat": "TO", "lean": "likely yours", "yahoo_mine": 19, "yahoo_theirs": 29},
        {"cat": "PF", "lean": "unlikely", "yahoo_mine": 44, "yahoo_theirs": 17},
        {"cat": "DD", "lean": "coin flip", "yahoo_mine": 2, "yahoo_theirs": 2},
    ]
    result = app_feed.score(leans, "2026-10-23")
    assert (result["won"], result["lost"], result["tied"]) == (2, 1, 1)
    assert result["outlook"] == {"yours": 2, "coin_flip": 1, "his": 1}
    assert "won" not in app_feed.score([{**row, "yahoo_mine": None} for row in leans][:0] or leans[:1], None)


def test_a_night_counts_only_the_starters_who_played():
    import numpy as np

    import matchup

    def line(points, minutes=30):
        vector = np.zeros(len(matchup.STATS))
        vector[matchup.AT["mp"]], vector[matchup.AT["pts"]] = minutes, points
        return vector

    plan = {
        "mine": {"2026-10-24": [
            {"name": "Starter", "fixed": line(30)},
            {"name": "Benched", "fixed": line(40)},
            {"name": "Sat out", "fixed": line(0, minutes=0)},
        ]},
        "lineups": {"2026-10-24": {"PG": "Starter", "SG": "Sat out"}},
    }
    rows, total = app_feed._night(plan, "mine", "2026-10-24")
    assert [row["player_name"] for row in rows] == ["Starter"]
    assert total[matchup.AT["pts"]] == 30


def test_true_shooting_and_usage_follow_the_standard_formulas():
    assert app_feed.true_shooting(22, 14, 5) == round(22 / (2 * (14 + 0.44 * 5)), 3)
    assert app_feed.true_shooting(0, 0, 0) is None
    player = {"min": 30, "fga": 15, "fta": 4, "to": 2}
    team = {"min": 240, "fga": 88, "fta": 22, "to": 13}
    expected = (15 + 0.44 * 4 + 2) * (240 / 5) / (30 * (88 + 0.44 * 22 + 13))
    assert app_feed.usage(player, team) == round(expected, 3)
    assert app_feed.usage({**player, "min": 0}, team) is None


def test_short_names_keep_the_surname_whole():
    assert app_feed.short_name("Nikola Jokić") == "N. Jokić"
    assert app_feed.short_name("Jaren Jackson Jr.") == "J. Jackson Jr."
    assert app_feed.short_name("Nenê") == "Nenê"
