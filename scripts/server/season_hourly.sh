#!/usr/bin/env bash
# Hourly on the home server "gw": pull ESPN, keep the raw feed on the season-feed branch,
# publish the web page and the iPhone app's app.json, then run any private follow-up.
#
# Works in its own clone (default ~/services/nba-fantasy/fantasy), never in the
# Syncthing-shared ~/Projects, so it cannot clash with work on the laptop.
# The code is whatever is pushed on the working branch; local edits there are discarded.
set -euo pipefail

# The whole body is read before it runs: the git reset below rewrites this file.
{

BASE=${NBA_FANTASY_HOME:-$HOME/services/nba-fantasy}
ENGINE=$BASE/fantasy
BRANCH=cursor/3rd-league-draft-dollars
FEED_BRANCH=season-feed
FEED_FILES="schedule.csv players.csv gamelogs_2026-27.csv shots_2026-27.csv boxextra_2026-27.csv injuries.csv feed.json"

exec 9>"$BASE/run.lock"
flock -n 9 || { echo "a run is still going; skipping"; exit 0; }
echo "== $(date -Is) season feed"

cd "$ENGINE"
git fetch -q origin "$BRANCH" "$FEED_BRANCH"
git reset -q --hard "origin/$BRANCH"
.venv/bin/pip install -q -r requirements.txt cryptography

# First run on this machine: start from the raw feed GitHub already has.
if [ ! -f data/season/schedule.csv ]; then
  git archive "origin/$FEED_BRANCH" | tar -x -C data/season
fi

.venv/bin/python scripts/refresh_season.py

# Keep the raw feed on GitHub too (the fallback workflow and other teams' feeds read it).
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
for name in $FEED_FILES; do
  if [ -f "data/season/$name" ]; then cp "data/season/$name" "$work/"; fi
done
(
  cd "$work"
  git init -q -b "$FEED_BRANCH"
  git add -A
  git -c user.name="NBA Fantasy feed" -c user.email="81742479+chamberneezy@users.noreply.github.com" \
    commit -q -m "Season feed $(date -u +%Y-%m-%dT%H:%MZ) (gw)"
  git push -q --force "$(git -C "$ENGINE" remote get-url origin)" "HEAD:refs/heads/$FEED_BRANCH"
)

.venv/bin/python scripts/publish_season.py --force

# Private follow-ups (other teams' feeds) live outside this repo.
if [ -x "$BASE/after-publish.sh" ]; then
  "$BASE/after-publish.sh"
fi
echo "== $(date -Is) done"
exit
}
