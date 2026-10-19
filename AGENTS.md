# Agent notes

Full briefing: [CLAUDE.md](CLAUDE.md). League contract: [context/system_rules.md](context/system_rules.md). Live Yahoo 51867: [context/league.md](context/league.md). Math: [.cursorrules](.cursorrules).

- App code in `src/`. No math/ranking/data-loading in tests or scripts.
- Brand is **NBA Fantasy** (not Pilsner). Yahoo league name is still 3. Pilsner Fantasy Liga. 16 teams, custom draft dollars (mock default $200), 10 seats, **no IL**, 12-cat z-scores (`ddof=0`). TO/PF inverted. FG%/FT% volume-weighted then standardized.
- `/` home, `/season` in-season (Mario’s 10, 4 adds/week, no IL), `/helper` live draft, `/draft` mock, `/lab` batch — **separate sessions**. Logo click (`data-home-reset`) clears helper, mock, lab, and season and goes home.
- Playoffs **weeks 19–21**, 8 teams, 4 divisions. Daily – Today. Lock benched players: No. Instant FA, 4 adds/week.
- Mario’s 10: Keyonte, Kawhi, Jalen Williams, John Collins, Jokic, **Hezonja (keep)**, Jrue, Queta, Anfernee Simons, Tre Jones (Brooks dropped for Simons 19 Oct). Do not recommend dropping Hezonja.
- Stay = median of Yahoo list + published AAV, never below list. Stretch = high. For listed ≥ $50 (Jokic / Luka / Wemby / SGA / Cade…), Stay is also ≥ 1.80× listed and Stretch ≥ 2.40× listed — Jokic list $60 Stay $108 Stretch $144; **$100 is still Stay**. 120% of listed is Yahoo’s computer, not the human cap.
- On a Yahoo-backed board, unlisted names are **$1**, not surplus. Surplus is only for pools with no Yahoo quotes.
- Helper card: Yahoo list · fair Stay–Stretch · this room (heat) · you leftover. Leftover-$1 still caps what you can pay; heat does not spend your last seats.
- Room heat (`src/room.py`): a quiet first star is noise; a nuclear first $50+ hammer (≈1.25× Stay, a steal, or over Stretch) or two sales in a tier moves this room’s Stay (clamp 0.85–1.22). Dynasty Keep/Locked at Yahoo list do not teach heat.
- `/lab` “most common name at each seat” is a unique greedy collage, not one roster. Never two of the same player.
- In-season helper (schedule, daily lines, matchup simulation, start/sit, add plans): state, measurements and next steps are in [context/season_helper.md](context/season_helper.md). Free NBA (`nba_api`) and ESPN injury feeds only; league rosters and matchups are pasted by Mario into `data/season/`.
- No Yahoo API, no auto-bid. Do not commit unless asked.
- Tests: `.venv/bin/python -m pytest tests/ -q`
- Server: same interpreter, `src/draft_server.py`, `127.0.0.1:5340`.
