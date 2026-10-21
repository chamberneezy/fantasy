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

- `data/season/league_rosters.csv` — all 16 teams, Yahoo slot + eligibility, **snapshot 5 Oct 2026**. Stale after any add/drop/trade. Re-paste the week’s opponent at least.
- `data/season/free_agents.csv` — Yahoo's free-agent list (name, team, Yahoo positions, Q/O tag, pre-season rank, % rostered), top 40 by pre-season rank, **19 Oct 2026**. When present, add plans only offer these names and skip Yahoo "O"; Yahoo positions replace the NBA-feed guess. Re-paste before each add decision.
- `data/season/matchups.csv` — `week,opponent`. **Only week 1 is filled** (Danijel's Dandy Team).
- `data/season/comebacks.csv` — players projected off an older season. Only **Tyrese Haliburton, 2024-25** (Mario’s call: expects him near that year). Kyrie Irving, Fred VanVleet, Damian Lillard missed 2025-26 too and still count as zero.
- `data/season/fantasy_weeks.csv` — optional `week,start,end` override. Not present. Week 1 = **20–25 Oct** (confirmed). Default after that is Monday–Sunday, but Yahoo’s week 21 ends 28 Mar, so two calendar weeks get joined somewhere before week 19 — **dates still needed** (matters from about February).

## Refresh (automated)

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

- Daily line vs naive, 2025-26 walk-forward (140 players, first 20 games as anchor): total error 17.32 vs 17.80 season-to-date vs 18.88 fixed line. Most of the gain is minutes.
- Opponent + home factors improve error by only ~0.1%. Shown, clamped, not trusted to swing a call.
- Second night of a back-to-back does **not** cut minutes of those who play (ratio 1.025). It is a sit chance only.
- Outlook model on held-out 2025-26: ~6–8% lower error than last season’s line. Model alone under-rates top scorers by ~0.5 pt; last season alone over-rates them by ~1.2 pt; 50/50 is best for stars.
- NBA feed position (G/F/C) matches Yahoo eligibility only roughly (Jaccard 0.69). Free-agent positions are **guessed** and flagged; e.g. Diabaté shows SF/PF but is a centre.

## Week 1 (live) — Tue 20 – Sun 25 Oct vs Danijel's Dandy Team

Mario's focus is **week 1 only** until it ends; ignore week 2+ for now.

- **Moves:** Dillon Brooks → **Anfernee Simons** (19 Oct); Jrue Holiday → **Jalen Smith** (21 Oct). **2 of 4 adds left**; keep them for an injured starter (no IL).
- **Goal:** win each week. Rank moves by this week's win chance; season value given up is a con, not a veto.
- **After Tue 20 Oct:** pad count 7–4–1 (assumes Hart + Duren started for Danijel). With Smith: win 63% / tie 21% / lose 16%, ~6.9 cats; REB 30% → 60%. Smith starts all 3 CHI games (Wed C, Fri PF, Sat PF). Wed lineup: Keyonte PG, Tre Jones SG, Kawhi PF, Smith C.
- **Odds after the move:** ~6.5 of 12 cats, **win 53% / tie 23% / lose 24%** (was 45 / 23 / 32). Likely wins MIN, FT%, PTS, STL; toss-ups 3PM, FG%, AST, TO; likely losses REB, PF, BLK, DD (Danijel has AD, Duren, Sarr, Carter). Chase the toss-ups (assists, 3s, efficient guards), not blocks/DD.
- **Tue lineup:** Simons at PG (Keyonte idle), Queta at C (Jokić idle). First tip Tue 21:00 Zurich. Simons is Yahoo **Q** (hamstring): if ruled out, leave PG empty rather than spend an add.
- **Considered, not done:** Champagnie for Collins (+0.2 cats; Collins may outplay his model in DET). Keep Jrue (hand, DTD, back ~21 Oct). Ayton is the best FA (+6.4) but C-only behind Jokić/Queta, so not this week.
- **Week plan (19 Oct, done 21 Oct):** empty seats are SG Tue, PF+C Wed, SG+PF Thu, SF+PF Sat. Jrue's two games (Wed, Fri) never get a seat, so he adds nothing this week. **Jrue → Jalen Smith** (CHI, PF/C; Wed/Fri/Sat, on the pasted FA list) re-simulates to about +0.5 cats, win ≈53% → ≈65%. Decide Wed morning after Tuesday's games: do it if no starter got hurt (leaves 2 adds); costs Jrue rest-of-season. Dropping Simons or Tre Jones instead is worse.

**What Mario sends (screenshots / messages), and when:**

| When | What |
|---|---|
| After any move | One line: "added X, dropped Y" → apply with `SeasonSession.add/drop`, `save_season`, then `scripts/publish_season.py`. |
| Done 19 Oct | Danijel's roster: unchanged from the 5 Oct paste. |
| Every morning Wed–Mon | Yahoo **matchup page** screenshot (12 cats + both rosters). Read the real score, say which cats are locked / lost / in play, tonight's lineup, whether an add is worth it. |
| Before an add | Free-agent list, top 25–40 → `data/season/free_agents.csv` (Brooks re-added there as FA). |
| If he deviates | "started X instead of Y"; otherwise assume he set the pad's lineup. |

Mario does **not** want the Yahoo API (needs app approval since Jul 2026) or anyone logging into his Yahoo account. Stats, injuries and schedules come from the NBA/ESPN feeds automatically.

## Results on file (7 Oct 2026, before any real game)

- Week 1 vs Danijel: **37% win / 23% tie / 40% lose**, ~5.8 of 12 cats. Swing cats: FG% (51%), TO (41%), AST (39%). Haliburton at full 2024-25 strength for 3 games.
- League round-robin over weeks 1–8 (scratch analysis, not on the page): Mario **5th of 16**, 53% vs the field. Danijel 1st. Strong: FG%, FT%, AST, PF. Weak: MIN, REB, BLK (14th–15th).
- Model vs news: Jalen Williams (healthy, model still on his injured year) and John Collins (expected ~30 min starter in DET) are the likely upside; Kawhi has a load-management plan in TOR; Hezonja ~15–20 min bench, **no line** (no NBA games on file) so he counts as zero.

## Next, in the order I would do it

1. ~~Matchup detail panel~~ **built 18 Oct** (`src/scouting.py`). Not in it: likely defender (`leagueseasonmatchups` is a per-player network call; add to the refresh if wanted).
2. **Rest of the matchup schedule** into `matchups.csv`, and Yahoo’s joined-week dates.
3. **Refit the outlook** (`scripts/refresh_season.py --refit`) once ~3 weeks of 2026-27 are in. The CLI exists; the timer does not refit.
4. **Backtest log (planned phase 8):** store each day’s projection and compare with the box score weekly, so trust is measured in-season.
5. **League table on the page** (currently scratch only) and comeback lines for Kyrie / VanVleet / Lillard if Mario wants them.
6. **Not built:** teammate boost when a starter sits; blowout risk (needs betting lines → API key); real banked lineups (past days assume best-by-value five); multi-add sequencing across the week; Yahoo eligibility for free agents.
7. Optional heavier modelling: gradient boosting needs `scikit-learn` / `lightgbm`, neither installed in `.venv`. Ask before `pip install`.

## Tests

`tests/test_schedule.py`, `test_daily.py`, `test_matchup.py`, `test_outlook.py`, `test_season.py`. All use synthetic frames or `tmp_path` feeds; none hit the network. `SeasonSession(build_pool())` without `data=` reads the real `data/season/`, so the older season tests depend on what is on disk.
