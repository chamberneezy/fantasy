"""Free NBA stats feed for the season pad: schedule, rosters, game logs.

Everything comes from the public NBA stats endpoints through ``nba_api``.
Nothing here touches Yahoo. Files land in ``data/season/`` and the pad reads
them from disk, so the pad still opens when the feed is down.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd

import injuries

ROOT = Path(__file__).resolve().parents[1]
FEED_DIR = ROOT / "data" / "season"
SCHEDULE_PATH = FEED_DIR / "schedule.csv"
PLAYERS_PATH = FEED_DIR / "players.csv"
INJURIES_PATH = FEED_DIR / "injuries.csv"
META_PATH = FEED_DIR / "feed.json"
# Players Mario wants projected off an older season (missed last year), as
# ``player_name,season``. Their games from that season land in OLDER_LOGS_PATH.
COMEBACKS_PATH = FEED_DIR / "comebacks.csv"
OLDER_LOGS_PATH = FEED_DIR / "gamelogs_older.csv"
# Next season's per-game lines from the three-season model in ``outlook.py``.
OUTLOOK_PATH = FEED_DIR / "outlook.csv"

SEASON = "2026-27"
LAST_SEASON = "2025-26"
REGULAR_SEASON_PREFIX = "002"
PAUSE_SECONDS = 1.0

SCHEDULE_COLUMNS = ("game_id", "date", "tip_utc", "home", "away", "label")
PLAYER_COLUMNS = ("player_id", "player_name", "team", "nba_position")
LOG_COLUMNS = (
    "player_id",
    "player_name",
    "team",
    "game_id",
    "date",
    "opp",
    "home",
    "min",
    "fgm",
    "fga",
    "ftm",
    "fta",
    "fg3m",
    "pts",
    "reb",
    "ast",
    "stl",
    "blk",
    "to",
    "pf",
    "dd",
)

_LOG_STATS = {
    "min": "MIN",
    "fgm": "FGM",
    "fga": "FGA",
    "ftm": "FTM",
    "fta": "FTA",
    "fg3m": "FG3M",
    "pts": "PTS",
    "reb": "REB",
    "ast": "AST",
    "stl": "STL",
    "blk": "BLK",
    "to": "TOV",
    "pf": "PF",
    "dd": "DD2",
}


def logs_path(season: str) -> Path:
    return FEED_DIR / f"gamelogs_{season}.csv"


def shape_schedule(games: pd.DataFrame) -> pd.DataFrame:
    """Regular-season games with both teams known. ``date`` is the US Eastern day."""
    if games.empty:
        return pd.DataFrame(columns=list(SCHEDULE_COLUMNS))
    game_ids = games["gameId"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    keep = game_ids.str.startswith(REGULAR_SEASON_PREFIX)
    if "postponedStatus" in games.columns:
        keep &= ~games["postponedStatus"].astype(str).str.upper().isin({"Y", "YES", "POSTPONED"})
    home = games["homeTeam_teamTricode"].fillna("").astype(str).str.strip()
    away = games["awayTeam_teamTricode"].fillna("").astype(str).str.strip()
    keep &= home.ne("") & away.ne("") & home.ne("None") & away.ne("None")
    shaped = pd.DataFrame(
        {
            "game_id": game_ids,
            "date": games["gameDateEst"].astype(str).str.slice(0, 10),
            "tip_utc": games["gameDateTimeUTC"].astype(str),
            "home": home,
            "away": away,
            "label": games.get("gameLabel", pd.Series("", index=games.index)).fillna("").astype(str),
        }
    )
    shaped = shaped.loc[keep].drop_duplicates("game_id")
    return shaped.sort_values(["date", "tip_utc", "game_id"], kind="mergesort").reset_index(drop=True)


def shape_players(index: pd.DataFrame) -> pd.DataFrame:
    if index.empty:
        return pd.DataFrame(columns=list(PLAYER_COLUMNS))
    first = index["PLAYER_FIRST_NAME"].fillna("").astype(str).str.strip()
    last = index["PLAYER_LAST_NAME"].fillna("").astype(str).str.strip()
    shaped = pd.DataFrame(
        {
            "player_id": index["PERSON_ID"].astype(int),
            "player_name": (first + " " + last).str.strip(),
            "team": index["TEAM_ABBREVIATION"].fillna("").astype(str),
            "nba_position": index["POSITION"].fillna("").astype(str),
        }
    )
    return shaped.drop_duplicates("player_id").reset_index(drop=True)


def shape_logs(logs: pd.DataFrame) -> pd.DataFrame:
    """One row per player per game played. ``opp`` and ``home`` come from MATCHUP."""
    if logs.empty:
        return pd.DataFrame(columns=list(LOG_COLUMNS))
    matchup = logs["MATCHUP"].astype(str)
    shaped = pd.DataFrame(
        {
            "player_id": logs["PLAYER_ID"].astype(int),
            "player_name": logs["PLAYER_NAME"].astype(str),
            "team": logs["TEAM_ABBREVIATION"].astype(str),
            "game_id": logs["GAME_ID"].astype(str).str.zfill(10),
            "date": logs["GAME_DATE"].astype(str).str.slice(0, 10),
            "opp": matchup.str.split().str[-1],
            "home": matchup.str.contains("vs.", regex=False).astype(int),
        }
    )
    for column, source in _LOG_STATS.items():
        shaped[column] = pd.to_numeric(logs[source], errors="coerce").fillna(0.0)
    shaped = shaped.loc[shaped["min"] > 0]
    return shaped.sort_values(["date", "game_id", "player_id"], kind="mergesort").reset_index(drop=True)


def fetch_schedule(season: str = SEASON, timeout: int = 60) -> pd.DataFrame:
    from nba_api.stats.endpoints import scheduleleaguev2

    return shape_schedule(scheduleleaguev2.ScheduleLeagueV2(season=season, timeout=timeout).get_data_frames()[0])


def fetch_players(season: str = SEASON, timeout: int = 60) -> pd.DataFrame:
    from nba_api.stats.endpoints import playerindex

    return shape_players(playerindex.PlayerIndex(season=season, timeout=timeout).get_data_frames()[0])


def fetch_logs(season: str, timeout: int = 90, player_id: int | None = None) -> pd.DataFrame:
    """Every player's games for a season, or one player's when ``player_id`` is given."""
    from nba_api.stats.endpoints import playergamelogs

    frame = playergamelogs.PlayerGameLogs(
        season_nullable=season,
        season_type_nullable="Regular Season",
        player_id_nullable=player_id,
        timeout=timeout,
    ).get_data_frames()[0]
    frame = shape_logs(frame)
    frame.insert(0, "season", season)
    return frame


HISTORY_DIR = FEED_DIR / "history"
HISTORY_SEASONS: tuple[str, ...] = ("2020-21", "2021-22", "2022-23", "2023-24", "2024-25")


def fetch_logs_by_team(season: str, timeout: int = 60) -> pd.DataFrame:
    """A whole past season, one team at a time. The league-wide pull fails for old seasons."""
    from nba_api.stats.endpoints import playergamelogs
    from nba_api.stats.static import teams

    frames = []
    for team in teams.get_teams():
        time.sleep(PAUSE_SECONDS)
        raw = playergamelogs.PlayerGameLogs(
            season_nullable=season,
            season_type_nullable="Regular Season",
            team_id_nullable=team["id"],
            timeout=timeout,
        ).get_data_frames()[0]
        frames.append(shape_logs(raw))
    frame = pd.concat([part for part in frames if len(part)], ignore_index=True)
    frame.insert(0, "season", season)
    return frame.sort_values(["date", "game_id", "player_id"], kind="mergesort").reset_index(drop=True)


def fetch_ages(season: str, timeout: int = 60) -> pd.DataFrame:
    from nba_api.stats.endpoints import leaguedashplayerstats

    raw = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season, season_type_all_star="Regular Season", per_mode_detailed="PerGame", timeout=timeout
    ).get_data_frames()[0]
    return pd.DataFrame({"season": season, "player_id": raw["PLAYER_ID"].astype(int), "age": raw["AGE"].astype(float)})


def pull_history(feed_dir: Path | None = None, seasons: tuple[str, ...] = HISTORY_SEASONS) -> dict:
    """Past seasons for training and testing the projections. Slow; each season is pulled once."""
    target = (feed_dir or FEED_DIR) / HISTORY_DIR.name
    target.mkdir(parents=True, exist_ok=True)
    report = {}
    ages = []
    for season in (*seasons, LAST_SEASON):
        time.sleep(PAUSE_SECONDS)
        ages.append(fetch_ages(season))
        path = target / f"gamelogs_{season}.csv"
        if season == LAST_SEASON or path.exists():
            continue
        frame = fetch_logs_by_team(season)
        frame.to_csv(path, index=False)
        report[season] = int(len(frame))
    pd.concat(ages, ignore_index=True).to_csv(target / "ages.csv", index=False)
    return report


def pull_comebacks(feed_dir: Path) -> int:
    """Fetch the older season for each listed comeback not already on disk. Returns rows added."""
    wanted_path = feed_dir / COMEBACKS_PATH.name
    players_path = feed_dir / PLAYERS_PATH.name
    if not wanted_path.exists() or not players_path.exists():
        return 0
    older_path = feed_dir / OLDER_LOGS_PATH.name
    older = pd.read_csv(older_path, dtype={"game_id": str}) if older_path.exists() else pd.DataFrame()
    have = set(zip(older["player_name"], older["season"])) if len(older) else set()
    ids = {str(row.player_name): int(row.player_id) for row in pd.read_csv(players_path).itertuples()}
    added = []
    for row in pd.read_csv(wanted_path).itertuples():
        name, season = str(row.player_name), str(row.season)
        if (name, season) in have or name not in ids:
            continue
        time.sleep(PAUSE_SECONDS)
        added.append(fetch_logs(season, player_id=ids[name]))
    if added:
        pd.concat([frame for frame in [older, *added] if len(frame)], ignore_index=True).to_csv(older_path, index=False)
    return sum(len(frame) for frame in added)


# A game is about 2h15 tip to buzzer; the stats feed posts its box score a little after.
GAME_LENGTH = timedelta(hours=2, minutes=30)
EASTERN = ZoneInfo("America/New_York")


def night_status(schedule: pd.DataFrame, logs: pd.DataFrame, now: datetime) -> dict:
    """Last night's games (US Eastern date before ``now``): are they over, and all in the logs?

    ``due`` is when the last one should be over. ``done`` means every game of the
    night is in the logs, so a morning pull has nothing left to fetch.
    """
    night = (now.astimezone(EASTERN).date() - timedelta(days=1)).isoformat()
    games = schedule.loc[schedule["date"] == night] if len(schedule) else schedule
    if games.empty:
        return {"night": night, "games": 0, "due": None, "done": True}
    tips = pd.to_datetime(games["tip_utc"], utc=True)
    due = tips.max().to_pydatetime() + GAME_LENGTH
    logged = set(logs["game_id"].astype(str)) if len(logs) else set()
    missing = sorted(set(games["game_id"].astype(str)) - logged)
    return {"night": night, "games": int(len(games)), "due": due, "done": not missing, "missing": len(missing)}


def refresh(feed_dir: Path | None = None, last_season: bool | None = None) -> dict:
    """Pull the feed and write it to disk. A failed pull keeps the old file.

    Last season's logs do not change, so they are pulled once unless asked.
    """
    target = feed_dir or FEED_DIR
    target.mkdir(parents=True, exist_ok=True)
    previous = target / f"gamelogs_{LAST_SEASON}.csv"
    want_last = (not previous.exists()) if last_season is None else last_season
    jobs = [
        ("schedule", target / SCHEDULE_PATH.name, fetch_schedule),
        ("players", target / PLAYERS_PATH.name, fetch_players),
        (f"logs {SEASON}", target / f"gamelogs_{SEASON}.csv", lambda: fetch_logs(SEASON)),
        ("injuries", target / INJURIES_PATH.name, injuries.fetch_injuries),
    ]
    if want_last:
        jobs.append((f"logs {LAST_SEASON}", previous, lambda: fetch_logs(LAST_SEASON)))
    report: dict = {"fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": {}, "errors": {}}
    for index, (label, path, fetch) in enumerate(jobs):
        if index:
            time.sleep(PAUSE_SECONDS)
        try:
            frame = fetch()
        except Exception as exc:  # the feed is a public endpoint; any failure keeps the old file
            report["errors"][label] = str(exc)[:200]
            continue
        # An empty schedule or roster is a bad pull. Empty logs are normal before opening night.
        if frame.empty and not label.startswith("logs"):
            report["errors"][label] = "empty response"
            continue
        frame.to_csv(path, index=False)
        report["rows"][label] = int(len(frame))
    try:
        pulled = pull_comebacks(target)
        if pulled:
            report["rows"]["comebacks"] = pulled
    except Exception as exc:
        report["errors"]["comebacks"] = str(exc)[:200]
    (target / META_PATH.name).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
