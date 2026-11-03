"""Write this week of the season pad as JSON for the read-only GitHub Pages copy.

One file per day (the same state the laptop page reads, plus every matchup
panel for that day's games) and an index. Reads the saved season session, so
the copy shows the roster and lineup as the laptop pad has them.

    .venv/bin/python scripts/export_season.py [out_dir]
    .venv/bin/python scripts/export_season.py --team-dir DIR --app OUT.json   # another team: only its app feed
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import app_feed  # noqa: E402
import schedule as slate  # noqa: E402
import season  # noqa: E402
from draft_room import build_pool  # noqa: E402

DEFAULT_OUT = ROOT / "data" / "season_export"


def _plain(value):
    """numpy numbers and arrays to JSON."""
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"cannot write {type(value).__name__}")


def export_app(team_dir: Path, out_file: Path) -> dict:
    """One app feed for the team whose session.json, matchups.csv and yahoo_scores.csv are in ``team_dir``."""
    session = season.load_season(build_pool([]), team_dir=team_dir)
    if not session.data.weeks:
        raise SystemExit("No schedule on disk. Run scripts/refresh_season.py first.")
    feed = app_feed.build(session, season.league_today())
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(feed, default=_plain, ensure_ascii=False), encoding="utf-8")
    return {"team": feed["team"], "week": feed["week"], "bytes": out_file.stat().st_size}


def export(out_dir: Path = DEFAULT_OUT) -> dict:
    session = season.load_season(build_pool([]))
    data = session.data
    if not data.weeks:
        raise SystemExit("No schedule on disk. Run scripts/refresh_season.py first.")
    today = season.league_today()
    week = slate.week_for(today, data.weeks)
    days = [day.isoformat() for day in slate.week_days(week)]
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    for iso in days:
        state = session.state(datetime.fromisoformat(iso).date())
        scouts = {}
        for row in (state.get("calendar") or {}).get("day", {}).get("playing", []):
            key = f"{row['player_name']}|{row['opp']}|{1 if row['home'] else 0}"
            scouts[key] = {"player_name": row["player_name"], **data.scout_detail(row["player_name"], row["opp"], bool(row["home"]))}
        state["scouts"] = scouts
        (out_dir / f"{iso}.json").write_text(json.dumps(state, default=_plain, ensure_ascii=False), encoding="utf-8")
    index = {
        "days": days,
        "default": min(max(today.isoformat(), days[0]), days[-1]),
        "week": week["week"],
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (out_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    # The iPhone app reads this one file.
    feed = app_feed.build(session, today)
    (out_dir / "app.json").write_text(json.dumps(feed, default=_plain, ensure_ascii=False), encoding="utf-8")
    return index


if __name__ == "__main__":
    if "--team-dir" in sys.argv:
        team_dir = Path(sys.argv[sys.argv.index("--team-dir") + 1])
        out_file = Path(sys.argv[sys.argv.index("--app") + 1]) if "--app" in sys.argv else team_dir / "app.json"
        print(json.dumps(export_app(team_dir, out_file)))
        sys.exit(0)
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    print(json.dumps(export(target)))
