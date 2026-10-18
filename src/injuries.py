"""Injury report for the season pad, from ESPN's free public feed. Never Yahoo."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

INJURY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
INJURY_COLUMNS = ("player_name", "status", "return_date", "reported", "part", "note")

# Chance of playing. "Day-To-Day" carries a date for the next look, not a promise.
OUT_BEFORE_RETURN = 0.0
OUT_FIRST_DAYS_BACK = 0.6
DAY_TO_DAY_BEFORE = 0.25
DAY_TO_DAY_FIRST_DAYS = 0.6
DAY_TO_DAY_LATER = 0.9
EASE_BACK_DAYS = 3
# An "Out" with no return date is believed for this long after the report.
OUT_UNDATED_DAYS = 14


def shape_injuries(payload: dict) -> pd.DataFrame:
    rows = []
    for team in payload.get("injuries") or []:
        for item in team.get("injuries") or []:
            details = item.get("details") or {}
            rows.append(
                {
                    "player_name": str((item.get("athlete") or {}).get("displayName") or "").strip(),
                    "status": str(item.get("status") or "").strip(),
                    "return_date": str(details.get("returnDate") or "")[:10],
                    "reported": str(item.get("date") or "")[:10],
                    "part": str(details.get("type") or ""),
                    "note": str(item.get("shortComment") or "").strip(),
                }
            )
    frame = pd.DataFrame(rows, columns=list(INJURY_COLUMNS))
    return frame.loc[frame["player_name"].ne("")].drop_duplicates("player_name").reset_index(drop=True)


def fetch_injuries(timeout: int = 30) -> pd.DataFrame:
    import requests

    response = requests.get(INJURY_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    response.raise_for_status()
    return shape_injuries(response.json())


def _day(text: object) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def play_chance(status: object, return_date: object, reported: object, day: date) -> float:
    """Chance a listed player plays on ``day``. Unlisted players are 1."""
    label = str(status or "").strip().lower()
    back = _day(return_date)
    if label == "out":
        if back is None:
            seen = _day(reported)
            return OUT_BEFORE_RETURN if seen is None or day <= seen + timedelta(days=OUT_UNDATED_DAYS) else 1.0
        if day < back:
            return OUT_BEFORE_RETURN
        return OUT_FIRST_DAYS_BACK if day < back + timedelta(days=EASE_BACK_DAYS) else 1.0
    if label == "day-to-day":
        if back is None:
            return DAY_TO_DAY_FIRST_DAYS
        if day < back:
            return DAY_TO_DAY_BEFORE
        return DAY_TO_DAY_FIRST_DAYS if day < back + timedelta(days=EASE_BACK_DAYS) else DAY_TO_DAY_LATER
    return 1.0
