# Daily 12-category routine

Mario asks for it in chat each morning. Read Yahoo first, then run the report. Mario asked for Yahoo to be read in his own Chrome (31 Oct 2026). Read only: ask before changing a lineup or making a move.

## 1. Read Yahoo (Claude in Chrome)

League 51867, Mario's team id 15, on `basketball.fantasysports.yahoo.com/nba/51867/`. The tool cuts each output near 1,000 characters, so keep the text on `window` and read it in slices. It also blocks output containing `==`.

| Page | What to take |
|---|---|
| `startingrosters` | All 16 rosters, one line per team: `Team : PG Name TEAM - PG,SG; BN ...`. The team name in the table's preceding element belongs to the table before it; the last is Vikings. |
| `players?status=A&pos=P&cut_type=33&stat1=S_L30&sort=AR&sdir=1`, then `&count=25`, `&count=50` | Free agents: `Name TEAM POS,POS|pre-season|current|12%` |
| `matchup?week=N&mid1=15&mid2=OPP` | Both totals, games played and remaining. Row: `MIN|FGM/A|FG%|FTM/A|FT%|3PM|PTS|REB|AST|ST|BLK|TO|PF|DD` |
| `15/team?date=YYYY-MM-DD`, `OPP/team?date=...` | Lineups for today and the days left |
| `transactions` | Every move since the last read, especially the opponent's |

## 2. Write the files and run

```
.venv/bin/python scripts/apply_yahoo.py --rosters FILE --free-agents FILE
.venv/bin/python scripts/apply_yahoo.py --score WEEK THROUGH "MY ROW" "THEIR ROW"
.venv/bin/python scripts/daily_plan.py
```

`THROUGH` is the last day whose games are in Yahoo's totals. A final-day score also lets the report grade that week. The report and forecasts go to `data/season/daily/`, git-ignored because they name opponents.

If `apply_yahoo.py` stops on a row, fix the row rather than skipping it. If the report says session and Yahoo rosters differ, update `data/season_session.json` first.

## 3. Answer

- Yahoo's score and games left first. Say plainly when a number is an estimate.
- All 12 categories in words, with the two-add case. No headline win chance. Name coin flips.
- Today's five, then who sits with a game and which seats are empty.
- Any move: every category it helps and hurts, league ranks, later weeks. Long-run cost first. Hezonja stays.
- Value is the plain sum of 12 z-scores. Never let points stand in for the whole team.

## What is measured

- Chances are shrunk to 60% of their log-odds (`CONFIDENCE_SHRINK`), from a replay of last season on a simplified model. Replace it once this season's graded forecasts are enough to measure it.
- Moves of under about 0.5 categories are inside the model's error on one week.
- One game: MIN, PTS, AST and REB are partly predictable; STL, PF and BLK are mostly not, so those are won by volume of games and players who are steadily good at them.
