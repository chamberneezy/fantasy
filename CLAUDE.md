# NBA Fantasy draft tool — briefing for Claude

Mario’s private unpublished helper for an NBA salary-cap draft: 16 teams, **$200** default draft dollars, **10 drafted seats** (PG/SG/SF/PF/C + 5 BN). IL+ is in-season only. Live draft is Sunday 4 Oct 2026. This is an information pad. It does **not** open Yahoo, does **not** auto-bid, and must not grow a cheat path.

Yahoo settings confirm the 12 H2H cats, 16 teams, 10 seats, 4 divisions, 8-team playoffs in weeks 18–20, daily lineup lock, 4 adds/week, no Yahoo waivers, commissioner trade review. **No dynasty this draft** (Keep/Locked stay for other nights). Yahoo currently lists Draft Type as Offline; the helper types what happens either way. “Not a cash league” means Yahoo prize league is off, not that the $200 cap is gone.

If you are double-checking work, treat `context/system_rules.md` and `.cursorrules` as the contract. This file is the map of what exists and what is trustworthy.

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

Flask on `127.0.0.1:5340`. Use Xcode Python (Homebrew `python3` often lacks pandas):

```
/Applications/Xcode.app/Contents/Developer/usr/bin/python3 src/draft_server.py
/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/ -q
```

Wordmark is **NBA Fantasy**. Do not revive Pilsner naming.

| URL | What it is | Session file |
|---|---|---|
| `/` | Home. Logo click from any page lands here after a full reset. | — |
| `/draft` | Practice **mock** (Yahoo clocks, bots) | `data/draft_session.json` |
| `/helper` | Live-night **input pad** | `data/helper_session.json` |
| `/lab` | Headless batch rooms + scenarios | `data/lab_report.json` |

These sessions must not overwrite each other. Starting helper must not wipe a mock. Do not delete `draft_session.json` on server restart. Logo (`data-home-reset`) clears helper, mock, **and** lab, then goes `/`.

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

**Trust for draft night**

- 12-cat z-score contract and tests in `tests/test_math_engine.py`.
- Yahoo list + Stay/Stretch from published sources in `market.py` (apex 1.80× / 2.40× on listed ≥ $50).
- Helper loop: name → Stay/Stretch/Pass → Sold/Me → leftover seats.
- Room heat after **two** hammers in a tier, **or** one nuclear first $50+ hammer. Not after one $87 Jokic.
- Unlisted = $1 on this board. Lab “most common name at each seat” is unique greedy — never two Sabonis.

**Do not treat as a forecast**

- `/lab` bots (7 tight / 7 room / 1 heat, invented interest). Modal squads (e.g. Cade in 95% of rooms) are leftover gravity, not scouting. The collage is not one room that happened.
- Surplus-only ranks that used to price Kawhi like a $50 star or Alondes like a $34 mid. If Yahoo lists $27, the list wins. If Yahoo does not list him, he is $1.
- Health-trap “steals” on rate (Embiid $17, Ja $5) without looking at predicted games.

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
- Do not build the in-season fantasy page yet.
- Do not commit unless Mario asks.
- UI changes: verify `/helper`, `/draft`, `/lab` as touched. Helper and mock must stay consistent.

## Double-check list

1. `pytest tests/ -q` with Xcode Python.
2. Helper and mock session files still separate after a restart.
3. Jokic list $60, Stay $108, Stretch $144, Kawhi list $27. $100 on Jokic is Stay.
4. `quote("Justin Edwards")` is `None`. `quote("luka")` is `None`; use `quote("Luka Dončić")`.
5. A quiet first star sale does not raise Cade’s Stay; a $160 Jokic does (Cade this-room ≤ 1.22× fair). Two hot star sales also do.
6. Lab language: modal slot ≠ one room that happened. Squad names are unique. Alondes is $1 / not draftable.
7. Logo from helper/draft/lab resets those sessions and opens `/`.
8. No exploit, scrape, or Yahoo-live wiring.

Owner: Mario. Prefer working in `src/` and tests, not a new parallel tool.
