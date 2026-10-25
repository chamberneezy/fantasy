import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import stats_board  # noqa: E402


def _logs(rows):
    columns = ["player_id", "player_name", "team", "date", *stats_board.SUM_STATS]
    return pd.DataFrame([[*row, *([10] * len(stats_board.SUM_STATS))] for row in rows], columns=columns)


def test_windows_keep_games_before_today_within_the_days():
    logs = _logs([(1, "A", "DEN", "2026-10-01"), (1, "A", "DEN", "2026-10-20"), (1, "A", "DEN", "2026-10-25")])
    today = date(2026, 10, 25)
    assert list(stats_board.window_games(logs, today, 7)["date"]) == ["2026-10-20"]
    assert list(stats_board.window_games(logs, today, None)["date"]) == ["2026-10-01", "2026-10-20"]


def test_averages_count_games_per_player():
    logs = _logs([(1, "A", "DEN", "2026-10-20"), (1, "A", "DEN", "2026-10-21"), (2, "B", "OKC", "2026-10-21")])
    frame = stats_board.averages(logs).set_index("player_id")
    assert frame.loc[1, "games"] == 2 and frame.loc[1, "pts"] == 20
    assert frame.loc[2, "games"] == 1


def test_board_ranks_by_value_and_needs_enough_games(monkeypatch):
    monkeypatch.setattr(stats_board.daily, "score_lines", lambda lines, baselines: [{"value": line["pts"]} for line in lines])

    class Data:
        logs = pd.concat(
            [
                _logs([(1, "Star", "DEN", "2026-10-20"), (1, "Star", "DEN", "2026-10-22"), (1, "Star", "DEN", "2026-10-24")]).assign(pts=[40, 40, 40]),
                _logs([(2, "Mine", "OKC", "2026-10-20"), (2, "Mine", "OKC", "2026-10-22")]).assign(pts=[20, 20]),
                _logs([(3, "Once", "UTA", "2026-10-22")]).assign(pts=[90]),
            ]
        )
        baselines = {}

        def rostered_by(self, name):
            return None

        def positions_for(self, name):
            return ("C", False)

    result = stats_board.board(Data(), date(2026, 10, 25), ["Mine"], [])
    league = result["rows"]["7d"]["league"]
    # Most games anyone played: 3, so the bar is 2. One game is under it: ranked out, though his night was biggest.
    assert [row["player_name"] for row in league] == ["Star", "Mine"]
    assert [row["rank"] for row in league] == [1, 2]
    assert league[1]["owner"] == "mine" and league[0]["owner"] == "free"
    assert result["rows"]["7d"]["mine"][0]["player_name"] == "Mine"
