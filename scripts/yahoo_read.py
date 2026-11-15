"""Read Mario's Yahoo league in a logged-in Chromium and write the pad's files. Read only.

Mario asked on 15 Nov 2026 for this to run every hour on his home server "gw" (it replaces
Claude reading the same pages by hand each morning). It only opens pages and reads their
tables: it never clicks, submits a form, or changes a lineup. Moves stay Mario's.

    .venv/bin/python scripts/yahoo_read.py --profile DIR            # hourly, headless
    .venv/bin/python scripts/yahoo_read.py --profile DIR --login    # once: a window to sign in to Yahoo

Writes data/season/league_rosters.csv, free_agents.csv, yahoo_scores.csv and the seats, IL,
week and adds in data/season_session.json. Exit code 3 when Yahoo asks to sign in again.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

import schedule as slate  # noqa: E402
import season  # noqa: E402
import yahoo_snapshot  # noqa: E402

LEAGUE = "https://basketball.fantasysports.yahoo.com/nba/51867/"
MY_TEAM = 15
FEED = ROOT / "data" / "season"
SESSION = ROOT / "data" / "season_session.json"
FREE_AGENT_PAGES = ("", "&count=25", "&count=50")
FREE_AGENTS = "players?status=A&pos=P&cut_type=33&stat1=S_L30&sort=AR&sdir=1"
CHROMIUM = "/usr/bin/chromium"

# Same-origin GETs read in the page, as Claude did in Chrome. Returns plain cell text only.
READ_JS = """
async (paths) => {
  const page = async (path) => new DOMParser().parseFromString(await (await fetch(path, {credentials: 'include'})).text(), 'text/html');
  const cells = (row) => [...row.querySelectorAll('th,td')].map(c => c.textContent.replace(/\\s+/g, ' ').trim());
  const out = {};
  const m = await page(paths.matchup);
  const totals = m.querySelectorAll('table')[1];
  out.matchup = {
    rows: totals ? [...totals.querySelectorAll('tr')].map(cells) : [],
    teams: totals ? [...totals.querySelectorAll('a')].map(a => [a.getAttribute('href'), a.textContent.trim()]) : [],
    week: (m.body.textContent.match(/Week (\\d+)/) || [])[1] || null,
  };
  const t = await page(paths.team);
  const lineup = t.querySelector('#statTable0');
  out.team = {rows: lineup ? [...lineup.querySelectorAll('tbody tr')].map(cells) : [], text: t.body.textContent};
  const r = await page(paths.rosters);
  out.rosters = [...r.querySelectorAll('table')].map(table => {
    let head = table.previousElementSibling, hops = 0;
    while (head && !head.textContent.trim() && hops < 5) { head = head.previousElementSibling; hops++; }
    return {team: head ? head.textContent.replace(/\\s+/g, ' ').trim() : '', rows: [...table.querySelectorAll('tbody tr')].map(cells)};
  });
  out.free_agents = [];
  for (const path of paths.free_agents) {
    const f = await page(path);
    const table = [...f.querySelectorAll('table')].find(x => /Player Note/.test(x.textContent));
    if (table) out.free_agents.push(...[...table.querySelectorAll('tbody tr')].map(cells));
  }
  if (paths.last_week) {
    const p = await page(paths.last_week);
    const lt = p.querySelectorAll('table')[1];
    out.last_week = lt ? [...lt.querySelectorAll('tr')].map(cells) : [];
  }
  return out;
}
"""


def _context(playwright, profile: Path, headed: bool):
    return playwright.chromium.launch_persistent_context(
        str(profile),
        executable_path=CHROMIUM,
        headless=not headed,
        args=["--ozone-platform-hint=auto"],
        locale="en-US",
        timezone_id="America/New_York",
    )


def login(profile: Path) -> int:
    """A visible window on gw's screen: Mario signs in to Yahoo himself, then closes it."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _context(playwright, profile, headed=True)
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(LEAGUE)
        print("Sign in to Yahoo in the window, open your league once, then close the window.")
        page.wait_for_event("close", timeout=0)
        browser.close()
    return 0


def _row_stats(cells: list[str]) -> str:
    """Team | 14 stats | score → the 14 stats as ``score_row`` reads them."""
    return "|".join(cells[1:15])


def _score_rows(rows: list[list[str]]) -> tuple[str, str] | None:
    data = [cells for cells in rows if len(cells) >= 15 and "/" in cells[2] and cells[1].replace(".", "").isdigit()]
    return (_row_stats(data[0]), _row_stats(data[1])) if len(data) >= 2 else None


def read(profile: Path) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _context(playwright, profile, headed=False)
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(LEAGUE, wait_until="domcontentloaded")
        if "login.yahoo.com" in page.url or "guce.yahoo.com" in page.url:
            browser.close()
            raise PermissionError(f"Yahoo wants a sign-in ({page.url.split('?')[0]})")
        today = season.league_today()
        weeks = slate.load_weeks(slate.load_schedule(FEED / "schedule.csv"))
        week = slate.week_for(today, weeks)
        last_week = None
        if week and week["start"] == today and week["week"] > 1:
            last_week = f"matchup?week={week['week'] - 1}&mid1={MY_TEAM}"
        paths = {
            "matchup": f"matchup?mid1={MY_TEAM}",
            "team": f"{MY_TEAM}/team",
            "rosters": "startingrosters",
            "free_agents": [FREE_AGENTS + extra for extra in FREE_AGENT_PAGES],
            "last_week": last_week,
        }
        found = page.evaluate(READ_JS, paths)
        browser.close()
    found["today"] = today.isoformat()
    found["week_info"] = week
    return found


def _tips_today(today: str) -> tuple[list[str], bool]:
    schedule = pd.read_csv(FEED / "schedule.csv", dtype={"game_id": str})
    games = schedule.loc[schedule["date"] == today]
    logs_path = FEED / "gamelogs_2026-27.csv"
    logged = set(pd.read_csv(logs_path, dtype={"game_id": str})["game_id"]) if logs_path.exists() else set()
    return sorted(games["tip_utc"].astype(str)), bool(len(games)) and set(games["game_id"]) <= logged


def write(found: dict) -> list[str]:
    """The files from one read. Returns what changed, in words."""
    notes = []
    known = [str(name) for name in pd.read_csv(FEED / "players.csv")["player_name"]]

    # League rosters: one line per team, then the existing parser.
    path = FEED / "league_rosters.csv"
    old = pd.read_csv(path)
    managers = old.drop_duplicates("fantasy_team").set_index("fantasy_team")["manager"].to_dict()
    teams = {}
    for table in found["rosters"]:
        if not table["team"]:
            continue
        items = [yahoo_snapshot.seat_text(cells[0], cells[1]) for cells in table["rows"] if len(cells) >= 2]
        teams[table["team"]] = "; ".join(item for item in items if item)
    if len(teams) >= 16:
        rows = yahoo_snapshot.roster_rows(teams, managers, known)
        rows.to_csv(path, index=False, lineterminator="\r\n")
        notes.append(f"rosters: {len(rows)} players on {rows['fantasy_team'].nunique()} teams")
    else:
        notes.append(f"rosters skipped: {len(teams)} teams read")

    # Free agents: "Name TEAM POS,POS|pre|current|pct%".
    lines = []
    for cells in found["free_agents"]:
        if len(cells) < 9:
            continue
        text = yahoo_snapshot.seat_text("FA", cells[2])
        if text:
            lines.append(f"{text[3:].replace(' - ', ' ')}|{cells[6]}|{cells[7]}|{cells[8]}")
    if lines:
        yahoo_snapshot.free_agent_rows(lines, known).to_csv(FEED / "free_agents.csv", index=False)
        notes.append(f"free agents: {len(lines)}")

    # The score, only for days whose games are all in Yahoo's totals.
    week = found.get("week_info")
    yahoo_week = int(found["matchup"]["week"]) if found["matchup"].get("week") else None
    tips, final = _tips_today(found["today"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    through = yahoo_snapshot.score_through(found["today"], tips, final, now)
    pair = _score_rows(found["matchup"]["rows"])
    saved = []
    if week and yahoo_week == week["week"] and pair and through and through >= week["start"].isoformat():
        saved.append(yahoo_snapshot.score_row(yahoo_week, through, "mine", pair[0]))
        saved.append(yahoo_snapshot.score_row(yahoo_week, through, "theirs", pair[1]))
        notes.append(f"score week {yahoo_week} through {through}")
    elif not through:
        notes.append("score skipped: games in progress")
    last = _score_rows(found.get("last_week") or [])
    if last and week:
        end = (week["start"] - timedelta(days=1)).isoformat()
        saved.append(yahoo_snapshot.score_row(week["week"] - 1, end, "mine", last[0]))
        saved.append(yahoo_snapshot.score_row(week["week"] - 1, end, "theirs", last[1]))
        notes.append(f"final score week {week['week'] - 1}")
    if saved:
        yahoo_snapshot.save_score(FEED / "yahoo_scores.csv", saved)

    # My seats, IL, adds and week in the session.
    found_seats = yahoo_snapshot.seats([(cells[0], cells[1]) for cells in found["team"]["rows"] if len(cells) >= 2])
    if len([seat for seat in found_seats if seat[0] != "IL"]) == 10:
        session = json.loads(SESSION.read_text(encoding="utf-8"))
        adds = yahoo_snapshot.adds_used(found["team"]["text"])
        updated, changes = yahoo_snapshot.sync_session(session, found_seats, adds, yahoo_week, found["today"])
        if updated != session:
            SESSION.write_text(json.dumps(updated, indent=2), encoding="utf-8")
        notes.append("session: " + (", ".join(changes) if changes else "unchanged"))
    else:
        notes.append(f"session skipped: {len(found_seats)} seats read")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", type=Path, required=True, help="Chromium profile that holds the Yahoo sign-in")
    parser.add_argument("--login", action="store_true", help="open a window to sign in to Yahoo")
    args = parser.parse_args()
    if args.login:
        return login(args.profile)
    try:
        found = read(args.profile)
    except PermissionError as exc:
        print(f"Yahoo sign-in needed: {exc}. Run: scripts/server/yahoo_login.sh")
        return 3
    for note in write(found):
        print(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
