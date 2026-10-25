"""One small JSON for the iPhone app: today's five, the week's starts, per-cat leans, and the news.

Built from the same session and feed as the laptop pad. No win percentage on
purpose: categories carry a word (likely / lean / coin flip), not a number.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import matchup as matchup_stats
import opportunity
import schedule as slate
import season

FEED_VERSION = 2
# Chance of winning a category (tie counts half) → the word shown.
LEAN_WORDS = ((0.75, "likely yours"), (0.58, "lean yours"), (0.42, "coin flip"), (0.25, "lean his"))
LEAN_FLOOR = "unlikely"
LINE_STATS = ("pts", "reb", "ast", "fg3m", "stl", "blk", "to")
GAME_STATS = ("min", "fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd")
RECENT_GAMES = 5


def lean_word(chance: float) -> str:
    for floor, word in LEAN_WORDS:
        if chance >= floor:
            return word
    return LEAN_FLOOR


def _line(line: dict | None) -> dict | None:
    if not line:
        return None
    return {"min": round(float(line.get("mp", 0.0)), 1), **{stat: round(float(line.get(stat, 0.0)), 1) for stat in LINE_STATS}}


def _average(games) -> dict | None:
    """Per-game averages, with FG% / FT% from made over attempted."""
    if not len(games):
        return None
    row = {stat: round(float(games[stat].mean()), 1) for stat in GAME_STATS if stat not in ("dd",)}
    row["dd"] = int(games["dd"].sum())
    row["fg_pct"] = round(float(games["fgm"].sum() / games["fga"].sum()), 3) if games["fga"].sum() else None
    row["ft_pct"] = round(float(games["ftm"].sum() / games["fta"].sum()), 3) if games["fta"].sum() else None
    row["games"] = int(len(games))
    return row


def player_card(data, name: str) -> dict:
    """Stats for one player: this season's averages, his last games, the pad's next-game line, injury."""
    games = data.season_games(name)
    recent = []
    for game in games.tail(RECENT_GAMES).iloc[::-1].to_dict("records"):
        recent.append(
            {
                "date": str(game["date"]),
                "opp": str(game["opp"]),
                "home": bool(game["home"]),
                **{stat: (round(float(game[stat]), 1) if stat == "min" else int(game[stat])) for stat in GAME_STATS},
            }
        )
    injury = data.injury(name) or {}
    line = data.line_for(name)
    return {
        "player_name": name,
        "team": data.team_of(name),
        "positions": data.positions_for(name)[0],
        "injury": {"status": str(injury.get("status") or ""), "return_date": str(injury.get("return_date") or ""), "note": str(injury.get("note") or "")}
        if injury
        else None,
        "season": _average(games),
        "recent": recent,
        "projection": opportunity.shown(line),
        "basis": (line or {}).get("basis", ""),
    }


def _today(grid: dict) -> dict:
    day = grid["day"]
    starters, bench = [], []
    for row in day["playing"]:
        item = {
            "player_name": row["player_name"],
            "positions": row["positions"],
            "team": row["team"],
            "seat": row["seat"],
            "opp": row["opp"],
            "home": bool(row["home"]),
            "tip_utc": row["tip_utc"],
            "status": row["status"] or "",
            "chance": row["chance"],
            "line": _line(row["line"]),
        }
        (starters if row["seat"] else bench).append(item)
    return {"date": day["date"], "starters": starters, "bench": bench, "off": day["off"]}


def _week(grid: dict, plan: dict) -> list[dict]:
    theirs = plan.get("theirs") or {}
    days = []
    for day in grid["days"]:
        seated = plan["lineups"].get(day["date"], {})
        days.append(
            {
                "date": day["date"],
                "dow": day["dow"],
                "past": bool(day["past"]),
                "my_starts": len(seated),
                "my_players": day["mine"],
                "their_players": len(theirs.get(day["date"], [])),
            }
        )
    return days


def _leans(matchup: dict | None, banked: dict | None) -> list[dict]:
    """Per-cat word for the week's end, plus Yahoo's real score when one is on file."""
    if not matchup:
        return []
    rows = []
    for row in matchup["cats"]:
        item = {"cat": row["cat"], "mine": row["mine"], "theirs": row["theirs"], "lean": lean_word(row["win"])}
        if banked:
            item["yahoo_mine"], item["yahoo_theirs"] = _yahoo_value(banked["mine"], row["cat"]), _yahoo_value(banked["theirs"], row["cat"])
        rows.append(item)
    return rows


def _yahoo_value(vector, cat: str) -> float:
    """One category from a ``matchup.STATS`` vector, as Yahoo shows it."""
    at = matchup_stats.AT
    if cat in matchup_stats.RATIOS:
        made, tried = matchup_stats.RATIOS[cat]
        return round(float(vector[at[made]] / vector[at[tried]]), 3) if vector[at[tried]] else 0.0
    return round(float(vector[at[matchup_stats.COUNTING[cat]]]), 1)


def _leans_note(banked: dict | None, today: date) -> str:
    if banked and banked["through"] >= (today.fromordinal(today.toordinal() - 1)).isoformat():
        return f"Starts from Yahoo's real score through {banked['through']}; only the days after are simulated."
    if banked:
        return f"Starts from Yahoo's score through {banked['through']}; the days after it assume both teams' best five. Send a fresh matchup screenshot."
    return "No Yahoo score on file this week: past days assume both teams started their best five."


def build(session, today: date) -> dict:
    data = session.data
    week = slate.week_for(today, data.weeks)
    grid = session.calendar(today, today)
    plan = session.week_plan(week, today)
    mine = [seat["player"]["player_name"] for seat in session.roster]
    protected = {name.casefold() for name in season.PROTECTED}
    return {
        "version": FEED_VERSION,
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "logs_through": data.logs_through(),
        "week": week["week"],
        "week_start": week["start"].isoformat(),
        "week_end": week["end"].isoformat(),
        "opponent": plan.get("opponent"),
        "adds_left": session.state(today).get("adds_left"),
        "today": _today(grid),
        "days": _week(grid, plan),
        "leans": _leans(grid.get("matchup"), plan.get("banked")),
        "yahoo_through": (plan.get("banked") or {}).get("through"),
        "leans_note": _leans_note(plan.get("banked"), today),
        "news": opportunity.news(data, mine, plan.get("opponent"), today, protected),
        "mine": [player_card(data, name) for name in mine],
        "theirs": [player_card(data, name) for name in (data.active_names(plan["opponent"]) if plan.get("opponent") else [])],
    }
