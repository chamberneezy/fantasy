import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yahoo_snapshot as snapshot  # noqa: E402


def test_status_comes_off_the_name_but_numerals_stay() -> None:
    assert snapshot.split_status("Chet HolmgrenO") == ("Chet Holmgren", "O")
    assert snapshot.split_status("Scotty Pippen Jr.Q") == ("Scotty Pippen Jr.", "Q")
    assert snapshot.split_status("Robert Williams IIIQ") == ("Robert Williams III", "Q")
    assert snapshot.split_status("Robert Williams III") == ("Robert Williams III", "")
    assert snapshot.split_status("Jusuf NurkićONo new player Notes") == ("Jusuf Nurkić", "O")
    assert snapshot.split_status("Doug McDermott") == ("Doug McDermott", "")


def test_short_names_expand_only_when_one_player_fits() -> None:
    known = ["Nickeil Alexander-Walker", "Jalen Williams", "Jaylin Williams"]
    assert snapshot.full_name("N. Alexander-Walker", known) == "Nickeil Alexander-Walker"
    assert snapshot.full_name("J. Williams", known) == "J. Williams"


def test_roster_rows_read_seats_and_skip_empty() -> None:
    rows = snapshot.roster_rows({"Lipicaneri": "PG Tre Jones CHI - PG,SG; PF (Empty); IL Kawhi LeonardO TOR - SG,SF,PF"}, {"Lipicaneri": "Mario"})
    assert list(rows["player_name"]) == ["Tre Jones", "Kawhi Leonard"]
    assert rows.iloc[0]["positions"] == "PG/SG"
    assert rows.iloc[1]["slot"] == "IL"
    assert rows.iloc[0]["manager"] == "Mario"


def test_a_roster_row_it_cannot_read_stops_the_import() -> None:
    with pytest.raises(ValueError):
        snapshot.roster_rows({"Lipicaneri": "nonsense"})


def test_free_agent_rows_keep_the_tag_and_ignore_tonight() -> None:
    rows = snapshot.free_agent_rows(["Saddiq Bey NOP SF,PF 7:00 pm vs ATL|158|103|33%", "Alex CarusoO OKC SG,SF|211|116|29%"])
    assert rows.iloc[0]["player_name"] == "Saddiq Bey"
    assert rows.iloc[0]["pct_rostered"] == "33"
    assert rows.iloc[1]["yahoo_status"] == "O"


def test_score_row_reads_makes_and_attempts(tmp_path) -> None:
    row = snapshot.score_row(2, "2026-10-30", "mine", "481|87/181|.481|37/48|.771|26|237|94|65|12|10|36|46|4")
    assert (row["fgm"], row["fga"], row["dd"], row["min"]) == (87.0, 181.0, 4.0, 481.0)
    path = tmp_path / "scores.csv"
    snapshot.save_score(path, [row])
    snapshot.save_score(path, [{**row, "pts": 240.0}])
    saved = pd.read_csv(path)
    assert len(saved) == 1
    assert saved.iloc[0]["pts"] == 240.0


def test_roster_cells_become_seat_lines_and_seats():
    assert snapshot.seat_text("IL", "Jalen SmithQNew Player Note CHI - PF,C") == "IL Jalen SmithQ CHI - PF,C"
    assert snapshot.seat_text("SF", "Derrick Jones Jr.Player Note LAC - SF,PF 4:30 pm vs CHA") == "SF Derrick Jones Jr. LAC - SF,PF"
    assert snapshot.seat_text("BN", "(Empty)") is None
    found = snapshot.seats([
        ("PG", "Collin GillespiePlayer Note PHX - PG,SG 4:00 pm vs LAL"),
        ("BN", "Mario HezonjaNew Player Note CLE - SF,PF"),
        ("BN", "Nikola JokićNew Player Note DEN - C"),
        ("IL", "Kawhi LeonardOPlayer Note TOR - SG,SF,PF 6:00 pm vs NYK"),
    ])
    assert found == [("PG", "Collin Gillespie", ""), ("BN1", "Mario Hezonja", ""), ("BN2", "Nikola Jokić", ""), ("IL", "Kawhi Leonard", "O")]


def test_adds_used_and_the_day_the_score_runs_through():
    assert snapshot.adds_used("You have used 2 of your 4 player adds for this week.") == 2
    assert snapshot.adds_used("nothing here") is None
    tips = ["2026-11-15T21:00:00Z", "2026-11-16T01:00:00Z"]
    assert snapshot.score_through("2026-11-15", tips, False, "2026-11-15T17:00:00Z") == "2026-11-14"
    assert snapshot.score_through("2026-11-15", tips, False, "2026-11-15T22:00:00Z") is None
    assert snapshot.score_through("2026-11-15", tips, True, "2026-11-16T04:00:00Z") == "2026-11-15"
    assert snapshot.score_through("2026-11-15", [], False, "2026-11-15T22:00:00Z") == "2026-11-14"


def test_session_follows_yahoo_and_logs_real_moves_only():
    session = {"week": 4, "adds_used": 2, "roster": [["PG", "Tristan Da Silva"], ["BN1", "Queta"]], "il": [], "moves": []}
    found = [("PG", "Tristan da Silva", ""), ("BN1", "Cam Spencer", ""), ("IL", "Kawhi Leonard", "O")]
    updated, changes = snapshot.sync_session(session, found, 3, 4, "2026-11-16")
    assert updated["roster"] == [["PG", "Tristan da Silva"], ["BN1", "Cam Spencer"]]
    assert updated["il"] == [["IL", "Kawhi Leonard"]]
    assert {"date": "2026-11-16", "drop": "Queta"} in updated["moves"]
    assert {"date": "2026-11-16", "add": "Cam Spencer"} in updated["moves"]
    assert not any(move.get("add") == "Tristan da Silva" for move in updated["moves"])
    assert updated["adds_used"] == 3 and "adds used 2 → 3" in changes


def test_team_headings_lose_yahoo_icon_glyphs():
    assert snapshot.team_name("Mother Tucker ") == "Mother Tucker"
    assert snapshot.team_name("  Brzi Botaničari ") == "Brzi Botaničari"
