"""Write what was read from Yahoo into the pad's files. Nothing here talks to Yahoo.

    .venv/bin/python scripts/apply_yahoo.py --rosters FILE --free-agents FILE
    .venv/bin/python scripts/apply_yahoo.py --score 2 2026-11-01 "MINE ROW" "THEIR ROW"

--rosters: one team per line, "Team : PG Name TEAM - PG,SG; BN ...". --free-agents:
"Name TEAM POS,POS|pre-season rank|current rank|12%". Score rows as on the matchup page.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

import yahoo_snapshot  # noqa: E402

FEED = ROOT / "data" / "season"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rosters", type=Path)
    parser.add_argument("--free-agents", type=Path)
    parser.add_argument("--score", nargs=4, metavar=("WEEK", "THROUGH", "MINE", "THEIRS"))
    args = parser.parse_args()
    known = [str(name) for name in pd.read_csv(FEED / "players.csv")["player_name"]]
    if args.rosters:
        path = FEED / "league_rosters.csv"
        managers = pd.read_csv(path).drop_duplicates("fantasy_team").set_index("fantasy_team")["manager"].to_dict()
        teams = dict(line.split(" : ", 1) for line in args.rosters.read_text(encoding="utf-8").splitlines() if line.strip())
        rows = yahoo_snapshot.roster_rows(teams, managers, known)
        rows.to_csv(path, index=False, lineterminator="\r\n")
        print(f"{len(rows)} roster rows, {rows['fantasy_team'].nunique()} teams")
    if args.free_agents:
        lines = [line for line in args.free_agents.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = yahoo_snapshot.free_agent_rows(lines, known)
        rows.to_csv(FEED / "free_agents.csv", index=False)
        print(f"{len(rows)} free agents")
    if args.score:
        week, through, mine, theirs = args.score
        yahoo_snapshot.save_score(FEED / "yahoo_scores.csv", [yahoo_snapshot.score_row(int(week), through, "mine", mine), yahoo_snapshot.score_row(int(week), through, "theirs", theirs)])
        print(f"Yahoo score saved through {through}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
