# Season helper — where it stands and what is next

Last worked on **19 Oct 2026**, committed and pushed on `cursor/3rd-league-draft-dollars`. Suite: **116 tests pass** (`.venv/bin/python -m pytest tests/ -q`). Restart the server on 5340 after pulling changes; a stale process keeps serving old code.

**18 Oct 2026:** restored on the Arch Linux machine from the `chamberneezy/backup` snapshot (16 Oct) into `~/Projects/fantasy`, still uncommitted on `cursor/3rd-league-draft-dollars`. Runs in `.venv` (Python 3.14); `scipy` added to `requirements.txt`. 96 tests pass.

Mario’s brief: a daily start/sit and add/drop helper for Yahoo 51867. Free data only (no paid API, no Yahoo premium, no Yahoo scraping). Use the machine fully — he said the first version was too conservative with analysis and compute.

## What `/season` does now

| Piece | Module | Notes |
|---|---|---|
| Free NBA feed → `data/season/` | `src/nba_feed.py` | schedule, rosters, game logs via `nba_api`; injuries via ESPN public JSON. “Refresh data” button or `nba_feed.refresh()`. A failed pull keeps the old file. |
| Fantasy weeks, week grid, back-to-backs | `src/schedule.py` | Fantasy day = US Eastern date. Tip times UTC, shown in browser time. |
| Per-game line | `src/daily.py` | per-minute rates × minutes; this season’s games recency-weighted (half-life 12 games, minutes 5), anchored on the season line (10 / 4 pseudo-games). |
| Season anchor | `src/outlook.py` → `data/season/outlook.csv` | 3 seasons + age, fitted on history, blended 50/50 with last season. Only the season pad uses it. Draft board and z contract untouched. |
| Opponent / home factors, rest habit | `src/context.py` | clamped ±15%. Back-to-back = chance of sitting per player, not fewer minutes. |
| Injury → chance to play | `src/injuries.py` | manual “Mark out / in” on the page beats the feed (`status` in the season session). |
| Simulated week | `src/matchup.py` | 20,000 runs. Each player-game drawn from his own past games rescaled to tonight’s line. Chance per category, expected cats, win/tie/lose. |
| Legal five + week plan | `src/lineup.py` | strict PG/SG/SF/PF/C. Opponent assumed to start best five by value. My five picked by swing in categories still in play; a player who costs more than he adds sits. |
| Add plans | `src/season.py` `stream_plans` | only names nobody owns, 20+ NBA games on file; drops limited to my 3 lowest season values, never Hezonja; top 5 replayed through the simulation. |
| My Team (top of `/season`) | `src/team_sheet.py` | Morning brief (score so far as the pad seated your five, last night's lines, injuries, games per day this week), then a Yahoo-style sheet for the chosen day: seat changes with reasons ("Start X: @MIL · +0.38 cats · helps AST" / "Out of SG: Y — no game"), who sits with a game and why, empty seats, and a table with Tonight / Last game / 7 days / Season / Proj. columns. "Done in Yahoo" (`POST /season/api/lineup?date=`) seats that day's five in the pad, idle names filling empty starts because Yahoo has only 5 bench spots. Reuses the week plan; no second model. |
| Matchup detail panel | `src/scouting.py` | "Matchup" on each day-card player, `/season/api/scout`. Opponent rank of 30 per category vs his position group (per minute allowed vs league), pace and defensive-rating ranks (possessions estimated without OREB, so read ranks), his games vs that team since 2020-21 against his own average, last 3 meetings, home/away split, usage and TS%. Last season until every team has 10 games. Information only: it does not move the simulation. |
| Data glue | `src/season_data.py` | reads feed + pasted rosters + matchups; cached on file mtimes. |

## Files Mario supplies (pasted by hand, never scraped)

- `data/season/league_rosters.csv` — all 16 teams, Yahoo slot + eligibility, **all re-pasted 25 Oct 2026** (Danijel's from the 24 Oct matchup page). Kept current from Yahoo's **Transactions** screen (adds, drops, trades with dates). With every roster on file, an unrostered player is a free agent. Stale after any add/drop/trade. Re-paste the week’s opponent at least. Slot `IL` stays rostered but is left out of that team's simulated starts (the league has no IL; Old Stars carries two anyway).
- `data/season/free_agents.csv` — Yahoo's free-agent list (name, team, Yahoo positions, Q/O tag, pre-season rank, % rostered), merged from Yahoo screenshots (Players → All Available, sorted by **Current** rank, 2–3 pages), last **25 Oct 2026**, 67 names. Names missing from a fresh screenshot that ranked inside it are removed as taken; names below the pages stay until seen again. When present, add plans only offer these names and skip Yahoo "O"; Yahoo positions replace the NBA-feed guess. Re-paste before each add decision.
- `data/season/matchups.csv` — `week,opponent`. Weeks **1–5** filled: Danijel's Dandy Team, Old Stars, BC Versus, Mother Tucker, Harlem Bricks.
- `data/season/comebacks.csv` — players projected off an older season. Only **Tyrese Haliburton, 2024-25** (Mario’s call: expects him near that year). Kyrie Irving, Fred VanVleet, Damian Lillard missed 2025-26 too and still count as zero.
- `data/season/fantasy_weeks.csv` — optional `week,start,end` override. Not present. Week 1 = **20–25 Oct** (confirmed). Default after that is Monday–Sunday, but Yahoo’s week 21 ends 28 Mar, so two calendar weeks get joined somewhere before week 19 — **dates still needed** (matters from about February).

## Refresh on GitHub (since 25 Oct 2026)

`.github/workflows/season.yml` lives on **main** (GitHub runs schedules only from the default branch) and checks out `cursor/3rd-league-draft-dollars`. It restores the raw feed from branch `season-feed`, runs `refresh_season.py` (ESPN), saves the feed back, then `publish_season.py` (season-data → Pages, incl. `app.json` for the iPhone app). Runs: 06/07/08 UTC with `--morning` (skips until last night is over, then once all games are in), 17 and 22 UTC for injury news, and by hand (`gh workflow run season.yml`). stats.nba.com times out and cdn.nba.com answers 403 from runners (probe 25 Oct), so the cloud uses ESPN; ESPN ids map to NBA ids in `data/season/espn_ids.csv`.

`data/season_session.json` (roster, lineup, adds used) is **committed** now, so the run and cloud sessions see Mario's ten. After a move: update the session (`SeasonSession.add/drop`, `save_season`) and `league_rosters.csv`, commit, push, `gh workflow run season.yml`.

## From the Claude iPhone app (cloud session on this repo)

Mario opens the Claude app → Code → this repo, branch `cursor/3rd-league-draft-dollars`, and sends Yahoo screenshots. A cloud session has the code and the committed files, not the raw feed: first `git fetch origin season-feed && git archive FETCH_HEAD | tar -x -C data/season` (schedule, players, this season's logs, injuries), then `pip install -r requirements.txt`. Then, per screenshot:

| Screenshot | Write | Notes |
|---|---|---|
| Matchup page (12 cats, both teams) | `data/season/yahoo_scores.csv`: two rows, `week,through,side` (`mine` / `theirs`) + `min,fgm,fga,ftm,fta,fg3m,pts,reb,ast,stl,blk,to,pf,dd` | `through` = the last day whose games are in the totals (a morning screenshot: yesterday). Keep earlier rows. The week plan then starts from these real totals. |
| "Added X, dropped Y" / My Team | `SeasonSession.drop/add` + `save_season` (session json), Mario's lines in `league_rosters.csv` (CRLF line endings), `free_agents.csv` (X off, Y on) | Adds count against 4 per week. |
| Transactions (League → Transactions) | append to `data/season/transactions.csv` (`when_local` in Zurich time as Yahoo shows it, `team`, `add`, `drop`; full names), then apply each add/drop/trade to that team's rows in `league_rosters.csv`, oldest first; Mario's own also via `SeasonSession.add/drop(on=date)` | Must reach back to the last row in the log (last: 25 Oct 12:19, Rapske Manige); say so if it does not. Slot `IL` = rostered but not simulated. |
| Free agents (sorted by Current rank) | merge into `free_agents.csv`; names missing that ranked inside the pages → remove as taken | |
| Season schedule | `matchups.csv` (`week,opponent`) | |

Then commit and push: the push starts `season.yml` (paths above), which pulls ESPN, rebuilds and publishes `app.json` and Pages within a few minutes. Reply in the agreed format: facts first, per-cat leans as words, coin flips named, long-run cost first on any move. Opponent analysis stays in chat, not in commits.

## Refresh on the laptop (old; its systemd timers were switched off 25 Oct 2026, GitHub publishes now)

Two systemd user timers, Zurich time. **Morning** (`nba-fantasy-morning`): every 15 min 06:00–09:45 runs `refresh_season.py --morning --publish`, which pulls only once last night's final game should be over (latest tip + 2h30; west-coast tips are 04:00–05:00 Zurich, so usually 06:30–07:30) and does nothing once every game of the night is in the logs (`nba_feed.night_status`). **Evening** (`nba-fantasy-refresh`): 18:00 and 23:30, injury news before tip-off. Both republish Pages after a pull. `Persistent=true` catches up after the laptop sleeps. Units live in `scripts/systemd/`, installed to `~/.config/systemd/user/`. A running server picks up new files on its next request.

```
.venv/bin/python scripts/refresh_season.py            # same pull as the page button
.venv/bin/python scripts/refresh_season.py --history  # past seasons 2020-21 … 2024-25, once (~10 min)
.venv/bin/python scripts/refresh_season.py --refit    # refit the outlook, rewrite outlook.csv
systemctl --user list-timers nba-fantasy-refresh.timer
journalctl --user -u nba-fantasy-refresh -n 30
```

**GitHub Pages copy:** https://chamberneezy.github.io/fantasy/season.html — read-only, this week only. After each refresh the same service runs `scripts/publish_season.py`: `export_season.py` writes every day's state + matchup panels to `data/season_export/` (git-ignored), the result is force-pushed as the single commit on branch `season-data` (skipped when unchanged), and `gh workflow run pages.yml --ref cursor/3rd-league-draft-dollars` rebuilds Pages. The workflow copies `src/static/season.js` → `docs/js/season.js` and `helper.css` → `docs/css/season.css`, and checks `season-data` out into `docs/data/season/`. `docs/season.html` sets `window.SEASON_STATIC`, which hides add/drop/lineup/refresh. The repo is public, so the copy (your roster, the pasted league rosters) is public. Laptop off = no updates.

Committed: hand-pasted files, `history/`, `gamelogs_2025-26.csv`, `gamelogs_older.csv`, `outlook.csv`. Git-ignored because every refresh rewrites them: `feed.json`, `injuries.csv`, `players.csv`, `schedule.csv`, `gamelogs_2026-27.csv`. A fresh clone needs one refresh.

## Measured, so do not re-argue without new data

- Injury bumps, 2025-26 replay (one rotation player out, earlier games only, top named teammate): shrink 15 games predicts +4.5 min on high calls vs +3.7 real (shrink 5 predicted +6.6). Gained minutes: high 69% (132 calls), medium 64%, low 57%. Per-player single-game minutes error stays ~4.9 whatever the method.
- ESPN vs stats.nba.com, 20–24 Oct 2026: 812/812 player-games, schedule 1,200/1,200, 515 players same team; 17 small stat differences; ESPN minutes are whole.

- Daily line vs naive, 2025-26 walk-forward (140 players, first 20 games as anchor): total error 17.32 vs 17.80 season-to-date vs 18.88 fixed line. Most of the gain is minutes.
- Opponent + home factors improve error by only ~0.1%. Shown, clamped, not trusted to swing a call.
- Second night of a back-to-back does **not** cut minutes of those who play (ratio 1.025). It is a sit chance only.
- Outlook model on held-out 2025-26: ~6–8% lower error than last season’s line. Model alone under-rates top scorers by ~0.5 pt; last season alone over-rates them by ~1.2 pt; 50/50 is best for stars.
- NBA feed position (G/F/C) matches Yahoo eligibility only roughly (Jaccard 0.69). Free-agent positions are **guessed** and flagged; e.g. Diabaté shows SF/PF but is a centre.

## Week 1 — Tue 20 – Sun 25 Oct vs Danijel's Dandy Team

- **Moves (3 of 4 adds):** Dillon Brooks → Anfernee Simons (19 Oct); Jrue Holiday → Jalen Smith (21 Oct); Anfernee Simons → **Tristan da Silva** (25 Oct; ORL SF/PF, starter minutes while Banchero is out ~4–6 weeks).
- **Score:** 3–9 after Wed, 7–5 after Thu, 6–5–1 after Fri (Yahoo), about 7–5 after Sat (box-score count). Final pending.
- **Lessons:** the "63% win" call after Tuesday was badly overconfident (opponent's early games, Jokić idle until Thu). Jrue → Smith and Brooks → Simons were weak long-run calls. Past days in the pad still assume both teams' best five, so its headline odds drift from the real Yahoo score mid-week.

## How to answer (agreed 23 Oct)

1. Facts first: score, games left, who plays — checkable against Mario's screenshot.
2. No headline win %. Per category: likely / lean / coin flip / unlikely, with the reason.
3. Coin flips are named as coin flips; Mario decides those.
4. Every add/drop shows the long-run value given up first; push only clear edges. Goal stays winning each week.

## Roster shape (sim of weeks 2–5, 24 Oct)

MIN and 3PM lean to the opponent in all four weeks; TO, STL, AST, FT% lean Mario's way. Week-2 adds should target minutes, threes and games, not centres (Jokić, Collins, Queta, Smith are already C-eligible). Week 3 has no games Tue 3 Nov and 10-for-5 seats Mon/Wed.

**What Mario sends (screenshots / messages), and when:**

| When | What |
|---|---|
| After any move | One line: "added X, dropped Y" → apply with `SeasonSession.add/drop`, `save_season`, then `scripts/publish_season.py`. |
| Every morning | Yahoo **matchup page** screenshot (12 cats + both rosters). Read the real score, say which cats are locked / lost / in play, tonight's lineup, whether an add is worth it. |
| Before an add | Players → All Available, sorted by **Current** rank, 2–3 pages → merge into `data/season/free_agents.csv`. |
| Sunday / Monday | Next opponent's roster → `league_rosters.csv`. |
| If he deviates | "started X instead of Y"; otherwise assume he set the pad's lineup. |

Mario does **not** want the Yahoo API (needs app approval since Jul 2026) or anyone logging into his Yahoo account. Stats, injuries and schedules come from the NBA/ESPN feeds automatically.

## Results on file (7 Oct 2026, before any real game)

- Week 1 vs Danijel: **37% win / 23% tie / 40% lose**, ~5.8 of 12 cats. Swing cats: FG% (51%), TO (41%), AST (39%). Haliburton at full 2024-25 strength for 3 games.
- League round-robin over weeks 1–8 (scratch analysis, not on the page): Mario **5th of 16**, 53% vs the field. Danijel 1st. Strong: FG%, FT%, AST, PF. Weak: MIN, REB, BLK (14th–15th).
- Model vs news: Jalen Williams (healthy, model still on his injured year) and John Collins (expected ~30 min starter in DET) are the likely upside; Kawhi has a load-management plan in TOR; Hezonja ~15–20 min bench, **no line** (no NBA games on file) so he counts as zero.

## Next, in the order I would do it

1. ~~Matchup detail panel~~ **built 18 Oct** (`src/scouting.py`). Not in it: likely defender (`leagueseasonmatchups` is a per-player network call; add to the refresh if wanted).
2. ~~Matchup schedule~~ weeks 1–5 in `matchups.csv` (24 Oct). Still needed: weeks 6+ and Yahoo’s joined-week dates.
2b. **Week-ahead report + weekly scorecard** (agreed 23 Oct, not built): Sunday report of starts per day, per-cat leans, add options with season cost; Monday score vs the leans in `data/season/results.csv`; weight this season's games more in `daily.py` once the scorecard shows it helps.
3. **Refit the outlook** (`scripts/refresh_season.py --refit`) once ~3 weeks of 2026-27 are in. The CLI exists; the timer does not refit.
3b. **Injury bumps:** minutes replay done (see Measured). Next: replay the per-minute production changes; until then they move very slowly (`RATE_SHRINK_GAMES`).
4. **Backtest log (planned phase 8):** store each day’s projection and compare with the box score weekly, so trust is measured in-season.
5. **League table on the page** (currently scratch only) and comeback lines for Kyrie / VanVleet / Lillard if Mario wants them.
6. **Not built:** teammate boost when a starter sits; blowout risk (needs betting lines → API key); real banked lineups (past days assume best-by-value five); multi-add sequencing across the week; Yahoo eligibility for free agents.
7. Optional heavier modelling: gradient boosting needs `scikit-learn` / `lightgbm`, neither installed in `.venv`. Ask before `pip install`.

## Tests

`tests/test_schedule.py`, `test_daily.py`, `test_matchup.py`, `test_outlook.py`, `test_season.py`. All use synthetic frames or `tmp_path` feeds; none hit the network. `SeasonSession(build_pool())` without `data=` reads the real `data/season/`, so the older season tests depend on what is on disk.
