"""Stay / Stretch / Pass and the live-room feed line."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coach import build_card, call_for, match_player, next_targets, parse_feed, stay_price, stretch_price
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
    assert parse_feed("jokic")["query"] == "nikola jokic"
    assert parse_feed("jokić")["query"] == "nikola jokic"
    assert parse_feed("wemby 52") == {"query": "victor wembanyama", "amount": 52, "action": "lookup"}
    assert parse_feed("bambi 72 sold") == {"query": "victor wembanyama", "amount": 72, "action": "sold"}
    assert parse_feed("kd 40 me") == {"query": "kevin durant", "amount": 40, "action": "me"}
    assert parse_feed("gobert keep") == {"query": "gobert", "amount": None, "action": "keep"}
    assert parse_feed("sarr locked") == {"query": "sarr", "amount": None, "action": "locked"}


def test_market_uses_yahoo_list_and_sale_averages() -> None:
    jokic = quote("Nikola Jokić")
    kawhi = quote("Kawhi Leonard")
    assert jokic["yahoo_listed"] == 60
    assert jokic["stay_market"] >= 100
    assert jokic["stretch_market"] >= 130
    assert quote("Luka Dončić")["stay_market"] >= 100
    assert kawhi["yahoo_listed"] == 27
    assert kawhi["auction_value"] == 27
    assert quote("Justin Edwards") is None
    assert quote("Thanasis Antetokounmpo") is None
    assert quote("jokic")["yahoo_listed"] == 60
    assert quote("Kevin Porter Jr.")["yahoo_listed"] == 3
    assert quote("Jaren Jackson Jr.")["yahoo_listed"] == 24
    assert quote("Kel'el Ware")["yahoo_listed"] == 16
    assert quote("VJ Edgecombe")["yahoo_listed"] == 12
    assert quote("Jimmy Butler")["yahoo_listed"] == 1
    assert quote("Nikola Vučević")["yahoo_listed"] == 1


def test_jokic_stay_and_stretch_match_the_room() -> None:
    assert stay_price(71, 200, 10, False) == 75
    assert stretch_price(71, 200, 10, False) == 80
    jokic = quote("jokic")
    player = {"stay_market": jokic["stay_market"], "stretch_market": jokic["stretch_market"]}
    stay = stay_price(60, 200, 10, False, player)
    stretch = stretch_price(60, 200, 10, False, player)
    assert stay >= 100
    assert stretch >= 130
    assert call_for(100, stay, stretch) == "stay"
    assert call_for(stretch + 1, stay, stretch) == "pass"
    assert stay_price(60, 80, 9, False, player) == 72
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


def test_nuclear_first_star_reprices_the_rest_of_the_board() -> None:
    room = read_room(
        [
            {
                "player_name": "Nikola Jokić",
                "price": 160,
                "listed": 60,
                "fair_stay": 108,
                "fair_stretch": 144,
                "auction_value": 60,
            }
        ],
        team_count=16,
        budget=200,
    )
    assert room["counts"]["star"] == 1
    assert room["listening"] is True
    assert room["factors"]["star"] > 1.08
    assert room["anchor"]["price"] == 160
    stay, stretch = apply_room(103, 137, 57, 200, 10, False, room)
    assert stay > 103
    assert "160" in room["note"]


def test_helper_moves_cade_after_a_nuclear_jokic() -> None:
    session = SidecarSession(
        [
            {
                "player_name": "Nikola Jokić",
                "positions": "C",
                "auction_value": 60,
                "yahoo_listed": 60,
                "stay_market": 108,
                "stretch_market": 144,
                "typical_low": 60,
                "typical_high": 144,
                "total_value": 24,
            },
            {
                "player_name": "Cade Cunningham",
                "positions": "PG",
                "auction_value": 57,
                "yahoo_listed": 57,
                "stay_market": 103,
                "stretch_market": 137,
                "typical_low": 57,
                "typical_high": 137,
                "total_value": 13,
            },
        ],
        team_count=16,
        budget=200,
    )
    session.feed("jokic 160 sold")
    session.feed("cade")
    card = session.state()["coach"]
    assert card["fair_stay"] == 103
    assert card["stay"] > 103
    assert card["room_factor"] > 1.08
    assert "160" in session.room()["note"]


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


def test_dynasty_keep_pays_list_and_skips_heat() -> None:
    session = SidecarSession(
        [
            {
                "player_name": "Alex Sarr",
                "positions": "C",
                "auction_value": 18,
                "yahoo_listed": 18,
                "stay_market": 18,
                "stretch_market": 22,
                "total_value": 6,
            },
            {
                "player_name": "Cade Cunningham",
                "positions": "PG",
                "auction_value": 57,
                "yahoo_listed": 57,
                "stay_market": 57,
                "stretch_market": 57,
                "total_value": 13,
            },
        ],
        team_count=16,
        budget=200,
    )
    session.pick("sarr")
    session.close("keep")
    assert session.picks[0]["price"] == 18
    assert session.picks[0]["kind"] == "dynasty"
    assert session.budget_left == 182
    session.pick("cade")
    session.close("locked")
    assert session.taken[-1]["kind"] == "dynasty"
    assert session.taken[-1]["yours"] is False
    room = session.room()
    assert room["counts"]["star"] == 0
    assert room["factors"]["star"] == 1.0


def test_dynasty_locked_stars_do_not_reprice_stay() -> None:
    room = read_room(
        [
            {"price": 60, "listed": 60, "fair_stay": 72, "fair_stretch": 85, "kind": "dynasty"},
            {"price": 61, "listed": 61, "fair_stay": 68, "fair_stretch": 74, "kind": "dynasty"},
        ],
        team_count=16,
        budget=200,
    )
    assert room["counts"]["star"] == 0
    assert room["factors"]["star"] == 1.0


def test_helper_next_names_and_table_seat() -> None:
    session = SidecarSession(PLAYERS, team_count=16, budget=200, draft_slot=7)
    state = session.state()
    assert state["nomination_slot"] == 7
    assert state["nominator"] == 1
    assert state["your_turn"] is False
    assert state["next"][0]["player_name"] == "Nikola Jokić"
    assert state["next"][0]["stay"] >= 1
    session.pick("jokic")
    session.close("sold")
    after = session.state()
    assert after["nominator"] == 2
    assert after["your_turn"] is False
    assert all(item["player_name"] != "Nikola Jokić" for item in after["next"])
    for _ in range(5):
        session.taken.append({"player_name": f"filler-{len(session.taken)}", "price": 1, "listed": 1, "fair_stay": 1, "fair_stretch": 1})
    assert session.state()["nominator"] == 7
    assert session.state()["your_turn"] is True
    cheap = next_targets(
        [{**PLAYERS[0], "yahoo_listed": 1, "auction_value": 1}, PLAYERS[3]],
        200,
        10,
        False,
    )
    assert [item["player_name"] for item in cheap] == ["Kevin Durant"]
    assert state["board"][0]["player_name"] == "Nikola Jokić"


def test_gone_crosses_off_at_stay_and_undo_restores() -> None:
    session = SidecarSession(PLAYERS, team_count=16, budget=200, draft_slot=5)
    session.gone("jokic")
    assert session.focus is None
    assert session.taken[0]["player_name"] == "Nikola Jokić"
    assert session.taken[0]["yours"] is False
    assert session.taken[0]["price"] == 75
    assert "Nikola Jokić" not in {row["player_name"] for row in session.state()["board"]}
    session.undo()
    assert session.taken == []
    assert any(row["player_name"] == "Nikola Jokić" for row in session.state()["board"])
    session.pick("jokic")
    session.close("me")
    session.gone("wemby")
    assert session.taken[-1]["player_name"] == "Victor Wembanyama"
    assert session.taken[-1]["yours"] is False
    assert session.taken[-1]["price"] == 70


def test_superstar_cannot_be_dynasty() -> None:
    session = SidecarSession(
        [{**PLAYERS[0], "yahoo_listed": 60, "superstar": True}],
        team_count=16,
        budget=200,
    )
    session.pick("jokic")
    try:
        session.close("keep")
    except ValueError as exc:
        assert "superstar" in str(exc).lower()
    else:
        raise AssertionError("keep should reject a superstar")
