"""This season's schedule, rosters and box scores from ESPN's free public API. Never Yahoo.

Writes the same files as ``nba_feed`` (schedule.csv, players.csv,
gamelogs_<season>.csv) so nothing downstream changes. Runs from a GitHub
runner, which stats.nba.com and cdn.nba.com refuse (probe, 25 Oct 2026).

Ids: last season's logs and the outlook use NBA person ids. ESPN athletes are
matched to them once by name (``espn_ids.csv``, committed); a player with no
NBA id yet gets ``ESPN_ID_OFFSET + espn id`` and is listed as unmatched.
Game ids are ESPN event ids for this season.
"""

from __future__ import annotations

import json
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import injuries
import nba_feed

API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_SEASON = 2027  # ESPN names a season by the year it ends
REGULAR_SEASON = 2
IDS_PATH = nba_feed.FEED_DIR / "espn_ids.csv"
ID_COLUMNS = ("espn_id", "player_id", "player_name")
ESPN_ID_OFFSET = 2_000_000_000
EASTERN = ZoneInfo("America/New_York")
PAUSE_SECONDS = 0.3
HEADERS = {"User-Agent": "Mozilla/5.0"}
# ESPN's short codes that differ from the NBA's.
TEAM_CODES = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
# ESPN positions to the NBA feed's G / F / C.
POSITIONS = {"PG": "G", "SG": "G", "G": "G", "SF": "F", "PF": "F", "F": "F", "C": "C"}
# Box score labels → log columns. "FG", "3PT", "FT" are "made-attempted".
DOUBLE_DOUBLE_STATS = ("pts", "reb", "ast", "stl", "blk")


def team_code(code: object) -> str:
    text = str(code or "").strip().upper()
    return TEAM_CODES.get(text, text)


def name_key(name: object) -> str:
    """Accents, dots, apostrophes, hyphens and suffixes off: "Nikola Jokić" → "nikola jokic"."""
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    for mark in (".", "'", "’", "-"):
        text = text.replace(mark, " " if mark == "-" else "")
    words = [word for word in text.split() if word not in ("jr", "sr", "ii", "iii", "iv")]
    return " ".join(words)


def _get(session, path: str, **params) -> dict:
    response = session.get(f"{API}/{path}", params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def eastern_day(utc: str) -> str:
    moment = datetime.fromisoformat(utc.replace("Z", "+00:00"))
    return moment.astimezone(EASTERN).date().isoformat()


def utc_stamp(utc: str) -> str:
    """ESPN's "2026-10-24T22:00Z" as the feed's "2026-10-24T22:00:00Z"."""
    moment = datetime.fromisoformat(utc.replace("Z", "+00:00"))
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- schedule -----------------------------------------------------------------

def shape_schedule(events: list[dict]) -> pd.DataFrame:
    """Regular-season games from team schedule events; ``date`` is the US Eastern day."""
    rows = []
    for event in events:
        if (event.get("seasonType") or {}).get("type") != REGULAR_SEASON:
            continue
        competition = (event.get("competitions") or [{}])[0]
        sides = {side.get("homeAway"): team_code((side.get("team") or {}).get("abbreviation")) for side in competition.get("competitors") or []}
        if not sides.get("home") or not sides.get("away") or not event.get("date"):
            continue
        status = ((competition.get("status") or {}).get("type") or {}).get("name", "")
        if status == "STATUS_POSTPONED":
            continue
        rows.append(
            {
                "game_id": str(event["id"]),
                "date": eastern_day(event["date"]),
                "tip_utc": utc_stamp(event["date"]),
                "home": sides["home"],
                "away": sides["away"],
                "label": "",
                "final": status == "STATUS_FINAL",
            }
        )
    frame = pd.DataFrame(rows, columns=[*nba_feed.SCHEDULE_COLUMNS, "final"])
    frame = frame.drop_duplicates("game_id")
    return frame.sort_values(["date", "tip_utc", "game_id"], kind="mergesort").reset_index(drop=True)


def fetch_teams(session) -> list[tuple[str, str]]:
    payload = _get(session, "teams")
    teams = payload["sports"][0]["leagues"][0]["teams"]
    return [(str(item["team"]["id"]), team_code(item["team"]["abbreviation"])) for item in teams]


def fetch_schedule(session, teams: list[tuple[str, str]]) -> pd.DataFrame:
    events = []
    for team_id, _ in teams:
        events += _get(session, f"teams/{team_id}/schedule", season=ESPN_SEASON, seasontype=REGULAR_SEASON).get("events") or []
        time.sleep(PAUSE_SECONDS)
    return shape_schedule(events)


# -- players ------------------------------------------------------------------

def fetch_rosters(session, teams: list[tuple[str, str]]) -> pd.DataFrame:
    rows = []
    for team_id, code in teams:
        for athlete in _get(session, f"teams/{team_id}/roster").get("athletes") or []:
            rows.append(
                {
                    "espn_id": int(athlete["id"]),
                    "espn_name": str(athlete.get("displayName") or ""),
                    "team": code,
                    "nba_position": POSITIONS.get(((athlete.get("position") or {}).get("abbreviation") or "").upper(), ""),
                }
            )
        time.sleep(PAUSE_SECONDS)
    return pd.DataFrame(rows, columns=["espn_id", "espn_name", "team", "nba_position"])


def match_ids(espn: pd.DataFrame, known: pd.DataFrame, nba_players: pd.DataFrame) -> pd.DataFrame:
    """ESPN id → NBA id and the NBA's spelling. Known pairs stay; new ones are matched by name.

    ``nba_players`` is any table with ``player_id`` and ``player_name`` (the NBA
    player index, or past logs). A name that matches two NBA ids is left unmatched.
    """
    pairs = {int(row.espn_id): (int(row.player_id), str(row.player_name)) for row in known.itertuples()}
    by_name: dict[str, set[tuple[int, str]]] = {}
    for row in nba_players.drop_duplicates("player_id").itertuples():
        by_name.setdefault(name_key(row.player_name), set()).add((int(row.player_id), str(row.player_name)))
    for row in espn.itertuples():
        if int(row.espn_id) in pairs:
            continue
        found = by_name.get(name_key(row.espn_name), set())
        if len(found) == 1:
            pairs[int(row.espn_id)] = next(iter(found))
    rows = [{"espn_id": espn_id, "player_id": player_id, "player_name": name} for espn_id, (player_id, name) in sorted(pairs.items())]
    return pd.DataFrame(rows, columns=list(ID_COLUMNS))


def shape_players(espn: pd.DataFrame, ids: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """players.csv rows with NBA ids where known; also the ESPN names left without one."""
    pairs = {int(row.espn_id): (int(row.player_id), str(row.player_name)) for row in ids.itertuples()}
    rows, unmatched = [], []
    for row in espn.itertuples():
        player_id, name = pairs.get(int(row.espn_id), (ESPN_ID_OFFSET + int(row.espn_id), str(row.espn_name)))
        if int(row.espn_id) not in pairs:
            unmatched.append(str(row.espn_name))
        rows.append({"player_id": player_id, "player_name": name, "team": row.team, "nba_position": row.nba_position})
    frame = pd.DataFrame(rows, columns=list(nba_feed.PLAYER_COLUMNS)).drop_duplicates("player_id")
    return frame.reset_index(drop=True), sorted(unmatched)


# -- box scores ---------------------------------------------------------------

def _made_attempted(text: str) -> tuple[int, int]:
    made, _, attempted = str(text).partition("-")
    try:
        return int(made), int(attempted)
    except ValueError:
        return 0, 0


def _number(text: object) -> float:
    try:
        return float(str(text).replace("+", ""))
    except ValueError:
        return 0.0


def shape_box(summary: dict, game: dict, ids: dict[int, tuple[int, str]]) -> list[dict]:
    """Log rows for one finished game: players with minutes only, the feed's columns."""
    rows = []
    for side in (summary.get("boxscore") or {}).get("players") or []:
        team = team_code((side.get("team") or {}).get("abbreviation"))
        home = 1 if team == game["home"] else 0
        opp = game["away"] if home else game["home"]
        for block in side.get("statistics") or []:
            labels = [label.upper() for label in block.get("labels") or []]
            for athlete in block.get("athletes") or []:
                values = dict(zip(labels, athlete.get("stats") or []))
                minutes = _number(values.get("MIN", 0))
                if athlete.get("didNotPlay") or minutes <= 0:
                    continue
                espn_id = int((athlete.get("athlete") or {}).get("id"))
                player_id, name = ids.get(espn_id, (ESPN_ID_OFFSET + espn_id, str((athlete.get("athlete") or {}).get("displayName") or "")))
                fgm, fga = _made_attempted(values.get("FG", "0-0"))
                fg3m, _ = _made_attempted(values.get("3PT", "0-0"))
                ftm, fta = _made_attempted(values.get("FT", "0-0"))
                row = {
                    "player_id": player_id,
                    "player_name": name,
                    "team": team,
                    "game_id": str(game["game_id"]),
                    "date": game["date"],
                    "opp": opp,
                    "home": home,
                    "min": minutes,
                    "fgm": fgm,
                    "fga": fga,
                    "ftm": ftm,
                    "fta": fta,
                    "fg3m": fg3m,
                    "pts": _number(values.get("PTS", 0)),
                    "reb": _number(values.get("REB", 0)),
                    "ast": _number(values.get("AST", 0)),
                    "stl": _number(values.get("STL", 0)),
                    "blk": _number(values.get("BLK", 0)),
                    "to": _number(values.get("TO", 0)),
                    "pf": _number(values.get("PF", 0)),
                }
                row["dd"] = 1 if sum(row[stat] >= 10 for stat in DOUBLE_DOUBLE_STATS) >= 2 else 0
                rows.append(row)
    return rows


def fetch_logs(session, schedule: pd.DataFrame, old: pd.DataFrame, ids: dict[int, tuple[int, str]]) -> tuple[pd.DataFrame, int]:
    """Finished games not yet in ``old``, one summary call each. Returns all logs and the games added."""
    have = set(old["game_id"].astype(str)) if len(old) else set()
    todo = schedule.loc[schedule["final"] & ~schedule["game_id"].astype(str).isin(have)]
    rows = []
    for game in todo.to_dict("records"):
        rows += shape_box(_get(session, "summary", event=game["game_id"]), game, ids)
        time.sleep(PAUSE_SECONDS)
    added = pd.DataFrame(rows, columns=list(nba_feed.LOG_COLUMNS))
    frames = [frame for frame in (old, added) if len(frame)]
    logs = pd.concat(frames, ignore_index=True) if frames else added
    logs = logs.drop_duplicates(["game_id", "player_id"], keep="last")
    return logs.sort_values(["date", "game_id", "player_id"], kind="mergesort").reset_index(drop=True), int(len(todo))


# -- refresh ------------------------------------------------------------------

def _read(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, **kwargs) if path.exists() else pd.DataFrame()


def refresh(feed_dir: Path | None = None) -> dict:
    """Pull schedule, rosters, new box scores and injuries; write the pad's files. A failed step keeps the old file."""
    import requests

    target = feed_dir or nba_feed.FEED_DIR
    target.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    report: dict = {"source": "espn", "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": {}, "errors": {}}
    logs_path = target / f"gamelogs_{nba_feed.SEASON}.csv"
    ids_path = target / IDS_PATH.name
    try:
        teams = fetch_teams(session)
        schedule = fetch_schedule(session, teams)
        if schedule.empty:
            raise ValueError("empty schedule")
        schedule[list(nba_feed.SCHEDULE_COLUMNS)].to_csv(target / nba_feed.SCHEDULE_PATH.name, index=False)
        report["rows"]["schedule"] = int(len(schedule))

        espn = fetch_rosters(session, teams)
        known = _read(ids_path)
        known = known if len(known) else pd.DataFrame(columns=list(ID_COLUMNS))
        index = pd.concat(
            [frame[["player_id", "player_name"]] for frame in (_read(target / nba_feed.PLAYERS_PATH.name), _read(target / f"gamelogs_{nba_feed.LAST_SEASON}.csv")) if len(frame)],
            ignore_index=True,
        ) if (target / nba_feed.PLAYERS_PATH.name).exists() or (target / f"gamelogs_{nba_feed.LAST_SEASON}.csv").exists() else pd.DataFrame(columns=["player_id", "player_name"])
        ids = match_ids(espn, known, index)
        ids.to_csv(ids_path, index=False)
        players, unmatched = shape_players(espn, ids)
        players.to_csv(target / nba_feed.PLAYERS_PATH.name, index=False)
        report["rows"]["players"] = int(len(players))
        report["unmatched"] = unmatched

        pairs = {int(row.espn_id): (int(row.player_id), str(row.player_name)) for row in ids.itertuples()}
        old = _read(logs_path, dtype={"game_id": str})
        # Logs from the NBA feed carry NBA game ids; the ESPN feed starts its own file.
        if len(old) and old["game_id"].astype(str).str.startswith("00").any():
            old = pd.DataFrame(columns=list(nba_feed.LOG_COLUMNS))
        logs, games = fetch_logs(session, schedule, old, pairs)
        logs.to_csv(logs_path, index=False)
        report["rows"][f"logs {nba_feed.SEASON}"] = int(len(logs))
        report["rows"]["new games"] = games
    except Exception as exc:  # a public endpoint; any failure keeps the old files
        report["errors"]["espn"] = str(exc)[:300]
    try:
        report_injuries = injuries.fetch_injuries()
        if report_injuries.empty:
            raise ValueError("empty response")
        report_injuries.to_csv(target / nba_feed.INJURIES_PATH.name, index=False)
        report["rows"]["injuries"] = int(len(report_injuries))
    except Exception as exc:
        report["errors"]["injuries"] = str(exc)[:200]
    (target / nba_feed.META_PATH.name).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
