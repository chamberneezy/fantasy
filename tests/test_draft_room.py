"""Snake draft control: slot first, then a player, for either manager."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import draft_server
from draft_room import DraftSession, eligible_for_slot, snake_order


PLAYERS = [
    {"player_name": "Center", "positions": "C", "team": "DEN", "total_value": 10, "predicted_games": 70, "rookie": False, "pts": 25, "reb": 12, "ast": 8, "stl": 1, "blk": 1, "fg3m": 1},
    {"player_name": "Guard", "positions": "PG", "team": "OKC", "total_value": 9, "predicted_games": 72, "rookie": False, "pts": 30, "reb": 5, "ast": 6, "stl": 1, "blk": 1, "fg3m": 2},
    {"player_name": "Wing", "positions": "SF/PF", "total_value": 8, "predicted_games": 60, "rookie": True, "team": "MEM", "pts": 18, "reb": 7, "ast": 3, "stl": 1, "blk": 1, "fg3m": 1},
    {"player_name": "Big", "positions": "C", "team": "SAS", "total_value": 7, "predicted_games": 65, "rookie": False, "pts": 20, "reb": 10, "ast": 3, "stl": 1, "blk": 3, "fg3m": 1},
]


def test_snake_flips_each_round() -> None:
    assert snake_order(2, rounds=2) == [0, 1, 1, 0]


def test_center_cannot_fill_point_guard() -> None:
    assert eligible_for_slot("C", "PG") is False
    assert eligible_for_slot("SF/PF", "PF") is True
    assert eligible_for_slot("C", "UTIL") is True


def test_yahoo_files_a_player_into_the_most_specific_open_slot() -> None:
    session = DraftSession(PLAYERS, team_count=2, draft_slot=1)
    session.pick("Guard")
    assert session.picks[0]["slot_label"] == "PG"
    session.pick("Center")
    assert session.picks[1]["slot_label"] == "C"
    session.pick("Wing")
    assert session.picks[2]["slot_label"] == "SF"


def test_second_pick_records_the_other_manager_before_you() -> None:
    session = DraftSession(PLAYERS, team_count=2, draft_slot=2)
    assert session.state()["your_turn"] is False
    session.pick("Center")
    state = session.state()
    assert state["your_turn"] is True
    assert state["available"][0]["player_name"] == "Guard"
    their_center = next(slot for slot in state["rosters"][0]["slots"] if slot["label"] == "C")
    assert their_center["player"]["player_name"] == "Center"


def test_suggestion_changes_when_another_team_takes_that_player() -> None:
    session = DraftSession(PLAYERS, team_count=2, draft_slot=2)
    suggestion = session.suggestion()
    assert suggestion["options"][0]["player_name"] == "Center"
    assert suggestion["options"][1]["player_name"] == "Guard"
    assert suggestion["options"][0]["percent"] + suggestion["options"][1]["percent"] == 100
    assert suggestion["options"][0]["percent"] > suggestion["options"][1]["percent"]
    assert "Center" in suggestion["paragraph"] and "Guard" in suggestion["paragraph"]
    session.autopick()
    assert session.state()["your_turn"] is True
    nxt = session.suggestion()
    assert nxt["options"][0]["player_name"] == "Guard"
    assert nxt["options"][0]["player_name"] != "Center"


def test_your_autopick_uses_the_queue_before_the_board() -> None:
    session = DraftSession(PLAYERS, team_count=2, draft_slot=1)
    session.queue_add("Wing")
    session.autopick()
    assert session.picks[0]["player_name"] == "Wing"
    session.autopick()
    assert session.picks[1]["player_name"] == "Center"


def test_draft_page_starts_only_after_a_pick_position(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(draft_server, "SESSION_PATH", tmp_path / "session.json")
    monkeypatch.setattr(draft_server, "save_session", lambda session: None)
    monkeypatch.setattr(draft_server, "pool_for", lambda punts: PLAYERS)
    draft_server.SESSION["current"] = None
    client = draft_server.app.test_client()

    page = client.get("/draft")
    assert page.status_code == 200
    script = client.get("/static/draft.js")
    assert script.status_code == 200
    assert b"Where are you picking?" in script.data

    missing = client.post("/draft/api/start", json={"team_count": 2})
    assert missing.status_code == 400

    started = client.post("/draft/api/start", json={"team_count": 2, "draft_slot": 1, "punts": []})
    assert started.status_code == 200
    assert started.get_json()["your_turn"] is True

    picked = client.post("/draft/api/pick", json={"player_name": "Guard"})
    body = picked.get_json()
    assert picked.status_code == 200
    assert body["your_turn"] is False
    assert all(player["player_name"] != "Guard" for player in body["available"])
