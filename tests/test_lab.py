"""Headless auction lab: bots in and over the room range."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from draft_room import build_pool
from lab import run_lab, scenario, simulate_draft


def _pieces():
    from lab import _piece

    return [_piece(player) for player in build_pool()]


def test_one_draft_fills_ten_seats() -> None:
    draft = simulate_draft(_pieces(), draft_slot=5, seed=7)
    assert len(draft["yours"]) == 10
    assert draft["leftover"] >= 0
    assert all(item["price"] >= 1 for item in draft["yours"])
    assert {item["slot_id"] for item in draft["yours"]} == {
        "PG",
        "SG",
        "SF",
        "PF",
        "C",
        "BN1",
        "BN2",
        "BN3",
        "BN4",
        "BN5",
    }


def test_report_has_a_probable_squad() -> None:
    report = run_lab(build_pool(), n=30, draft_slot=5, seed=4)
    squad = report["you"]["squad"]
    assert [row["label"] for row in squad] == ["PG", "SG", "SF", "PF", "C", "BN", "BN", "BN", "BN", "BN"]
    assert all(row["name"] for row in squad)
    names = [row["name"] for row in squad]
    assert len(names) == len(set(names))
    headline = set(names)
    assert all(alt["name"] not in headline for row in squad for alt in row.get("alts") or [])
    assert squad[0]["p"] > 0
    card = scenario(report, "jokic", buyer="room")
    assert len(card["squad"]) == 10
    assert card["squad"][0]["name"]
    card_names = [row["name"] for row in card["squad"] if row["name"]]
    assert len(card_names) == len(set(card_names))


def test_probable_squad_does_not_repeat_a_name() -> None:
    from lab import _squad

    drafts = []
    for _ in range(8):
        drafts.append(
            {
                "yours": [
                    {"name": "Domantas Sabonis", "price": 50, "slot_id": "BN1"},
                    {"name": "Jamal Murray", "price": 40, "slot_id": "BN2"},
                ]
            }
        )
    for _ in range(7):
        drafts.append(
            {
                "yours": [
                    {"name": "Karl-Anthony Towns", "price": 41, "slot_id": "BN1"},
                    {"name": "Domantas Sabonis", "price": 51, "slot_id": "BN2"},
                ]
            }
        )
    squad = {row["id"]: row for row in _squad(drafts)}
    assert squad["BN1"]["name"] == "Domantas Sabonis"
    assert squad["BN2"]["name"] == "Jamal Murray"
    assert all(alt["name"] != "Domantas Sabonis" for alt in squad["BN2"]["alts"])


def test_same_player_cannot_headline_two_seats() -> None:
    from lab import _squad

    drafts = [
        {
            "yours": [
                {"name": "Domantas Sabonis", "price": 51, "slot_id": "BN1"},
                {"name": "Domantas Sabonis", "price": 51, "slot_id": "BN2"},
                {"name": "Josh Giddey", "price": 38, "slot_id": "PG"},
            ]
        }
        for _ in range(10)
    ]
    squad = _squad(drafts)
    names = [row["name"] for row in squad if row["name"]]
    assert names.count("Domantas Sabonis") == 1
    assert len(names) == len(set(names))
    pairs = [(row["name"], row["price"]) for row in squad if row["name"]]
    assert len(pairs) == len(set(pairs))


def test_lab_board_skips_tiny_sample_two_ways() -> None:
    from lab import _draftable

    players = build_pool()
    alondes = next(player for player in players if player["player_name"] == "Alondes Williams")
    giddey = next(player for player in players if "giddey" in player["player_name"].lower())
    assert _draftable(alondes) is False
    assert _draftable(giddey) is True
    report = run_lab(players, n=24, draft_slot=9, policy="stretch", seed=5)
    names = {row["name"] for row in report["you"]["squad"]}
    assert "Alondes Williams" not in names
    assert len(names) == 10


def test_jokic_does_not_sell_for_a_dollar() -> None:
    report = run_lab(build_pool(), n=40, draft_slot=5, seed=3)
    jokic = next(row for row in report["stars"] if "joki" in row["name"].lower())
    assert jokic["median"] >= 50
    assert jokic["p25"] >= 40
    assert jokic["listed"] == 60


def test_lab_http_runs_a_short_batch(tmp_path, monkeypatch) -> None:
    import draft_server

    monkeypatch.setattr(draft_server, "LAB_PATH", tmp_path / "lab.json")
    monkeypatch.setattr(draft_server, "save_report", lambda report: None)
    monkeypatch.setattr(draft_server, "LAB", {"report": None})
    client = draft_server.app.test_client()
    home = client.get("/")
    assert home.status_code == 200
    assert b"data-home-reset" in home.data
    page = client.get("/lab")
    assert page.status_code == 200
    started = client.post("/lab/api/run", json={"n": 24, "draft_slot": 5, "policy": "stay"})
    assert started.status_code == 200
    payload = started.get_json()
    assert payload["ready"] is True
    assert payload["n"] == 24
    stretched = client.post("/lab/api/run", json={"n": 24, "draft_slot": 1, "policy": "stretch"})
    assert stretched.status_code == 200
    other = stretched.get_json()
    assert other["draft_slot"] == 1
    assert other["policy"] == "stretch"
    assert other["n"] == 24
    assert "drafts" not in payload or payload["drafts"] == []
    asked = client.post("/lab/api/scenario", json={"player_name": "jokic", "buyer": "room"})
    assert asked.status_code == 200
    assert asked.get_json()["matched"] >= 1
    wiped = client.post("/lab/api/reset")
    assert wiped.status_code == 200
    assert wiped.get_json()["ready"] is False


def test_saved_report_cannot_keep_a_duplicate_name(tmp_path) -> None:
    from lab import load_report, save_report

    path = tmp_path / "lab.json"
    save_report(
        {
            "you": {
                "squad": [
                    {"id": "BN1", "label": "BN", "name": "Domantas Sabonis", "p": 0.2, "price": 51, "alts": []},
                    {"id": "BN2", "label": "BN", "name": "Domantas Sabonis", "p": 0.16, "price": 51, "alts": []},
                ]
            },
            "drafts": [
                {
                    "yours": [
                        ["Domantas Sabonis", 51, "BN1"],
                        ["Josh Giddey", 38, "PG"],
                    ]
                }
            ],
        },
        path,
    )
    loaded = load_report(path)
    names = [row["name"] for row in loaded["you"]["squad"] if row["name"]]
    assert names.count("Domantas Sabonis") == 1
    assert len(names) == len(set(names))


def test_scenario_reads_a_field_sale() -> None:
    report = run_lab(build_pool(), n=80, draft_slot=5, seed=11)
    jokic = next(row for row in report["stars"] if "joki" in row["name"].lower())
    card = scenario(report, "jokic", buyer="room", price=jokic["median_field"] or jokic["median"])
    assert card["matched"] >= 1
    assert card["player_name"]
    assert "room" in card["why"].lower() or "Room" in card["buyer"]
