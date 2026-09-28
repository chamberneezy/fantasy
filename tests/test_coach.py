"""Stay / Stretch / Pass and the live-room feed line."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coach import build_card, call_for, match_player, parse_feed, stay_price, stretch_price
from market import quote
from room import apply_room, read_room
from sidecar import SidecarSession


PLAYERS = [
    {"player_name": "Nikola Jokić", "positions": "C", "auction_value": 71, "total_value": 24},
    {"player_name": "Victor Wembanyama", "positions": "C", "auction_value": 67, "total_value": 21},
    {"player_name": "Luka Dončić", "positions": "PG", "auction_value": 53, "total_value": 16},
    {"player_name": "Kevin Durant", "positions": "PF", "auction_value": 39, "total_value": 11},
]


def test_feed_lines_split_name_dollar_and_who() -> None:
    assert parse_feed("wemby") == {"query": "victor wembanyama", "amount": None, "action": "lookup"}
    assert parse_feed("wemby 52") == {"query": "victor wembanyama", "amount": 52, "action": "lookup"}
    assert parse_feed("bambi 72 sold") == {"query": "victor wembanyama", "amount": 72, "action": "sold"}
    assert parse_feed("kd 40 me") == {"query": "kevin durant", "amount": 40, "action": "me"}


def test_market_uses_yahoo_list_and_sale_averages() -> None:
    jokic = quote("Nikola Jokić")
    kawhi = quote("Kawhi Leonard")
    assert jokic["yahoo_listed"] == 60
    assert jokic["stay_market"] >= 70
    assert jokic["stretch_market"] >= 80
    assert kawhi["yahoo_listed"] == 27
    assert kawhi["auction_value"] == 27
    assert quote("Justin Edwards") is None
    assert quote("Thanasis Antetokounmpo") is None
    assert quote("jokic")["yahoo_listed"] == 60


def test_jokic_stay_and_stretch_match_the_room() -> None:
    assert stay_price(71, 200, 10, False) == 75
    assert stretch_price(71, 200, 10, False) == 80
    assert call_for(68, 75, 80) == "stay"
    assert call_for(78, 75, 80) == "stretch"
    assert call_for(85, 75, 80) == "pass"


def test_paying_eighty_for_jokic_locks_the_second_star() -> None:
    card = build_card(PLAYERS[0], 80, 200, 10, False, PLAYERS)
    assert card["tax"] == 5
    assert card["after"] == 120
    assert card["seats_after"] == 9
    assert card["call"] == "stretch"
    assert all(item["listed"] < 40 or item["player_name"] != "Victor Wembanyama" for item in card["next"])


def test_sold_and_me_work_without_a_dollar() -> None:
    session = SidecarSession(PLAYERS, team_count=4, budget=200)
    session.pick("jokic")
    session.close("me")
    assert session.picks[0]["player_name"] == "Nikola Jokić"
    assert session.picks[0]["price"] == 75
    assert session.budget_left == 125
    session.pick("wemby")
    session.close("sold")
    names = {item["player_name"] for item in session.available_players()}
    assert "Victor Wembanyama" not in names


def test_sidecar_logs_a_sale_and_your_buy() -> None:
    session = SidecarSession(PLAYERS, team_count=4, budget=200)
    session.feed("jokic")
    assert session.focus["player_name"] == "Nikola Jokić"
    session.feed("jokic 80 me")
    assert session.budget_left == 120
    assert session.picks[0]["player_name"] == "Nikola Jokić"
    session.feed("wemby 72 sold")
    names = {item["player_name"] for item in session.available_players()}
    assert "Victor Wembanyama" not in names
    assert "Nikola Jokić" not in names
    card = session.state()["coach"]
    assert card is None
    session.feed("luka 50")
    assert session.state()["coach"]["second_star"] is True
    assert session.state()["coach"]["call"] == "pass"


def test_one_star_hammer_does_not_reprice_the_tier() -> None:
    room = read_room(
        [{"price": 87, "listed": 60, "fair_stay": 72, "fair_stretch": 85, "auction_value": 60}],
        team_count=16,
        budget=200,
    )
    assert room["counts"]["star"] == 1
    assert room["factors"]["star"] == 1.0
    stay, stretch = apply_room(57, 57, 57, 200, 10, False, room)
    assert stay == 57
    assert stretch == 57


def test_two_hot_stars_lift_this_rooms_stay() -> None:
    room = read_room(
        [
            {"price": 87, "listed": 60, "fair_stay": 72, "fair_stretch": 85, "auction_value": 60},
            {"price": 78, "listed": 61, "fair_stay": 68, "fair_stretch": 74, "auction_value": 61},
        ],
        team_count=16,
        budget=200,
    )
    assert room["listening"] is True
    assert room["factors"]["star"] > 1.08
    stay, stretch = apply_room(57, 57, 57, 200, 10, False, room)
    assert stay > 57
    assert stay <= 70


def test_helper_learns_after_two_star_sales() -> None:
    session = SidecarSession(
        [
            {
                "player_name": "Nikola Jokić",
                "positions": "C",
                "auction_value": 60,
                "yahoo_listed": 60,
                "stay_market": 72,
                "stretch_market": 85,
                "typical_low": 60,
                "typical_high": 85,
                "total_value": 24,
            },
            {
                "player_name": "Victor Wembanyama",
                "positions": "C",
                "auction_value": 61,
                "yahoo_listed": 61,
                "stay_market": 68,
                "stretch_market": 74,
                "typical_low": 61,
                "typical_high": 74,
                "total_value": 21,
            },
            {
                "player_name": "Cade Cunningham",
                "positions": "PG",
                "auction_value": 57,
                "yahoo_listed": 57,
                "stay_market": 57,
                "stretch_market": 57,
                "typical_low": 57,
                "typical_high": 57,
                "total_value": 13,
            },
        ],
        team_count=16,
        budget=200,
    )
    session.feed("jokic 87 sold")
    session.feed("cade")
    first = session.state()["coach"]
    assert first["stay"] == 57
    assert first["room_factor"] == 1.0
    session.feed("wemby 78 sold")
    session.feed("cade")
    second = session.state()["coach"]
    assert second["fair_stay"] == 57
    assert second["stay"] > 57
    assert second["room_factor"] > 1.08
    assert second["room_factor"] == session.state()["room"]["factors"]["star"]


def test_match_reads_a_nickname() -> None:
    assert match_player("sga", [{"player_name": "Shai Gilgeous-Alexander", "auction_value": 55}])["player_name"] == "Shai Gilgeous-Alexander"
