"""In-season pad: seeded 10, no IL, 4 adds/week."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from draft_room import build_pool
from season import ADDS_PER_WEEK, SeasonSession, load_season, reset_season, save_season


def test_opening_roster_is_yahoo_ten() -> None:
    session = SeasonSession(build_pool())
    names = [seat["player"]["player_name"] for seat in session.roster]
    assert names == [
        "Keyonte George",
        "Kawhi Leonard",
        "Jalen Williams",
        "John Collins",
        "Nikola Jokić",
        "Mario Hezonja",
        "Jrue Holiday",
        "Neemias Queta",
        "Dillon Brooks",
        "Tre Jones",
    ]
    assert len(names) == len(set(names))
    assert session.adds_used == 0
    tape = session.tape()
    assert tape["TO"] < 0
    assert tape["PF"] < 0
    assert "Mario Hezonja" not in {row["player_name"] for row in session.drops()}
    try:
        session.drop("hezonja")
        raise AssertionError("Hezonja must stay")
    except ValueError as exc:
        assert "stay" in str(exc).lower()
    try:
        session.to_il("Jalen Williams")
        raise AssertionError("no IL")
    except ValueError as exc:
        assert "no IL" in str(exc)


def test_add_drop_and_week(tmp_path) -> None:
    session = SeasonSession(build_pool())
    session.drop("Dillon Brooks")
    session.add("Andrew Nembhard")
    assert session.adds_used == 1
    owned = session.owned_names()
    assert "Andrew Nembhard" in owned
    assert "Dillon Brooks" not in owned
    assert "Mario Hezonja" in owned
    session.new_week()
    assert session.week == 2
    assert session.adds_used == 0
    path = tmp_path / "season_session.json"
    save_season(session, path)
    loaded = load_season(build_pool(), path)
    assert loaded.week == 2
    assert "Andrew Nembhard" in loaded.owned_names()
    reset_season(path)
    assert not path.exists()


def test_fifth_add_is_blocked() -> None:
    session = SeasonSession(build_pool())
    session.adds_used = 0
    session.drop("Dillon Brooks")
    session.drop("Jrue Holiday")
    session.drop("Neemias Queta")
    session.drop("John Collins")
    session.add("Andrew Nembhard")
    session.add("Toumani Camara")
    session.add("Brook Lopez")
    session.add("Keon Ellis")
    assert session.adds_used == ADDS_PER_WEEK
    session.drop("Tre Jones")
    try:
        session.add("Sandro Mamukelashvili")
        raise AssertionError("fifth add should fail")
    except ValueError as exc:
        assert "4" in str(exc)


def test_streamers_are_cheap_and_not_on_the_ten() -> None:
    session = SeasonSession(build_pool())
    rows = session.streamers()
    names = {row["player_name"] for row in rows}
    assert names
    assert "Nikola Jokić" not in names
    assert "Tre Jones" not in names
    assert all(row["listed"] <= 8 for row in rows)
    assert all("average" not in row["player_name"].lower() for row in rows)


def test_season_http_seeds_and_resets(tmp_path, monkeypatch) -> None:
    import draft_server
    import season as season_mod

    path = tmp_path / "season.json"
    monkeypatch.setattr(season_mod, "SEASON_PATH", path)
    monkeypatch.setattr(draft_server, "SEASON", {"current": None})
    client = draft_server.app.test_client()
    home = client.get("/")
    assert home.status_code == 200
    assert b"/season" in home.data
    page = client.get("/season")
    assert page.status_code == 200
    started = client.post("/season/api/start", json={})
    assert started.status_code == 200
    payload = started.get_json()
    assert payload["started"] is True
    assert payload["adds_left"] == 4
    assert payload["il_enabled"] is False
    names = [row["player_name"] for row in payload["roster"]]
    assert "Nikola Jokić" in names
    assert "Mario Hezonja" in names
    assert "Tre Jones" in names
    hezonja = next(row for row in payload["roster"] if row["player_name"] == "Mario Hezonja")
    assert hezonja["protected"] is True
    dropped = client.post("/season/api/drop", json={"query": "dillon brooks"})
    assert dropped.status_code == 200
    added = client.post("/season/api/add", json={"query": "nembhard"})
    assert added.status_code == 200
    assert added.get_json()["adds_left"] == 3
    blocked = client.post("/season/api/drop", json={"query": "hezonja"})
    assert blocked.status_code == 400
    wiped = client.post("/season/api/reset")
    assert wiped.status_code == 200
    assert wiped.get_json()["started"] is False
