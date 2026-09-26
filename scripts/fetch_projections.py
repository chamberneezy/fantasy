"""Download 2025-26 per-game stats and write data/projections.csv.

Source: Basketball-Reference regular-season per-game table. Players who
changed teams are kept once, on the combined 2TM/3TM row. Positions on
that table are primary only, so multi-position eligibility is not included.
"""

from __future__ import annotations

import csv
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_URL = "https://www.basketball-reference.com/leagues/NBA_2026_per_game.html"
SEASON = "2025-26"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "projections.csv"

COMBINED_TEAMS = {"2TM", "3TM", "4TM", "5TM"}

ENGINE_COLUMNS = [
    "player_name",
    "positions",
    "pts",
    "reb",
    "ast",
    "stl",
    "blk",
    "fg3m",
    "fg_pct",
    "fga",
    "ft_pct",
    "fta",
    "to",
]

EXTRA_COLUMNS = [
    "season",
    "team",
    "age",
    "games",
    "games_started",
    "mp",
    "fg",
    "fg3a",
    "fg3_pct",
    "fg2",
    "fg2a",
    "fg2_pct",
    "efg_pct",
    "ft",
    "orb",
    "drb",
    "pf",
    "awards",
]

STAT_MAP = {
    "pts": "pts_per_g",
    "reb": "trb_per_g",
    "ast": "ast_per_g",
    "stl": "stl_per_g",
    "blk": "blk_per_g",
    "fg3m": "fg3_per_g",
    "fg_pct": "fg_pct",
    "fga": "fga_per_g",
    "ft_pct": "ft_pct",
    "fta": "fta_per_g",
    "to": "tov_per_g",
    "age": "age",
    "games": "games",
    "games_started": "games_started",
    "mp": "mp_per_g",
    "fg": "fg_per_g",
    "fg3a": "fg3a_per_g",
    "fg3_pct": "fg3_pct",
    "fg2": "fg2_per_g",
    "fg2a": "fg2a_per_g",
    "fg2_pct": "fg2_pct",
    "efg_pct": "efg_pct",
    "ft": "ft_per_g",
    "orb": "orb_per_g",
    "drb": "drb_per_g",
    "pf": "pf_per_g",
}

RATE_COLUMNS = {"fg_pct", "ft_pct", "fg3_pct", "fg2_pct", "efg_pct"}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.capture = False
        self.rows: list[dict[str, str]] = []
        self._current: list[tuple[str, str]] = []
        self._cell = ""
        self._stat: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "per_game_stats":
            self.in_table = True
        if not self.in_table:
            return
        if tag == "tr":
            self._current = []
        if tag in ("td", "th"):
            self.capture = True
            self._stat = attributes.get("data-stat")
            self._cell = ""

    def handle_endtag(self, tag: str) -> None:
        if not self.in_table:
            return
        if tag in ("td", "th") and self.capture:
            stat = self._stat or ""
            self._current.append((stat, " ".join(self._cell.split())))
            self.capture = False
        if tag == "tr" and self._current:
            self.rows.append(dict(self._current))
            self._current = []
        if tag == "table":
            self.in_table = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self._cell += data


def _download() -> str:
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; fantasy-projections/1.0)"},
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_number(value: str, column: str) -> float:
    text = value.strip()
    if not text:
        return 0.0
    if text.startswith("."):
        text = "0" + text
    number = float(text)
    if column in RATE_COLUMNS and number > 1:
        number = number / 100
    return number


def _one_row_per_player(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    players = [
        row
        for row in rows
        if row.get("name_display") and row.get("name_display") != "Player"
    ]
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in players:
        grouped.setdefault(row["name_display"], []).append(row)

    chosen: list[dict[str, str]] = []
    for name, group in grouped.items():
        combined = [row for row in group if row.get("team_name_abbr") in COMBINED_TEAMS]
        chosen.append(combined[0] if combined else group[0])
        del name
    return chosen


def _to_record(row: dict[str, str]) -> dict[str, object]:
    record: dict[str, object] = {
        "player_name": row.get("name_display", ""),
        "positions": (row.get("pos") or "").replace("-", "/"),
        "season": SEASON,
        "team": row.get("team_name_abbr", ""),
        "awards": row.get("awards", ""),
    }
    for column, source in STAT_MAP.items():
        record[column] = _parse_number(row.get(source, ""), column)
    return record


def build_rows(html: str) -> list[dict[str, object]]:
    parser = _TableParser()
    parser.feed(html)
    return [_to_record(row) for row in _one_row_per_player(parser.rows)]


def write_projections(rows: list[dict[str, object]], path: Path = OUTPUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ENGINE_COLUMNS + EXTRA_COLUMNS
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def main() -> None:
    rows = build_rows(_download())
    path = write_projections(rows)
    print(f"Wrote {len(rows)} players to {path}")


if __name__ == "__main__":
    main()
