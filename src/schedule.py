"""NBA schedule for the season pad: fantasy weeks, who plays when, back-to-backs.

A fantasy day is the US Eastern date of the game, the same day Yahoo files it
under. Tip times stay in UTC and the page shows them in the browser's zone.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from nba_feed import FEED_DIR, SCHEDULE_COLUMNS

WEEKS_PATH = FEED_DIR / "fantasy_weeks.csv"
SLOTS_PER_DAY = 5

# Basketball-Reference codes in projections.csv that differ from the NBA feed.
TEAM_ALIASES: dict[str, str] = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}


def as_day(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def nba_team(code: object) -> str:
    text = "" if code is None else str(code).strip().upper()
    if text in ("", "NAN", "NONE"):
        return ""
    return TEAM_ALIASES.get(text, text)


def load_schedule(path: Path) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=list(SCHEDULE_COLUMNS))
    frame = pd.read_csv(path, dtype={"game_id": str})
    frame["label"] = frame["label"].fillna("")
    return frame


def fantasy_weeks(schedule: pd.DataFrame, overrides: pd.DataFrame | None = None) -> list[dict]:
    """Matchup weeks as ``{"week", "start", "end"}`` with inclusive days.

    Default: week 1 runs from opening night to the first Sunday, then Monday
    to Sunday. Yahoo joins some weeks (All-Star), so a ``week,start,end`` file
    copied from Yahoo replaces the default outright.
    """
    if overrides is not None and not overrides.empty:
        rows = [
            {"week": int(row.week), "start": as_day(row.start), "end": as_day(row.end)}
            for row in overrides.itertuples()
        ]
        return sorted(rows, key=lambda row: row["start"])
    if schedule.empty:
        return []
    first = as_day(schedule["date"].min())
    last = as_day(schedule["date"].max())
    weeks: list[dict] = []
    start = first
    while start <= last:
        end = start + timedelta(days=6 - start.weekday())
        weeks.append({"week": len(weeks) + 1, "start": start, "end": end})
        start = end + timedelta(days=1)
    return weeks


def load_weeks(schedule: pd.DataFrame, path: Path | None = None) -> list[dict]:
    target = path or WEEKS_PATH
    overrides = pd.read_csv(target) if Path(target).exists() else None
    return fantasy_weeks(schedule, overrides)


def week_for(day: date, weeks: list[dict]) -> dict | None:
    """The week holding ``day``. Before opening night it is week 1; after the end, the last."""
    if not weeks:
        return None
    for week in weeks:
        if week["start"] <= day <= week["end"]:
            return week
    if day < weeks[0]["start"]:
        return weeks[0]
    later = [week for week in weeks if week["start"] > day]
    return later[0] if later else weeks[-1]


def week_days(week: dict) -> list[date]:
    span = (week["end"] - week["start"]).days
    return [week["start"] + timedelta(days=offset) for offset in range(span + 1)]


def team_games(schedule: pd.DataFrame, team: str, start: date, end: date) -> list[dict]:
    """A team's games from ``start`` to ``end`` inclusive, in order.

    ``b2b`` marks the second night of a back-to-back, where rest is likeliest.
    """
    code = nba_team(team)
    if not code or schedule.empty:
        return []
    mine = schedule.loc[(schedule["home"] == code) | (schedule["away"] == code)]
    played = {as_day(value) for value in mine["date"]}
    window = mine.loc[(mine["date"] >= start.isoformat()) & (mine["date"] <= end.isoformat())]
    games = []
    for row in window.itertuples():
        day = as_day(row.date)
        at_home = row.home == code
        games.append(
            {
                "game_id": row.game_id,
                "date": day.isoformat(),
                "opp": row.away if at_home else row.home,
                "home": bool(at_home),
                "tip_utc": row.tip_utc,
                "b2b": (day - timedelta(days=1)) in played,
            }
        )
    return games


def league_games(schedule: pd.DataFrame, day: date) -> int:
    if schedule.empty:
        return 0
    return int((schedule["date"] == day.isoformat()).sum())


def week_grid(schedule: pd.DataFrame, roster: list[dict], week: dict, today: date) -> dict:
    """Who on the roster plays on each day of the week.

    ``roster`` rows carry ``player_name`` and ``team``. ``left`` counts games
    from ``today`` on. A day with more than five players playing is ``over``:
    someone with a game has to sit. Fewer than five is ``open``.
    """
    days = week_days(week)
    rows = []
    playing = {day: 0 for day in days}
    for seat in roster:
        by_day = {game["date"]: game for game in team_games(schedule, seat.get("team"), days[0], days[-1])}
        cells = [by_day.get(day.isoformat()) for day in days]
        for day, cell in zip(days, cells):
            if cell:
                playing[day] += 1
        rows.append(
            {
                "player_name": seat["player_name"],
                "team": nba_team(seat.get("team")),
                "games": sum(1 for cell in cells if cell),
                "left": sum(1 for day, cell in zip(days, cells) if cell and day >= today),
                "cells": cells,
            }
        )
    return {
        "week": week["week"],
        "start": days[0].isoformat(),
        "end": days[-1].isoformat(),
        "days": [
            {
                "date": day.isoformat(),
                "dow": day.strftime("%a"),
                "league_games": league_games(schedule, day),
                "mine": playing[day],
                "over": playing[day] > SLOTS_PER_DAY,
                "open": playing[day] < SLOTS_PER_DAY,
                "past": day < today,
            }
            for day in days
        ],
        "rows": rows,
        "starts_left": sum(min(playing[day], SLOTS_PER_DAY) for day in days if day >= today),
    }
