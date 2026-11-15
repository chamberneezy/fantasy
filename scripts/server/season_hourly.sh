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
.venv/bin/pip install -q -r requirements.txt cryptography playwright

# First run on this machine: start from the raw feed GitHub already has.
if [ ! -f data/season/schedule.csv ]; then
  git archive "origin/$FEED_BRANCH" | tar -x -C data/season
fi

.venv/bin/python scripts/refresh_season.py

# Yahoo, read only, once Mario has signed in (scripts/server/yahoo_login.sh). Changed files go to GitHub.
PROFILE=$BASE/yahoo-profile
if [ -d "$PROFILE" ]; then
  set +e
  .venv/bin/python scripts/yahoo_read.py --profile "$PROFILE"
  code=$?
  set -e
  if [ "$code" -eq 0 ]; then
    git add data/season_session.json data/season/league_rosters.csv data/season/free_agents.csv data/season/yahoo_scores.csv
    if ! git diff --cached --quiet; then
      git -c user.name="NBA Fantasy on gw" -c user.email="81742479+chamberneezy@users.noreply.github.com" \
        commit -q -m "Yahoo read on gw $(date +%Y-%m-%dT%H:%M)"
      if git pull -q --rebase origin "$BRANCH" && git push -q origin "HEAD:$BRANCH"; then
        echo "Yahoo files pushed"
      else
        git rebase --abort 2>/dev/null || true
        echo "Yahoo files not pushed (the branch moved); used locally, next hour tries again"
      fi
    fi
  elif [ "$code" -eq 3 ]; then
    echo "Yahoo sign-in expired: run scripts/server/yahoo_login.sh on gw"
  else
    echo "Yahoo read failed (exit $code); ESPN feed still publishes"
  fi
fi

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
