"""Yahoo pages read in Mario's own browser, turned into the pad's hand-supplied files.

Read only: nothing here talks to Yahoo. The text comes from the Starting Rosters,
Player List and matchup pages (see context/daily_routine.md).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

import matchup

ROSTER_COLUMNS = ("fantasy_team", "manager", "slot", "player_name", "nba_team", "positions")
FREE_AGENT_COLUMNS = ("player_name", "nba_team", "positions", "yahoo_status", "yahoo_rank_pre", "pct_rostered")
STATUS_TAGS = ("INJ", "GTD", "SUSP", "NA", "O", "Q", "D", "P")
_ROW = re.compile(r"^(?P<slot>[A-Z]+) (?P<name>.+?) (?P<team>[A-Z]{2,4}) - (?P<positions>[A-Z,]+)$")
_NOTE = re.compile(r"(New Player Note|Player Note|No new player Notes)")


def split_status(name: str) -> tuple[str, str]:
    """Yahoo glues the injury tag to the name: ``Chet HolmgrenO``. Roman numerals stay."""
    cleaned = _NOTE.sub("", name).strip()
    for tag in STATUS_TAGS:
        if cleaned.endswith(tag) and len(cleaned) > len(tag) and cleaned[-len(tag) - 1] != " ":
            return cleaned[: -len(tag)].strip(), tag
    return cleaned, ""


def full_name(name: str, known: list[str]) -> str:
    """``N. Alexander-Walker`` to the one known name with that initial and surname."""
    match = re.match(r"^([A-Z])\. (.+)$", name)
    if not match:
        return name
    hits = [other for other in known if other.startswith(match[1]) and other.endswith(f" {match[2]}")]
    return hits[0] if len(hits) == 1 else name


def roster_rows(teams: dict[str, str], managers: dict[str, str] | None = None, known: list[str] | None = None) -> pd.DataFrame:
    """``{team: "PG Tre Jones CHI - PG,SG; BN ...; IL ..."}`` to ``league_rosters.csv`` rows."""
    rows = []
    for team, text in teams.items():
        for item in text.split(";"):
            item = item.strip()
            match = _ROW.match(item)
            if match is None:
                if item and "(Empty)" not in item:
                    raise ValueError(f"Cannot read roster row {item!r} on {team}")
                continue
            name, _ = split_status(match["name"])
            rows.append(
                {
                    "fantasy_team": team,
                    "manager": (managers or {}).get(team, ""),
                    "slot": match["slot"],
                    "player_name": full_name(name, known or []),
                    "nba_team": match["team"],
                    "positions": match["positions"].replace(",", "/"),
                }
            )
    return pd.DataFrame(rows, columns=list(ROSTER_COLUMNS))


def free_agent_rows(lines: list[str], known: list[str] | None = None) -> pd.DataFrame:
    """``Name TEAM POS,POS|pre-season rank|current rank|12%`` to ``free_agents.csv`` rows, best first."""
    rows = []
    for line in lines:
        parts = line.split("|")
        match = re.match(r"^(?P<name>.+?) (?P<team>[A-Z]{2,4}) (?P<positions>[A-Z,]+)(?: .*)?$", parts[0].strip())
        if match is None:
            raise ValueError(f"Cannot read free agent {line!r}")
        name, status = split_status(match["name"])
        rows.append(
            {
                "player_name": full_name(name, known or []),
                "nba_team": match["team"],
                "positions": match["positions"].replace(",", "/"),
                "yahoo_status": status,
                "yahoo_rank_pre": parts[1].strip(),
                "pct_rostered": parts[3].strip().rstrip("%"),
            }
        )
    return pd.DataFrame(rows, columns=list(FREE_AGENT_COLUMNS))


def score_row(week: int, through: str, side: str, row: str) -> dict:
    """One line of Yahoo's matchup table: ``MIN|FGM/A|FG%|FTM/A|FT%|3PM|PTS|REB|AST|ST|BLK|TO|PF|DD``."""
    cells = [cell.strip() for cell in row.split("|")]
    fgm, fga = cells[1].split("/")
    ftm, fta = cells[3].split("/")
    scored = {
        "min": cells[0], "fgm": fgm, "fga": fga, "ftm": ftm, "fta": fta, "fg3m": cells[5], "pts": cells[6], "reb": cells[7],
        "ast": cells[8], "stl": cells[9], "blk": cells[10], "to": cells[11], "pf": cells[12], "dd": cells[13],
    }
    return {"week": week, "through": through, "side": side, **{key: float(value) for key, value in scored.items()}}


def save_score(path: Path, rows: list[dict]) -> None:
    """Keep earlier scores; the same week, day and side is replaced."""
    columns = ["week", "through", "side", *("min" if stat == "mp" else stat for stat in matchup.STATS)]
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=columns)
    fresh = pd.DataFrame(rows, columns=columns)
    merged = pd.concat([frame for frame in (old, fresh) if len(frame)], ignore_index=True)
    merged = merged.drop_duplicates(["week", "through", "side"], keep="last")
    merged = merged.astype({column: int for column in columns if column not in ("through", "side")})
    merged[columns].to_csv(path, index=False)
