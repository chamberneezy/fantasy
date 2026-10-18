"""Refresh the season pad's free NBA + ESPN feed into data/season/.

Same pull as the page's "Refresh data" button. A running server picks the
new files up on its next request (season_data caches on file mtimes).

    .venv/bin/python scripts/refresh_season.py            # daily pull
    .venv/bin/python scripts/refresh_season.py --history  # past seasons, once (~10 min)
    .venv/bin/python scripts/refresh_season.py --refit    # rewrite outlook.csv

Exit code 1 when every job failed, so a timer shows the run as failed.
"""

from __future__ import annotations

import argparse
import json
import sys
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
    args = parser.parse_args()

    report = nba_feed.refresh()
    print(json.dumps(report, indent=2))
    failed = bool(report["errors"]) and not report["rows"]

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
