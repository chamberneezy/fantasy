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
