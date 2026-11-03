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
