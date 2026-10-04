# Agent notes

Full briefing: [CLAUDE.md](CLAUDE.md). League contract: [context/system_rules.md](context/system_rules.md). Math: [.cursorrules](.cursorrules).

- App code in `src/`. No math/ranking/data-loading in tests or scripts.
- Brand is **NBA Fantasy** (not Pilsner). 16 teams, $160–$240 draft dollars (default $200, that is the cap not a payment), 10 seats, 12-cat z-scores (`ddof=0`). TO/PF inverted. FG%/FT% volume-weighted then standardized.
- `/` home, `/draft` mock, `/helper` live pad, `/lab` batch rooms — **separate sessions**. Logo click (`data-home-reset`) clears helper, mock, and lab and goes home.
- Stay = median of Yahoo list + published AAV, never below list. Stretch = high. For listed ≥ $50 (Jokic / Luka / Wemby / SGA / Cade…), Stay is also ≥ 1.80× listed and Stretch ≥ 2.40× listed — Jokic list $60 Stay $108 Stretch $144; **$100 is still Stay**. 120% of listed is Yahoo’s computer, not the human cap.
- On a Yahoo-backed board, unlisted names are **$1**, not surplus. Surplus is only for pools with no Yahoo quotes.
- Helper card: Yahoo list · fair Stay–Stretch · this room (heat) · you leftover. Leftover-$1 still caps what you can pay; heat does not spend your last seats.
- Room heat (`src/room.py`): a quiet first star is noise; a nuclear first $50+ hammer (≈1.25× Stay, a steal, or over Stretch) or two sales in a tier moves this room’s Stay (clamp 0.85–1.22). Dynasty Keep/Locked at Yahoo list do not teach heat.
- `/lab` “most common name at each seat” is a unique greedy collage, not one roster. Never two of the same player.
- No Yahoo API, no auto-bid. Do not commit unless asked.
- Tests: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/ -q`
- Server: same interpreter, `src/draft_server.py`, `127.0.0.1:5340`.
