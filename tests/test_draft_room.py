"""Yahoo live salary-cap: circular nominations and a rising bid."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import draft_server
from auction import assign_auction_values, cap_bid
from draft_room import eligible_for_slot, snake_order
from yahoo_auction import DraftSession


PLAYERS = [
    {"player_name": "Center", "positions": "C", "team": "DEN", "total_value": 10, "predicted_games": 70, "rookie": False, "pts": 25, "reb": 12, "ast": 8, "stl": 1, "blk": 1, "fg3m": 1, "mp": 34, "pf": 2.5, "dd": 0.7},
    {"player_name": "Guard", "positions": "PG", "team": "OKC", "total_value": 9, "predicted_games": 72, "rookie": False, "pts": 30, "reb": 5, "ast": 6, "stl": 1, "blk": 1, "fg3m": 2, "mp": 33, "pf": 2.0, "dd": 0.2},
    {"player_name": "Wing", "positions": "SF/PF", "total_value": 8, "predicted_games": 60, "rookie": True, "team": "MEM", "pts": 18, "reb": 7, "ast": 3, "stl": 1, "blk": 1, "fg3m": 1, "mp": 30, "pf": 2.2, "dd": 0.1},
    {"player_name": "Big", "positions": "C", "team": "SAS", "total_value": 7, "predicted_games": 65, "rookie": False, "pts": 20, "reb": 10, "ast": 3, "stl": 1, "blk": 3, "fg3m": 1, "mp": 28, "pf": 3.0, "dd": 0.4},
]


def test_snake_flips_each_round() -> None:
    assert snake_order(2, rounds=2) == [0, 1, 1, 0]


def test_center_cannot_fill_point_guard() -> None:
    assert eligible_for_slot("C", "PG") is False
    assert eligible_for_slot("SF/PF", "PF") is True
    assert eligible_for_slot("C", "BN") is True


def test_auction_values_spend_the_budget() -> None:
    players = [dict(player) for player in PLAYERS]
    assign_auction_values(players, team_count=2, roster_size=2, budget=20)
    assert sum(player["auction_value"] for player in players) == 40
    assert all(player["auction_value"] >= 1 for player in players)


def test_cap_bid_leaves_a_dollar_for_empty_seats() -> None:
    assert cap_bid(80, 200, 10) == 80
    assert cap_bid(80, 20, 8) == 13


def test_you_nominate_at_a_dollar_then_the_clock_sells() -> None:
    session = DraftSession(PLAYERS, team_count=2, draft_slot=1, budget=20, rounds=2)
    assert session.state()["can_nominate"] is True
    session.nominate("Center")
    assert session.on_block["bid"] == 1
    assert session.on_block["high_bidder"] == 0
    session.clock_ends = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.tick()
    assert session.picks[0]["player_name"] == "Center"
    assert session.picks[0]["slot_label"] == "C"
    assert session.picks[0]["price"] >= 1
    assert session.nominator() == 1


def test_listed_stars_sit_in_a_real_room() -> None:
    from draft_room import build_pool

    players = build_pool()
    top = players[0]
    wemby = next(player for player in players if "wembanyama" in player["player_name"].lower())
    doncic = next(player for player in players if "don" in player["player_name"].lower() and "luka" in player["player_name"].lower())
    jokic = next(player for player in players if "joki" in player["player_name"].lower())
    kawhi = next(player for player in players if "kawhi" in player["player_name"].lower())
    porter = next(player for player in players if "kevin porter" in player["player_name"].lower())
    ware = next(player for player in players if "ware" in player["player_name"].lower() and "kel" in player["player_name"].lower())
    butler = next(player for player in players if player["player_name"].lower().startswith("jimmy butler"))
    assert wemby["auction_value"] == 61
    assert jokic["auction_value"] == 60
    assert doncic["auction_value"] == 59
    assert kawhi["auction_value"] == 27
    assert jokic["stay_market"] >= 70
    assert porter["yahoo_listed"] == 3
    assert porter["auction_value"] == 3
    assert ware["yahoo_listed"] == 16
    assert butler["yahoo_listed"] == 1
    assert butler["auction_value"] == 1
    alondes = next(player for player in players if player["player_name"] == "Alondes Williams")
    kadary = next(player for player in players if player["player_name"] == "Kadary Richmond")
    assert alondes.get("yahoo_listed") in (None, 0)
    assert alondes["auction_value"] == 1
    assert kadary["auction_value"] == 1
    assert alondes["total_value"] > 8


def test_a_star_does_not_sell_for_a_dollar() -> None:
    players = [
        {**PLAYERS[0], "player_name": "Kevin Durant", "auction_value": 45, "total_value": 11.8, "superstar": True},
        {**PLAYERS[1], "auction_value": 20},
        {**PLAYERS[2], "auction_value": 10},
        {**PLAYERS[3], "auction_value": 8},
    ]
    session = DraftSession(players, team_count=4, draft_slot=1, budget=200, rounds=2)
    session.nominate("Kevin Durant")
    session.clock_ends = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.tick()
    sold = session.picks[0]
    assert sold["player_name"] == "Kevin Durant"
    assert sold["price"] >= 20


def _filler(index: int, value: int) -> dict:
    return {
        "player_name": f"Role {index}",
        "positions": "SG",
        "team": "ORL",
        "total_value": 3,
        "auction_value": value,
        "predicted_games": 70,
        "rookie": False,
        "pts": 12,
        "reb": 4,
        "ast": 3,
        "stl": 1,
        "blk": 0.4,
        "fg3m": 1.5,
        "mp": 28,
        "pf": 2.0,
        "dd": 0.05,
    }


def test_two_stars_do_not_land_on_one_roster() -> None:
    stars = [
        {**PLAYERS[0], "player_name": "Nikola Jokic", "auction_value": 71, "total_value": 24, "superstar": True},
        {**PLAYERS[3], "player_name": "Victor Wembanyama", "auction_value": 67, "total_value": 21, "superstar": True},
        {**PLAYERS[1], "player_name": "Luka Doncic", "auction_value": 55, "total_value": 16, "superstar": True},
        {**PLAYERS[2], "player_name": "Shai Gilgeous-Alexander", "auction_value": 54, "total_value": 15, "superstar": True},
    ]
    players = stars + [_filler(index, 8 if index < 12 else 2) for index in range(20)]
    session = DraftSession(players, team_count=8, draft_slot=1, budget=200, rounds=3)
    for _ in range(48):
        if len(session.picks) >= session.total_picks:
            break
        session.clock_ends = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.tick()
    names = {"Nikola Jokic", "Victor Wembanyama", "Luka Doncic"}
    sold = [pick for pick in session.picks if pick["player_name"] in names]
    assert len(sold) == 3
    assert all(pick["price"] >= 40 for pick in sold)
    by_team: dict[int, list[str]] = {}
    for pick in sold:
        by_team.setdefault(pick["team_index"], []).append(pick["player_name"])
    assert all(len(group) == 1 for group in by_team.values())


def test_a_raise_must_beat_the_current_offer() -> None:
    session = DraftSession(PLAYERS, team_count=2, draft_slot=1, budget=20, rounds=2)
    session.nominate("Guard")
    session.bid(2)
    assert session.on_block["bid"] == 2
    assert session.on_block["high_bidder"] == 0


def test_second_seat_waits_for_the_first_nomination() -> None:
    session = DraftSession(PLAYERS, team_count=2, draft_slot=2, budget=20, rounds=2)
    assert session.state()["can_nominate"] is False
    session.tick()
    assert session.on_block is not None
    session.clock_ends = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.tick()
    assert session.picks
    assert session.state()["can_nominate"] is True


def test_tick_without_a_session_returns_the_setup_screen(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(draft_server, "SESSION_PATH", tmp_path / "session.json")
    monkeypatch.setattr(draft_server, "SESSION", {"current": None})
    client = draft_server.app.test_client()
    tick = client.post("/draft/api/tick", json={})
    assert tick.status_code == 200
    assert tick.get_json()["started"] is False


def test_live_helper_reads_a_feed_line(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(draft_server, "HELPER_PATH", tmp_path / "helper.json")
    monkeypatch.setattr(draft_server, "save_sidecar", lambda session: None)
    monkeypatch.setattr(draft_server, "HELPER", {"current": None})
    monkeypatch.setattr(draft_server, "pool_for", lambda punts, team_count=4, budget=200: [
        {**PLAYERS[0], "player_name": "Nikola Jokić", "auction_value": 60, "yahoo_listed": 60, "stay_market": 72, "stretch_market": 85, "typical_low": 60, "typical_high": 85},
        {**PLAYERS[1], "auction_value": 20},
        {**PLAYERS[2], "auction_value": 10},
        {**PLAYERS[3], "auction_value": 8},
    ])
    client = draft_server.app.test_client()
    started = client.post("/helper/api/start", json={"team_count": 4, "budget": 200})
    assert started.status_code == 200
    assert started.get_json()["mode"] == "live"
    lookup = client.post("/helper/api/feed", json={"line": "jokic 68"})
    assert lookup.status_code == 200
    coach = lookup.get_json()["coach"]
    assert coach["player_name"] == "Nikola Jokić"
    assert coach["call"] == "stay"
    assert coach["stay"] == 72
    picked = client.post("/helper/api/pick", json={"player_name": "jokic"})
    assert picked.status_code == 200
    closed = client.post("/helper/api/close", json={"action": "me"})
    assert closed.status_code == 200
    payload = closed.get_json()
    assert payload["budget_left"] == 128
    taken = [slot["player"] for slot in payload["rosters"][0]["slots"] if slot.get("player")]
    assert taken[0]["player_name"] == "Nikola Jokić"
    assert taken[0]["price"] == 72
    cheap = client.post("/helper/api/start", json={"team_count": 16, "budget": 50})
    assert cheap.status_code == 400


def test_draft_page_starts_only_after_a_nomination_seat(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(draft_server, "SESSION_PATH", tmp_path / "session.json")
    monkeypatch.setattr(draft_server, "save_session", lambda session: None)
    monkeypatch.setattr(draft_server, "SESSION", {"current": None})
    monkeypatch.setattr(draft_server, "pool_for", lambda punts, team_count=2, budget=20: PLAYERS)
    client = draft_server.app.test_client()
    page = client.get("/draft")
    assert page.status_code == 200
    script = client.get("/static/draft.js")
    assert b"Where do you nominate?" in script.data
    missing = client.post("/draft/api/start", json={"team_count": 2})
    assert missing.status_code == 400
    started = client.post("/draft/api/start", json={"draft_slot": 1, "team_count": 2, "budget": 20})
    assert started.status_code == 200
    assert started.get_json()["can_nominate"] is True
