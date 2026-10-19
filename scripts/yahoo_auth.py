"""One-time Yahoo sign-in for the season pad (read-only access).

    .venv/bin/python scripts/yahoo_auth.py            # prints the Yahoo sign-in link
    .venv/bin/python scripts/yahoo_auth.py '<code>'   # after approving: the code, or the whole
                                                      # https://localhost:8080/?code=... address

The browser lands on a localhost page that does not load; that is expected,
the code is in its address bar. The token is saved to data/yahoo_token.json
(git-ignored, owner-only) and refreshes itself from then on.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yahoo_api  # noqa: E402


def main() -> int:
    try:
        if len(sys.argv) < 2:
            link = yahoo_api.authorize_url()
            print("Open this link, sign in, press Agree, then copy the address the browser lands on:\n")
            print(link)
            return 0
        yahoo_api.exchange_code(sys.argv[1])
        games = yahoo_api.get("users;use_login=1/games;game_keys=nba/teams")
    except yahoo_api.YahooNotConnected as exc:
        print(exc)
        return 1
    teams = []
    users = games["fantasy_content"]["users"]["0"]["user"][1]["games"]
    for index in range(int(users.get("count", 0))):
        game = users[str(index)]["game"]
        for entry in (game[1].get("teams") or {}).values() if len(game) > 1 else []:
            if isinstance(entry, dict) and "team" in entry:
                fields = {key: value for part in entry["team"][0] if isinstance(part, dict) for key, value in part.items()}
                teams.append(f"{fields.get('name')} ({fields.get('team_key')})")
    print("Connected to Yahoo. Your NBA teams:", ", ".join(teams) or "none found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
