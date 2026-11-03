"""The morning report: 12 categories for every player and every decision.

Run after the Yahoo files are current (context/daily_routine.md). The report and
forecast log stay in data/season/daily/, git-ignored: they name opponents.

    .venv/bin/python scripts/daily_plan.py                  # refresh ESPN, report for today
    .venv/bin/python scripts/daily_plan.py --date 2026-11-02 --no-refresh
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

import category_board  # noqa: E402
import espn_feed  # noqa: E402
import nba_feed  # noqa: E402
import schedule as slate  # noqa: E402
import season  # noqa: E402
import season_data  # noqa: E402
from draft_room import build_pool  # noqa: E402

DAILY_DIR = ROOT / "data" / "season" / "daily"
FORECASTS = DAILY_DIR / "forecasts.csv"


def finals(data, weeks: list[dict]) -> dict[int, dict[str, float]]:
    """Weeks whose Yahoo totals run through their last day."""
    results = {}
    for week in weeks:
        banked = data.yahoo_banked(week["week"])
        if banked and banked["through"] >= str(week["end"]):
            results[week["week"]] = category_board.category_results(banked["mine"], banked["theirs"])
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", help="report day, YYYY-MM-DD; default today in US Eastern")
    parser.add_argument("--no-refresh", action="store_true", help="use the ESPN files already on disk")
    args = parser.parse_args()
    if not args.no_refresh:
        feed = espn_feed.refresh()
        if feed.get("errors"):
            print(f"ESPN refresh problems, older files kept where it failed: {feed['errors']}", file=sys.stderr)
    today = date.fromisoformat(args.date) if args.date else datetime.now(ZoneInfo("America/New_York")).date()

    session = season.load_season(build_pool())
    data = session.data
    weeks = data.weeks
    week = slate.week_for(today, weeks)
    if week is None:
        print(f"No fantasy week on {today}.", file=sys.stderr)
        return 1
    rostered = {str(row["player_name"]): str(row["fantasy_team"]) for row in data.rosters.to_dict("records")}
    later = [other for other in weeks if other["week"] > week["week"]]
    report = category_board.week_report(session, week, today, rostered, later_weeks=later)

    mine = {espn_feed.name_key(name) for name, team in rostered.items() if team == session.team}
    on_file = {espn_feed.name_key(name) for name in report["roster"]} | {espn_feed.name_key(row["player"]["player_name"]) for row in session.il}
    differs = mine ^ on_file
    if differs:
        print(f"Session and Yahoo rosters differ: {sorted(differs)}", file=sys.stderr)

    last_games = [str(games.iloc[-1]["game_id"]) for games in (data.season_games(name) for name in report["roster"]) if len(games)]
    tonight = data.schedule.loc[data.schedule["date"].astype(str) == today.isoformat(), "game_id"].astype(str).tolist()
    notes = espn_feed.game_notes([*last_games, *tonight])
    flags = category_board.watch_flags(session, report["values"], report["roster"], notes, today)

    category_board.record_forecast(FORECASTS, report)
    grades = None
    if FORECASTS.exists():
        grades = category_board.grade_forecasts(pd.read_csv(FORECASTS), finals(data, weeks))
    text = category_board.render(report, flags, grades)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    (DAILY_DIR / f"{today.isoformat()}.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
