#!/usr/bin/env bash
# Once (and whenever Yahoo signs you out): opens a Chromium window on gw's screen with the
# profile the hourly reader uses. Sign in to Yahoo yourself, open the league, close the window.
set -euo pipefail
BASE=${NBA_FANTASY_HOME:-$HOME/services/nba-fantasy}
cd "$BASE/fantasy"
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-$(basename "$(ls "$XDG_RUNTIME_DIR"/wayland-* 2>/dev/null | grep -v lock | head -1)")}
mkdir -p "$BASE/yahoo-profile"
chmod 700 "$BASE/yahoo-profile"
.venv/bin/python scripts/yahoo_read.py --profile "$BASE/yahoo-profile" --login
