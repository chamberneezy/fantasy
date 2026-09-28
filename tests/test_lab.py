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
    assert squad[0]["p"] > 0
    card = scenario(report, "jokic", buyer="room")
    assert len(card["squad"]) == 10
    assert card["squad"][0]["name"]


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
    page = client.get("/lab")
    assert page.status_code == 200
    started = client.post("/lab/api/run", json={"n": 24, "draft_slot": 5, "policy": "stay"})
    assert started.status_code == 200
    payload = started.get_json()
    assert payload["ready"] is True
    assert payload["n"] == 24
    assert "drafts" not in payload or payload["drafts"] == []
    asked = client.post("/lab/api/scenario", json={"player_name": "jokic", "buyer": "room"})
    assert asked.status_code == 200
    assert asked.get_json()["matched"] >= 1


def test_scenario_reads_a_field_sale(tmp_path) -> None:
    report = run_lab(build_pool(), n=80, draft_slot=5, seed=11)
    jokic = next(row for row in report["stars"] if "joki" in row["name"].lower())
    card = scenario(report, "jokic", buyer="room", price=jokic["median_field"] or jokic["median"])
    assert card["matched"] >= 1
    assert card["player_name"]
    assert "room" in card["why"].lower() or "Room" in card["buyer"]
