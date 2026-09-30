"""Write the ranked pool as JSON for the GitHub Pages helper and mock."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from draft_room import build_pool

KEEP = (
    "player_name",
    "positions",
    "team",
    "total_value",
    "auction_value",
    "yahoo_listed",
    "stay_market",
    "stretch_market",
    "typical_low",
    "typical_high",
    "predicted_games",
    "superstar",
)


def main() -> None:
    players = []
    for player in build_pool():
        row = {key: player.get(key) for key in KEEP}
        listed = player.get("yahoo_listed")
        row["yahoo_listed"] = int(listed) if listed not in (None, "") else None
        row["auction_value"] = int(player.get("auction_value") or 1)
        players.append(row)
    out = ROOT / "docs" / "data" / "pool.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"categories": ["MIN", "FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO", "PF", "DD"], "players": players}, ensure_ascii=False))
    print(f"wrote {len(players)} players to {out}")


if __name__ == "__main__":
    main()
