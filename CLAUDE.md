# Pilsner draft tool — briefing for Claude

Mario’s private unpublished helper for **3. Pilsner Fantasy Liga** (Yahoo league 51867): 16-team salary-cap, **$200** default draft dollars, **10 drafted seats** (PG/SG/SF/PF/C + 5 BN). IL+ is in-season only. Live draft is Sunday 4 Oct 2026. This is an information pad. It does **not** open Yahoo, does **not** auto-bid, and must not grow a cheat path.

Yahoo settings confirm the 12 H2H cats, 16 teams, 10 seats, 4 divisions, 8-team playoffs in weeks 18–20, daily lineup lock, 4 adds/week, no Yahoo waivers, commissioner trade review. **3rd league has no dynasty this draft** (Keep/Locked stay for 1st/2nd). Yahoo currently lists Draft Type as Offline; Pilsner pravila still describe a live salary-cap room — Mario types what happens either way. “Not a cash league” means Yahoo prize league is off, not that the $200 cap is gone.

If you are double-checking work, treat `context/system_rules.md` and `.cursorrules` as the contract. This file is the map of what exists and what is trustworthy.

## League math (do not “improve”)

12 H2H cats: `MIN, FG%, FT%, 3PM, PTS, REB, AST, STL, BLK, TO, PF, DD`.

- Counting z: `(stat - mean) / std` with **population** std (`ddof=0`). Std `0` → z `0`.
- TO and PF are inverted: `-1 * (stat - mean) / std`.
- FG% / FT% are **volume-weighted** first (`(pct - mean_pct) * attempts`), then that impact is standardized like a counting z.
- Punts drop categories from the **sum only**. Stored per-cat z stays intact.
- Predicted games are informational. They must not lower rank.
- Dual-position 1.12× exists in code and is unused on this Pilsner file.

Application math, ranking, and data loading live in `src/`. Not in tests, scripts, or notebooks.

## Three pages, three sessions

Flask on `127.0.0.1:5340`. Use Xcode Python (Homebrew `python3` often lacks pandas):

```
/Applications/Xcode.app/Contents/Developer/usr/bin/python3 src/draft_server.py
/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/ -q
```

| URL | What it is | Session file |
|---|---|---|
| `/draft` | Practice **mock** (Yahoo clocks, bots) | `data/draft_session.json` |
| `/helper` | Live-night **input pad** | `data/helper_session.json` |
| `/lab` | Headless batch rooms + scenarios | `data/lab_report.json` |

These sessions must not overwrite each other. Starting helper must not wipe a mock. Do not delete `draft_session.json` on server restart.

## Prices (helper / coach)

- **Yahoo list** (`src/market.py` `YAHOO_LISTED`) is the official 2025-26 salary-cap board dollar.
- **Stay** = median of Yahoo list + Hashtag Y!/ESPN AAV + FantraxHQ, **never below Yahoo list**.
- **Stretch** = high of those samples.
- Unlisted names stay on surplus (`src/auction.py`, `SURPLUS_POWER = 0.74`). Last-name market match is **single-token only** (`jokic` → Jokic; `Justin Edwards` must not inherit Anthony Edwards).
- After a **$40+** buy, the next elite is a pass (Stay ≈ 0.50× listed, leftover-$1 still binds).
- Leftover rule: always leave **$1 per empty seat**.

### Room learning (`src/room.py`)

Logged Sold/Me hammers update **this room’s Stay** by tier (`star` ≥ $40, `mid` ≥ $20, `end` else):

- Heat = median(`hammer / fair Stay`) in that bucket, clamped 0.85–1.22.
- **One** sale in a bucket is noise (factor stays 1.0).
- **Two** sales in a bucket move that tier.
- **Three** stars over fair Stretch also lift mid a bit.
- Yahoo list and fair Stay stay on the card. The big Stay number is the room-adjusted call.
- League cash = `teams × $200 − spent`. If leftover per empty seat `< $8` after 8+ sales, warn the $1 endgame.
- Second-star and leftover-$1 beat heat if they conflict.

Helper UX: tap a name (or type 3 letters), then **Sold** / **Me**. Dollar defaults to Stay. Do not autofocus the search after those buttons. Budget is Pilsner draft dollars ($160–$240), the cap, not a payment. **3. Pilsner has no dynasty this year** — use Sold/Me. Keep/Locked remain for 1st/2nd dynasty nights only. Superstars cannot be dynasty.

## What to trust vs not

**Trust for draft night**

- 12-cat z-score contract and tests in `tests/test_math_engine.py`.
- Yahoo list + Stay/Stretch from published sources in `market.py`.
- Helper loop: name → Stay/Stretch/Pass → Sold/Me → leftover seats.
- Room heat after **two** hammers in a tier. Not after one $87 Jokic.

**Do not treat as a forecast**

- `/lab` bots (7 tight / 7 room / 1 heat, invented interest). Modal squads (e.g. Cade in 95% of rooms) are leftover gravity, not scouting.
- Surplus-only ranks that used to price Kawhi like a $50 star. If Yahoo lists $27, the list wins.
- Health-trap “steals” on rate (Embiid $17, Ja $5) without looking at predicted games.

A $25 list **can** project more 12-cat z than a $50 name (e.g. Kawhi $27 vs Cade $57 on current projections). That is surplus vs dollar, not last year’s Pilsner results. We do **not** have a full 2024-25 Pilsner sale tape.

## Layout

```
src/math_engine.py      z-scores
src/market.py           Yahoo list + AAV / Fantrax
src/auction.py          surplus $ then market overwrite
src/coach.py            Stay / Stretch / Pass, feed parse
src/room.py             live heat from logged sales
src/sidecar.py          helper session
src/yahoo_auction.py    mock clocks + bots
src/lab.py              headless 2k/10k rooms
src/draft_room.py       pool, slots, paths
src/draft_server.py     Flask
tests/                  pytest; no math implementations
data/                   projections, sessions; do not commit secrets
```

## Constraints that keep coming back

- No Yahoo API. No official NBA logo.
- Do not edit the original plan file.
- Do not build the in-season fantasy page yet.
- Do not commit unless Mario asks.
- UI changes: verify `/helper`, `/draft`, `/lab` as touched. Helper and mock must stay consistent.

## Double-check list

1. `pytest tests/ -q` with Xcode Python.
2. Helper and mock session files still separate after a restart.
3. Jokic list $60, Stay ≥ $70, Kawhi list $27.
4. `quote("Justin Edwards")` is `None`.
5. One logged star sale does not raise Cade’s Stay; two hot star sales do.
6. Lab language: modal slot ≠ one room that happened.
7. No exploit, scrape, or Yahoo-live wiring.

Owner: Mario. Prefer working in `src/` and tests, not a new parallel tool.
