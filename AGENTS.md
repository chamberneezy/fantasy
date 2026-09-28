# Agent notes

Full briefing: [CLAUDE.md](CLAUDE.md). League contract: [context/system_rules.md](context/system_rules.md). Math: [.cursorrules](.cursorrules).

- App code in `src/`. No math/ranking/data-loading in tests or scripts.
- 16 teams, 3. Pilsner, $160–$240 draft dollars (default $200, that is the cap not a payment), 10 seats, 12-cat z-scores (`ddof=0`). TO/PF inverted. FG%/FT% volume-weighted then standardized.
- `/draft` mock, `/helper` live pad, `/lab` batch rooms — **separate sessions**.
- Stay = median of Yahoo list + published AAV, never below list. Stretch = high.
- Room heat (`src/room.py`): one sale is noise; two in a tier move this room’s Stay. Dynasty Keep/Locked at Yahoo list do not teach heat.
- No Yahoo API, no auto-bid. Do not commit unless asked.
- Tests: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/ -q`
- Server: same interpreter, `src/draft_server.py`, `127.0.0.1:5340`.
