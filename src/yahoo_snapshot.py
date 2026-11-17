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
# Link labels Yahoo prints right after a player's name. "Video Forecast" appeared on 17 Nov 2026.
_LABELS = r"(?:(?:New |No new )?[Pp]layer [Nn]otes?|Video Forecast)"
_NOTE = re.compile(_LABELS)


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


# -- the hourly reader on the home server (scripts/yahoo_read.py) -------------------------------
# Mario asked on 15 Nov 2026 for Yahoo to be read every hour on his server "gw". Still read only:
# the reader opens pages and reads their tables; it never clicks, submits or changes a lineup.

_CELL = re.compile(r"^(?P<name>.+?)\s*(?:" + _LABELS + r"\s*)*(?P<team>[A-Z]{2,4}) - (?P<positions>[A-Z,]+)(?:\s.*)?$")
_ADDS = re.compile(r"used (\d+) of your (\d+) player adds")


def team_name(text: str) -> str:
    """A team heading without Yahoo's icon-font glyphs (private-use characters) and spare spaces."""
    return " ".join(re.sub(r"[\ue000-\uf8ff]", "", text).split())


def seat_text(slot: str, cell: str) -> str | None:
    """A roster cell as ``roster_rows`` reads it: ``PG Name TEAM - PG,SG``. ``None`` for an empty seat."""
    cell = " ".join(cell.split())
    if not cell or "(Empty)" in cell:
        return None
    match = _CELL.match(cell)
    if match is None:
        raise ValueError(f"Cannot read roster cell {cell!r}")
    return f"{slot} {match['name'].strip()} {match['team']} - {match['positions']}"


def seats(rows: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """Team page rows (slot, player cell) to (slot, name, status); bench seats numbered BN1..BN5."""
    out, bench = [], 0
    for slot, cell in rows:
        text = seat_text(slot, cell)
        if text is None:
            continue
        name, status = split_status(_CELL.match(" ".join(cell.split()))["name"].strip())
        if slot == "BN":
            bench += 1
            slot = f"BN{bench}"
        out.append((slot, name, status))
    return out


def adds_used(text: str) -> int | None:
    """"You have used 2 of your 4 player adds for this week." → 2."""
    match = _ADDS.search(" ".join(text.split()))
    return int(match[1]) if match else None


def score_through(today: str, tips_today: list[str], today_final: bool, now_utc: str) -> str | None:
    """The last day whose games are fully in Yahoo's totals, or ``None`` while games are being played.

    Before the first tip it is yesterday; once every game of the day is final it is today.
    """
    from datetime import date, timedelta

    if not tips_today or now_utc < min(tips_today):
        return (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    return today if today_final else None


def sync_session(session: dict, found: list[tuple[str, str, str]], adds: int | None, week: int | None, today: str) -> tuple[dict, list[str]]:
    """Session roster and IL as Yahoo shows them; new and gone players logged as today's moves."""
    roster = [[slot, name] for slot, name, _ in found if slot != "IL"]
    il = [["IL", name] for slot, name, _ in found if slot == "IL"]
    from espn_feed import name_key

    before = {name_key(name): name for _, name in [*session.get("roster", []), *session.get("il", [])]}
    after = {name_key(name): name for _, name in [*roster, *il]}
    changes = []
    updated = dict(session)
    moves = list(session.get("moves", []))
    for key in sorted(set(after) - set(before)):
        moves.append({"date": today, "add": after[key]})
        changes.append(f"added {after[key]}")
    for key in sorted(set(before) - set(after)):
        moves.append({"date": today, "drop": before[key]})
        changes.append(f"dropped {before[key]}")
    if week is not None and week != session.get("week"):
        changes.append(f"week {session.get('week')} → {week}")
        updated["week"] = week
        if adds is None and session.get("adds_used"):
            changes.append(f"adds used {session.get('adds_used')} → 0 (new week)")
            updated["adds_used"] = 0
    if adds is not None and adds != session.get("adds_used"):
        changes.append(f"adds used {session.get('adds_used')} → {adds}")
        updated["adds_used"] = adds
    if roster != session.get("roster") or il != session.get("il"):
        changes.append("seats as in Yahoo")
    updated.update(roster=roster, il=il, moves=moves)
    return updated, changes
