"""One small JSON for the iPhone app: today's five, the week's starts, per-cat leans, and the news.

Built from the same session and feed as the laptop pad. No win percentage on
purpose: categories carry a word (likely / lean / coin flip), not a number.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np

import matchup as matchup_stats
import opportunity
import schedule as slate
import stats_board

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
    """Per-cat word for the week's end, plus the score so far (``live_totals``) when there is one."""
    if not matchup:
        return []
    rows = []
    for row in matchup["cats"]:
        item = {"cat": row["cat"], "mine": row["mine"], "theirs": row["theirs"], "lean": lean_word(row["win"])}
        if banked:
            item["yahoo_mine"], item["yahoo_theirs"] = _yahoo_value(banked["mine"], row["cat"]), _yahoo_value(banked["theirs"], row["cat"])
        rows.append(item)
    return rows


SEATS = 5


def live_totals(plan: dict, today: date) -> dict | None:
    """The week so far: Yahoo's last typed-in totals, plus ESPN box scores for every finished day after them.

    A day counts each team's starters. With five or fewer players in games they all
    started, so the day is exact; with more, the five who played the most minutes are
    assumed, and the day is listed in ``assumed`` (Yahoo may show a different five).
    """
    if not plan.get("result"):
        return None
    banked = plan.get("banked")
    start = banked["through"] if banked else ""
    yesterday = date.fromordinal(today.toordinal() - 1).isoformat()
    sides = {
        "mine": (plan["mine"], plan["lineups"], banked["mine"].copy() if banked else np.zeros(len(matchup_stats.STATS))),
        "theirs": (plan["theirs"], plan.get("their_lineups") or {}, banked["theirs"].copy() if banked else np.zeros(len(matchup_stats.STATS))),
    }
    assumed, counted = [], False
    for side, (by_day, lineups, total) in sides.items():
        for day, entries in by_day.items():
            if day <= start or day > yesterday:
                continue
            counted = True
            played = [entry for entry in entries if entry.get("fixed") is not None and entry["fixed"][matchup_stats.AT["mp"]] > 0]
            if len(played) > SEATS:
                assumed.append({"side": side, "date": day, "played": len(played)})
            seated = set(lineups.get(day, {}).values())
            for entry in played:
                if entry["name"] in seated:
                    total += entry["fixed"]
    through = yesterday if counted else (start or None)
    if not through:
        return None
    return {"through": through, "yahoo_through": start or None, "mine": sides["mine"][2], "theirs": sides["theirs"][2], "assumed": sorted(assumed, key=lambda row: row["date"])}


def score(leans: list[dict], through: str | None) -> dict | None:
    """The week's score as Yahoo shows it (categories won, lost, tied) and the outlook as counts of lean words."""
    if not leans:
        return None
    outlook = {"yours": 0, "coin_flip": 0, "his": 0}
    for row in leans:
        key = "yours" if row["lean"] in ("likely yours", "lean yours") else "coin_flip" if row["lean"] == "coin flip" else "his"
        outlook[key] += 1
    result = {"through": through, "outlook": outlook}
    if through and all("yahoo_mine" in row for row in leans):
        won = lost = tied = 0
        for row in leans:
            mine, theirs = row["yahoo_mine"], row["yahoo_theirs"]
            if mine == theirs:
                tied += 1
            elif (mine < theirs) == (row["cat"] in ("TO", "PF")):
                won += 1
            else:
                lost += 1
        result.update(won=won, lost=lost, tied=tied)
    return result


CATEGORIES = ("MIN", "FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO", "PF", "DD")


def season_weeks(session, current: int, today: date) -> list[dict]:
    """Every week with an opponent on file: dates, opponent, and the score.

    Finished weeks are scored like the live week: Yahoo's last typed-in totals plus
    box scores through Sunday. Later weeks show only the opponent.
    """
    data = session.data
    rows = []
    for week in data.weeks:
        opponent = data.matchups.get(week["week"])
        if not opponent:
            continue
        row = {
            "week": week["week"],
            "start": week["start"].isoformat(),
            "end": week["end"].isoformat(),
            "opponent": opponent,
            "current": week["week"] == current,
        }
        if week["end"] < today:
            day_after = date.fromordinal(week["end"].toordinal() + 1)
            live = live_totals(session.week_plan(week, day_after), day_after)
            if live:
                leans = [
                    {"cat": cat, "lean": "", "yahoo_mine": _yahoo_value(live["mine"], cat), "yahoo_theirs": _yahoo_value(live["theirs"], cat)}
                    for cat in CATEGORIES
                ]
                counted = score(leans, live["through"])
                row.update(through=live["through"], won=counted["won"], lost=counted["lost"], tied=counted["tied"], final=True)
        rows.append(row)
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


def _with_live(weeks: list[dict], live: dict | None, leans: list[dict]) -> list[dict]:
    """The current week in the season list shows the same live score as the score card."""
    block = score(leans, (live or {}).get("through")) if live else None
    for row in weeks:
        if row["current"] and block and "won" in block:
            row.update(through=block["through"], won=block["won"], lost=block["lost"], tied=block["tied"], final=block["through"] >= row["end"])
    return weeks


def _score_block(leans: list[dict], live: dict | None) -> dict | None:
    block = score(leans, (live or {}).get("through"))
    if block and live:
        block["yahoo_through"] = live["yahoo_through"]
        block["assumed"] = live["assumed"]
        block["basis"] = _basis(live)
    return block


def _basis(live: dict) -> str:
    """One line on where the score comes from, and which days guess the starters."""
    parts = []
    if live["yahoo_through"]:
        parts.append(f"Yahoo to {_day(live['yahoo_through'])}")
    if live["through"] != live["yahoo_through"]:
        parts.append(f"box scores to {_day(live['through'])}")
    text = " + ".join(parts) if parts else "box scores"
    if live["assumed"]:
        guesses = ", ".join(f"{'your' if row['side'] == 'mine' else 'his'} {_day(row['date'])}" for row in live["assumed"])
        text += f". Starters guessed on {guesses} (more than five played)."
    return text


def _day(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%a %-d %b")


def _cards(data, board: dict, mine: list[str], theirs: list[str]) -> dict:
    """A player page (last games, injury, projection) for everyone on the board, keyed by name."""
    names = {*mine, *theirs}
    for window in board["rows"].values():
        names.update(row["player_name"] for row in window["league"])
    return {name: player_card(data, name) for name in sorted(names)}


def build(session, today: date) -> dict:
    data = session.data
    week = slate.week_for(today, data.weeks)
    grid = session.calendar(today, today)
    plan = session.week_plan(week, today)
    mine = [seat["player"]["player_name"] for seat in session.roster]
    protected = {name.casefold() for name in session.protected}
    their = data.active_names(plan["opponent"]) if plan.get("opponent") else []
    board = stats_board.board(data, today, mine, their)
    return {
        "version": FEED_VERSION,
        "team": session.team,
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "logs_through": data.logs_through(),
        "week": week["week"],
        "week_start": week["start"].isoformat(),
        "week_end": week["end"].isoformat(),
        "opponent": plan.get("opponent"),
        "adds_left": session.state(today).get("adds_left"),
        "today": _today(grid),
        "days": _week(grid, plan),
        "leans": (leans := _leans(grid.get("matchup"), live := live_totals(plan, today))),
        "score": _score_block(leans, live),
        "season": _with_live(season_weeks(session, week["week"], today), live, leans),
        "yahoo_through": (live or {}).get("through"),
        "leans_note": _leans_note(plan.get("banked"), today),
        "news": opportunity.news(data, mine, plan.get("opponent"), today, protected),
        "mine": [player_card(data, name) for name in mine],
        "theirs": [player_card(data, name) for name in their],
        "stats": board,
        "cards": _cards(data, board, mine, their),
    }
