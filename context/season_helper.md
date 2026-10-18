# Season helper — where it stands and what is next

Last worked on **7 Oct 2026**. Everything below is **uncommitted** on `cursor/3rd-league-draft-dollars`. Suite: **96 tests pass** (`.venv/bin/python -m pytest tests/ -q`). Restart the server on 5340 after pulling changes; a stale process keeps serving old code.

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
| Data glue | `src/season_data.py` | reads feed + pasted rosters + matchups; cached on file mtimes. |

## Files Mario supplies (pasted by hand, never scraped)

- `data/season/league_rosters.csv` — all 16 teams, Yahoo slot + eligibility, **snapshot 5 Oct 2026**. Stale after any add/drop/trade. Re-paste the week’s opponent at least.
- `data/season/matchups.csv` — `week,opponent`. **Only week 1 is filled** (Danijel's Dandy Team).
- `data/season/comebacks.csv` — players projected off an older season. Only **Tyrese Haliburton, 2024-25** (Mario’s call: expects him near that year). Kyrie Irving, Fred VanVleet, Damian Lillard missed 2025-26 too and still count as zero.
- `data/season/fantasy_weeks.csv` — optional `week,start,end` override. Not present. Week 1 = **20–25 Oct** (confirmed). Default after that is Monday–Sunday, but Yahoo’s week 21 ends 28 Mar, so two calendar weeks get joined somewhere before week 19 — **dates still needed** (matters from about February).

## Rebuild commands

```
PY=.venv/bin/python
# daily refresh (same as the page button)
$PY -c "import sys; sys.path.insert(0,'src'); import nba_feed; print(nba_feed.refresh())"
# past seasons 2020-21 … 2024-25, team by team (~10 min, once; league-wide pull 500s for old seasons)
$PY -c "import sys; sys.path.insert(0,'src'); import nba_feed; print(nba_feed.pull_history())"
# refit the outlook and rewrite outlook.csv (not wired to the Refresh button yet)
$PY -c "import sys; sys.path.insert(0,'src'); import pandas as pd, nba_feed, outlook; print(outlook.build(nba_feed.HISTORY_DIR, pd.read_csv(nba_feed.logs_path(nba_feed.LAST_SEASON)), nba_feed.LAST_SEASON, nba_feed.SEASON, nba_feed.OUTLOOK_PATH))"
```

`data/season/` is ~30 MB of CSV and is **not** in `.gitignore`. Decide before committing whether it goes in.

## Measured, so do not re-argue without new data

- Daily line vs naive, 2025-26 walk-forward (140 players, first 20 games as anchor): total error 17.32 vs 17.80 season-to-date vs 18.88 fixed line. Most of the gain is minutes.
- Opponent + home factors improve error by only ~0.1%. Shown, clamped, not trusted to swing a call.
- Second night of a back-to-back does **not** cut minutes of those who play (ratio 1.025). It is a sit chance only.
- Outlook model on held-out 2025-26: ~6–8% lower error than last season’s line. Model alone under-rates top scorers by ~0.5 pt; last season alone over-rates them by ~1.2 pt; 50/50 is best for stars.
- NBA feed position (G/F/C) matches Yahoo eligibility only roughly (Jaccard 0.69). Free-agent positions are **guessed** and flagged; e.g. Diabaté shows SF/PF but is a centre.

## Results on file (7 Oct 2026, before any real game)

- Week 1 vs Danijel: **37% win / 23% tie / 40% lose**, ~5.8 of 12 cats. Swing cats: FG% (51%), TO (41%), AST (39%). Haliburton at full 2024-25 strength for 3 games.
- League round-robin over weeks 1–8 (scratch analysis, not on the page): Mario **5th of 16**, 53% vs the field. Danijel 1st. Strong: FG%, FT%, AST, PF. Weak: MIN, REB, BLK (14th–15th).
- Model vs news: Jalen Williams (healthy, model still on his injured year) and John Collins (expected ~30 min starter in DET) are the likely upside; Kawhi has a load-management plan in TOR; Hezonja ~15–20 min bench, **no line** (no NBA games on file) so he counts as zero.

## Next, in the order I would do it

1. **Matchup detail panel** on each player in the day card (Mario asked; confirmed possible on the free feed, awaiting his go): opponent rank vs position per category, pace / defensive rating, his history vs that team (six seasons on disk), home/away split, likely defender (`leagueseasonmatchups`), usage / TS%. Label early-season numbers as last year’s.
2. **Rest of the matchup schedule** into `matchups.csv`, and Yahoo’s joined-week dates.
3. **Wire `outlook.build` and `pull_history`** into Refresh (or a CLI in `scripts/`), and refit once ~3 weeks of 2026-27 are in.
4. **Backtest log (planned phase 8):** store each day’s projection and compare with the box score weekly, so trust is measured in-season.
5. **League table on the page** (currently scratch only) and comeback lines for Kyrie / VanVleet / Lillard if Mario wants them.
6. **Not built:** teammate boost when a starter sits; blowout risk (needs betting lines → API key); real banked lineups (past days assume best-by-value five); multi-add sequencing across the week; Yahoo eligibility for free agents.
7. Optional heavier modelling: gradient boosting needs `scikit-learn` / `lightgbm`, neither installed in `.venv`. Ask before `pip install`.

## Tests

`tests/test_schedule.py`, `test_daily.py`, `test_matchup.py`, `test_outlook.py`, `test_season.py`. All use synthetic frames or `tmp_path` feeds; none hit the network. `SeasonSession(build_pool())` without `data=` reads the real `data/season/`, so the older season tests depend on what is on disk.
