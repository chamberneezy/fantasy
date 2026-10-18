"""Refresh the season pad's free NBA + ESPN feed into data/season/.

Same pull as the page's "Refresh data" button. A running server picks the
new files up on its next request (season_data caches on file mtimes).

    .venv/bin/python scripts/refresh_season.py            # daily pull
    .venv/bin/python scripts/refresh_season.py --history  # past seasons, once (~10 min)
    .venv/bin/python scripts/refresh_season.py --refit    # rewrite outlook.csv
    .venv/bin/python scripts/refresh_season.py --morning  # only once last night's games are over and not yet in
    .venv/bin/python scripts/refresh_season.py --publish  # then republish the GitHub Pages copy

The morning timer runs ``--morning`` every 15 minutes from 06:00 to 09:45 Zurich
time: it pulls once the night's last game should be over (tip + 2h30) and stops
once every game of that night is in the logs.

Exit code 1 when every job failed, so a timer shows the run as failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

import nba_feed  # noqa: E402
import outlook  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--history", action="store_true", help="pull past seasons for the outlook model")
    parser.add_argument("--refit", action="store_true", help="refit the outlook model and rewrite outlook.csv")
    parser.add_argument("--morning", action="store_true", help="pull only when last night is over and not yet logged")
    parser.add_argument("--publish", action="store_true", help="after a pull, republish the GitHub Pages copy")
    args = parser.parse_args()

    if args.morning:
        logs_path = nba_feed.logs_path(nba_feed.SEASON)
        schedule = pd.read_csv(nba_feed.SCHEDULE_PATH, dtype={"game_id": str}) if nba_feed.SCHEDULE_PATH.exists() else pd.DataFrame()
        logs = pd.read_csv(logs_path, dtype={"game_id": str}) if logs_path.exists() else pd.DataFrame()
        night = nba_feed.night_status(schedule, logs, datetime.now(timezone.utc))
        if night["done"]:
            print(f"night of {night['night']}: {night['games']} games, all in. Nothing to pull.")
            return 0
        if datetime.now(timezone.utc) < night["due"]:
            print(f"night of {night['night']}: last game not over until {night['due'].astimezone().strftime('%H:%M')}.")
            return 0

    report = nba_feed.refresh()
    print(json.dumps(report, indent=2))
    failed = bool(report["errors"]) and not report["rows"]
    if args.publish and not failed:
        sys.path.insert(0, str(ROOT / "scripts"))
        from publish_season import publish

        print(publish())

    if args.history:
        print("history:", nba_feed.pull_history())
    if args.refit:
        last_logs = pd.read_csv(nba_feed.logs_path(nba_feed.LAST_SEASON))
        written = outlook.build(
            nba_feed.HISTORY_DIR, last_logs, nba_feed.LAST_SEASON, nba_feed.SEASON, nba_feed.OUTLOOK_PATH
        )
        print("outlook players:", written)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
