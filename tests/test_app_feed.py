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
