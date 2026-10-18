# NBA Fantasy draft tool — briefing for Claude

Mario’s private unpublished helper for Yahoo league **51867** (Yahoo name: 3. Pilsner Fantasy Liga). Pad brand is **NBA Fantasy**, not Pilsner. 16 teams, salary-cap auction, **10 seats** (PG/SG/SF/PF/C + 5 BN). **No IL / IL+.** Live draft was Sunday 4 Oct 2026. This is an information pad. It does **not** open Yahoo, does **not** auto-bid, and must not grow a cheat path.

Yahoo Settings (5 Oct 2026): 12 H2H cats, 16 teams, 4 divisions, 8-team playoffs in **weeks 19–21**, daily lineup (**Daily – Today**), **Lock benched players: No**, **4 adds/week**, no season add cap, **no waivers** (FA instant), commissioner trade review, custom per-team draft dollars. **No dynasty.** “Not a cash league” means Yahoo prize league is off, not that the cap is gone. Full snapshot: `context/league.md`.

If you are double-checking work, treat `context/system_rules.md` and `.cursorrules` as the contract. This file is the map of what exists and what is trustworthy.

**Continuing the in-season helper?** Read `context/season_helper.md` first: what is built, what was measured, the files Mario pastes, and the next steps in order.

## League math (do not “improve”)

12 H2H cats: `MIN, FG%, FT%, 3PM, PTS, REB, AST, STL, BLK, TO, PF, DD`.

- Counting z: `(stat - mean) / std` with **population** std (`ddof=0`). Std `0` → z `0`.
- TO and PF are inverted: `-1 * (stat - mean) / std`.
- FG% / FT% are **volume-weighted** first (`(pct - mean_pct) * attempts`), then that impact is standardized like a counting z.
- Punts drop categories from the **sum only**. Stored per-cat z stays intact.
- Predicted games are informational. They must not lower rank.
- Dual-position 1.12× exists in code and is unused on this file.

Application math, ranking, and data loading live in `src/`. Not in tests, scripts, or notebooks.

## Pages and sessions

Flask on `127.0.0.1:5340`. Use the project venv (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`):

```
.venv/bin/python src/draft_server.py
.venv/bin/python -m pytest tests/ -q
```

Wordmark is **NBA Fantasy**. Do not revive Pilsner naming.

| URL | What it is | Session file |
|---|---|---|
| `/` | Home. Logo click from any page lands here after a full reset. | — |
| `/draft` | Practice **mock** (Yahoo clocks, bots) | `data/draft_session.json` |
| `/helper` | Live-night **input pad** | `data/helper_session.json` |
| `/lab` | Headless batch rooms + scenarios | `data/lab_report.json` |
| `/season` | In-season pad (your 10, 4 adds/week, **no IL**) | `data/season_session.json` |

These sessions must not overwrite each other. Starting helper must not wipe a mock. Do not delete `draft_session.json` on server restart. Logo (`data-home-reset`) clears helper, mock, lab, **and** season, then goes `/`.

## Prices (helper / coach)

- **Yahoo list** (`src/market.py` `YAHOO_LISTED`) is the official 2025-26 salary-cap board dollar.
- **Stay** = median of Yahoo list + Hashtag Y!/ESPN AAV + FantraxHQ, **never below Yahoo list**. For listed ≥ $50, also ≥ **1.80× listed**. Jokic list $60 → Stay **$108**, Stretch **$144**. **$100 is still Stay**. Yahoo 120% is computer only.
- **Stretch** = high of those samples, and ≥ **2.40× listed** on those apex names (Luka / Wemby / SGA / Cade too). Names under $50 (Kawhi $27, Trae on AAV) stay on list/AAV — they are not 1.80×.
- On a **Yahoo-backed board**, unlisted names are **$1** endgame flyers (`apply_market_prices`). Surplus (`src/auction.py`, `SURPLUS_POWER = 0.74`) is only a starting guess when the pool has **no** Yahoo quotes (tests). A four-game two-way must not sit as a $30 mid.
- Last-name market match is **single-token only** (`jokic` → Jokic; `Justin Edwards` must not inherit Anthony Edwards).
- After a **$40+** buy, the next elite is a pass (Stay ≈ 0.50× listed, leftover-$1 still binds).
- Leftover rule: always leave **$1 per empty seat**. Heat can mark remaining stars; leftover still caps **your** bid. After Stay $108 on Jokic, leftover-max for 9 seats is $84 — that is *you*, not the room’s Stay on Cade.

### Room learning (`src/room.py`)

Logged Sold/Me hammers update **this room’s Stay** by tier (`star` ≥ $40, `mid` ≥ $20, `end` else):

- Heat = median(`hammer / fair Stay`) in that bucket, clamped 0.85–1.22.
- **One quiet** sale in a bucket is noise (factor stays 1.0). Example: $87 Jokic.
- **One nuclear** first $50+ hammer marks remaining stars immediately: price ≥ max(1.25× Stay, Stay+$15), or ≤ 0.80× Stay, or ≥ 1.12× Stretch. Example: $160 Jokic → Cade fair $103, this room $126 (1.22× cap).
- **Two** sales in a bucket move that tier.
- **Three** stars over fair Stretch also lift mid a bit.
- Card line: Yahoo list · **fair** Stay–Stretch · **this room** (if heat ≠ 1) · **you** leftover if leftover < room Stay. The big Stay number is the room-adjusted call, then leftover.
- League cash = `teams × $200 − spent`. If leftover per empty seat `< $8` after 8+ sales, warn the $1 endgame.
- Second-star and leftover-$1 beat heat if they conflict.

Helper UX: tap a name (or type 3 letters), then **Sold** / **Me**. Dollar defaults to Stay. Do not autofocus the search after those buttons. Budget is draft dollars ($160–$240), the cap, not a payment. **No dynasty this year** — use Sold/Me. Keep/Locked remain for a dynasty night only. Superstars cannot be dynasty.

## What to trust vs not

**Trust for this league**

- 12-cat z-score contract and tests in `tests/test_math_engine.py`.
- Yahoo Settings snapshot in `context/league.md` (51867, no IL, playoffs weeks 19–21, 4 adds/week, instant FA).
- Yahoo list + Stay/Stretch from published sources in `market.py` (apex 1.80× / 2.40× on listed ≥ $50).
- Helper loop: name → Stay/Stretch/Pass → Sold/Me → leftover seats.
- Room heat after **two** hammers in a tier, **or** one nuclear first $50+ hammer. Not after one $87 Jokic.
- Unlisted = $1 on this board. Lab “most common name at each seat” is unique greedy — never two Sabonis.
- In-season pad (`src/season.py`): Mario’s 10, Hezonja protected, week-1 1 of 4 adds used, no IL.
- Season pad start/sit and matchup odds as **estimates**: strict-seat legal five, 20,000-run week vs the pasted opponent. Free NBA + ESPN feeds only.

**Do not treat as a forecast**

- `/lab` bots (7 tight / 7 room / 1 heat, invented interest). Modal squads (e.g. Cade in 95% of rooms) are leftover gravity, not scouting. The collage is not one room that happened.
- Surplus-only ranks that used to price Kawhi like a $50 star or Alondes like a $34 mid. If Yahoo lists $27, the list wins. If Yahoo does not list him, he is $1.
- Health-trap “steals” on rate (Embiid $17, Ja $5) without looking at predicted games.
- Season pad inputs that go stale or are guessed: pasted league rosters (5 Oct snapshot), free-agent positions (from NBA G/F/C), opponent lineups (assumed best five), players with no NBA games on file (Hezonja = zero), early-season opponent factors (last year’s rosters).

A $25 list **can** project more 12-cat z than a $50 name (e.g. Kawhi $27 vs Cade $57 on current projections). That is surplus vs dollar, not last year’s sale results. We do **not** have a full prior-year sale tape.

## Layout

```
src/math_engine.py      z-scores
src/market.py           Yahoo list + AAV / Fantrax
src/auction.py          surplus $ then market overwrite
src/coach.py            Stay / Stretch / Pass, feed parse
src/room.py             live heat from logged sales
src/sidecar.py          helper session
src/yahoo_auction.py    mock clocks + bots
src/season.py           in-season pad; 4 adds/week; no IL in this league
src/nba_feed.py         free NBA stats feed (nba_api) → data/season/; never Yahoo
src/schedule.py         fantasy weeks, week grid, back-to-backs (Eastern day)
src/daily.py            per-game line: per-minute rates × minutes, season-line anchor
src/season_data.py      reads data/season/ (feed, pasted rosters, matchups) for the pad
src/context.py          opponent / home factors and per-player back-to-back rest, from logs
src/injuries.py         ESPN free injury feed → chance to play; manual mark beats it
src/matchup.py          simulated week: 12-cat totals, chance per cat, swing weights
src/lineup.py           legal five (strict PG/SG/SF/PF/C) and the week plan
src/outlook.py          3-season + age model for the season pad's anchor line (data/season/outlook.csv); not the draft board
scripts/refresh_season.py  season feed refresh (systemd timer: scripts/systemd/, 08:00 / 18:00 / 23:30)
src/lab.py              headless 2k/10k rooms; unique greedy squad
src/draft_room.py       pool, slots, paths
src/draft_server.py     Flask (`/` home)
src/static/motion.js    logo home-reset + transitions
tests/                  pytest; no math implementations
data/                   projections, sessions; do not commit secrets
```

## Constraints that keep coming back

- No Yahoo API. No official NBA logo.
- Do not edit the original plan file.
- Do not scrape Yahoo or wire a live league.
- Do not commit unless Mario asks.
- UI changes: verify `/season`, `/helper`, `/draft`, `/lab` as touched. Helper and mock must stay consistent.

## Double-check list

1. `pytest tests/ -q` with the `.venv` Python.
2. Helper and mock session files still separate after a restart.
3. Jokic list $60, Stay $108, Stretch $144, Kawhi list $27. $100 on Jokic is Stay.
4. `quote("Justin Edwards")` is `None`. `quote("luka")` is `None`; use `quote("Luka Dončić")`.
5. A quiet first star sale does not raise Cade’s Stay; a $160 Jokic does (Cade this-room ≤ 1.22× fair). Two hot star sales also do.
6. Lab language: modal slot ≠ one room that happened. Squad names are unique. Alondes is $1 / not draftable.
7. Logo from helper/draft/lab/season resets those sessions and opens `/`.
8. No exploit, scrape, or Yahoo-live wiring.
9. Season pad: no IL, Hezonja stays, Tre Jones on the 10, week 1 has 1 of 4 adds used.
10. Season helper: no Yahoo calls anywhere in `nba_feed.py` / `injuries.py`; `/season` shows a matchup card only when `matchups.csv` names the week’s opponent; add plans never offer a rostered name or drop Hezonja.

## Mario’s roster (week 1)

Yahoo My Team after dropping Davion Mitchell for Tre Jones. **Hezonja stays.**

PG Keyonte George · SG Kawhi Leonard · SF Jalen Williams · PF John Collins · C Nikola Jokić · BN Mario Hezonja, Jrue Holiday, Neemias Queta, Dillon Brooks, Tre Jones.

1 of 4 adds used this week. Holes: TO, PF. No IL — a DNP costs a drop to stream.
