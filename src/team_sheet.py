"""My Team: the morning brief, the Yahoo-style sheet for one day, and the lineup moves.

The sheet mirrors Yahoo's My Team page: each seat, who sits in it now, tonight's
game, and a stat line (tonight's projection, his last game, last 7 days, this
season, or the season projection). Moves compare the five sitting in the seats
now with the five the week plan picks, and say why for each change.

Nothing here is a second model. Tonight's lines, chances and category swing
come from the week plan the rest of the pad already uses.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

import daily
import lineup
import matchup
import schedule as slate
from math_engine import ALL_CATEGORIES, NEGATIVE_CATEGORIES

LINE_STATS = ("mp", "fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd")
RECENT_DAYS = 7
# A chance to play below this is called out as the reason a player sits.
DOUBTFUL = 0.75
# A day with fewer starters than seats is worth an add; say so in the brief.
SEAT_COUNT = len(lineup.SEATS)
CAT_SHORT = {"MIN": "min", "3PM": "3s", "PTS": "pts", "REB": "reb", "AST": "ast", "STL": "stl", "BLK": "blk", "TO": "to", "PF": "pf", "DD": "DD"}


def _with_rates(line: dict) -> dict:
    line["fg_pct"] = round(line["fgm"] / line["fga"], 3) if line["fga"] else None
    line["ft_pct"] = round(line["ftm"] / line["fta"], 3) if line["fta"] else None
    return line


def average(games: pd.DataFrame) -> dict | None:
    """Per-game line over these games. Shooting is made over attempted, not a mean of nights."""
    if games.empty:
        return None
    line = {stat: round(float(games[stat if stat != "mp" else "min"].mean()), 2 if stat == "dd" else 1) for stat in LINE_STATS}
    sums = games[["fgm", "fga", "ftm", "fta"]].sum()
    line["fg_pct"] = round(float(sums["fgm"] / sums["fga"]), 3) if sums["fga"] else None
    line["ft_pct"] = round(float(sums["ftm"] / sums["fta"]), 3) if sums["fta"] else None
    line["games"] = int(len(games))
    return line


def one_game(row: pd.Series) -> dict:
    line = {stat: int(round(float(row[stat if stat != "mp" else "min"]))) for stat in LINE_STATS}
    line = _with_rates(line)
    line.update(date=str(row["date"]), opp=str(row["opp"]), home=bool(row["home"]))
    return line


def vector_line(values: np.ndarray) -> dict:
    """A line from a ``matchup.STATS`` row (a banked game)."""
    line = {stat: int(round(float(values[matchup.AT[stat]]))) for stat in LINE_STATS}
    return _with_rates(line)


def projected(line: dict | None) -> dict | None:
    if line is None:
        return None
    shown = {stat: round(float(line.get(stat) or 0.0), 2 if stat == "dd" else 1) for stat in LINE_STATS}
    return _with_rates(shown) | {"value": round(float(line.get("value") or 0.0), 2)}


def week_totals(games: pd.DataFrame) -> dict | None:
    """Summed box score over these games, with its per-game average kept for scoring."""
    if games.empty:
        return None
    line = {stat: int(round(float(games[stat if stat != "mp" else "min"].sum()))) for stat in LINE_STATS}
    line = _with_rates(line)
    line["games"] = int(len(games))
    line["per_game"] = average(games)
    return line


def _score(stats: dict, baselines: dict) -> dict:
    """Give every view a ``value``: the 12-cat z of its per-game line, 0 = a typical player."""
    keyed = []
    for view, line in stats.items():
        if line is None:
            continue
        per_game = line.get("per_game") or line
        keyed.append((view, {key: (per_game.get(key) or 0.0) for key in (*LINE_STATS, "fg_pct", "ft_pct")}))
    if not keyed:
        return stats
    scored = daily.score_lines([line for _, line in keyed], baselines)
    for (view, _), result in zip(keyed, scored):
        stats[view] = {**stats[view], "value": result["value"]}
        stats[view].pop("per_game", None)
    return stats


def player_stats(data, name: str, chosen: date, tonight: dict | None, week_start: date | None = None, banked=None) -> dict:
    """Every view of the sheet for one player, as of the morning of ``chosen``."""
    games = data.season_games(name)
    before = games.loc[games["date"] < chosen.isoformat()] if len(games) else games
    recent = before.loc[before["date"] >= (chosen - timedelta(days=RECENT_DAYS)).isoformat()] if len(before) else before
    this_week = before.loc[before["date"] >= week_start.isoformat()] if week_start and len(before) else before.iloc[0:0]
    stats = {
        "today": vector_line(banked) if banked is not None else projected(tonight),
        "last": one_game(before.iloc[-1]) if len(before) else None,
        "l7": average(recent),
        "season": average(before),
        "week": week_totals(this_week),
        "proj": projected(data.line_for(name)),
    }
    return _score(stats, data.baselines)


def injury_tag(data, name: str) -> dict | None:
    listed = data.injury(name)
    if not listed or not str(listed.get("status") or "").strip():
        return None
    status = str(listed["status"]).strip()
    short = {"out": "O", "day-to-day": "DTD", "questionable": "Q", "doubtful": "D", "probable": "P", "game time decision": "GTD"}
    return {
        "status": status,
        "short": short.get(status.lower(), status[:3].upper()),
        "part": str(listed.get("part") or ""),
        "back": str(listed.get("return_date") or ""),
    }


def _swing(entry: dict | None, weights: dict | None) -> dict[str, float] | None:
    if not entry or not weights or entry.get("line") is None:
        return None
    return matchup.game_swing(entry, weights)


def _worth(entry: dict | None, weights: dict | None) -> float | None:
    swing = _swing(entry, weights)
    if swing is not None:
        return float(sum(swing.values()))
    if entry and entry.get("line") is not None:
        return float(entry.get("value") or 0.0)
    return None


def _helps(swing: dict[str, float] | None, sign: int = 1, top: int = 2) -> list[str]:
    if not swing:
        return []
    ranked = sorted(((sign * value, cat) for cat, value in swing.items() if sign * value > 0.01), reverse=True)
    return [cat for _, cat in ranked[:top]]


def _game_text(game: dict) -> str:
    return f"{'vs' if game['home'] else '@'} {game['opp']}"


def _sit_reason(name: str, entry: dict | None, rec_seat: str | None, rival: dict | None, weights: dict | None) -> str:
    if rec_seat:
        return f"moves to {rec_seat}"
    if entry is None:
        return "no game"
    chance = float(entry.get("p", 1.0))
    if chance <= 0:
        return f"out{' · ' + entry['why'] if entry.get('why') else ''}"
    if chance < DOUBTFUL:
        return f"{round(chance * 100)}% to play{' · ' + entry['why'] if entry.get('why') else ''}"
    mine = _worth(entry, weights)
    costs = _helps(_swing(entry, weights), sign=-1)
    if rival is None:
        return f"costs you {', '.join(costs)}" if costs else "adds nothing tonight"
    theirs = _worth(rival, weights)
    if mine is not None and theirs is not None:
        unit = "cats" if weights else "value"
        text = f"{mine:+.2f} vs {theirs:+.2f} {unit}"
        return f"{text} · costs {', '.join(costs)}" if costs else text
    return "a better game is open"


def _start_reason(entry: dict, weights: dict | None, from_seat: str | None) -> str:
    parts = [_game_text(entry["game"])]
    worth = _worth(entry, weights)
    if worth is not None:
        parts.append(f"{worth:+.2f} {'cats' if weights else 'value'}")
    helps = _helps(_swing(entry, weights))
    if helps:
        parts.append(f"helps {', '.join(helps)}")
    if entry["game"].get("b2b"):
        parts.append("2nd of back-to-back")
    if from_seat and from_seat != "BN":
        parts.append(f"from {from_seat}")
    return " · ".join(parts)


def lineup_moves(current: dict[str, str], recommended: dict[str, str], entries: dict[str, dict], weights: dict | None) -> list[dict]:
    """Seat-by-seat changes from the five sitting now to the recommended five."""
    rec_seat = {name: seat for seat, name in recommended.items()}
    cur_seat = {name: seat for seat, name in current.items()}
    moves = []
    for seat in lineup.SEATS:
        now, best = current.get(seat), recommended.get(seat)
        if now == best:
            continue
        if best is None and (now is None or now not in entries):
            continue  # nobody to start, and the one there has no game anyway: no click needed
        move = {"seat": seat, "start": best, "sit": now}
        if best is not None:
            move["start_why"] = _start_reason(entries[best], weights, cur_seat.get(best, "BN"))
        else:
            move["start_why"] = "leave it empty: nobody eligible adds anything"
        if now is not None:
            move["sit_why"] = _sit_reason(now, entries.get(now), rec_seat.get(now), entries.get(best) if best else None, weights)
        moves.append(move)
    return moves


def bench_reasons(recommended: dict[str, str], entries: dict[str, dict], weights: dict | None) -> list[dict]:
    """Players with a game who still sit, and why: injury, rest, or a better game at every seat he fits."""
    seated = set(recommended.values())
    reasons = []
    for name, entry in entries.items():
        if name in seated or entry.get("line") is None:
            continue
        fits = [seat for seat in lineup.SEATS if seat in entry["positions"]]
        rivals = [(seat, recommended[seat]) for seat in fits if seat in recommended]
        rival = min(rivals, key=lambda pair: _worth(entries[pair[1]], weights) or 0.0) if rivals else None
        why = _sit_reason(name, entry, None, entries[rival[1]] if rival else None, weights)
        if rival and why[0] in "+-":
            why = f"{why} ({rival[1]} at {rival[0]})"
        elif not rivals and fits:
            why = f"{why} · every seat he fits ({'/'.join(fits)}) stays empty" if why == "adds nothing tonight" else why
        reasons.append({"player_name": name, "game": _game_text(entry["game"]), "why": why})
    return reasons


def sheet(session, chosen: date, plan: dict, today: date, protected: frozenset = frozenset()) -> dict:
    """The My Team sheet for ``chosen``: rows, the moves, and empty seats."""
    data = session.data
    iso = chosen.isoformat()
    day_entries = {entry["name"]: entry for entry in plan["mine"].get(iso, [])}
    recommended = plan["lineups"].get(iso, {})
    weights = plan.get("weights")
    current = {seat["slot_id"]: seat["player"]["player_name"] for seat in session.roster if seat["slot_id"] in lineup.SEATS}
    rec_seat = {name: seat for seat, name in recommended.items()}
    week_start = date.fromisoformat(min(plan["mine"])) if plan["mine"] else None
    order = {slot: index for index, slot in enumerate(lineup.SEATS)}
    rows = []
    for seat in sorted(session.roster, key=lambda item: (order.get(item["slot_id"], 9), item["slot_id"])):
        player = seat["player"]
        name = player["player_name"]
        entry = day_entries.get(name)
        game = entry["game"] if entry else None
        swing = _swing(entry, weights)
        rows.append(
            {
                "slot": seat["slot_id"] if seat["slot_id"] in lineup.SEATS else "BN",
                "best": rec_seat.get(name, "BN"),
                "player_name": name,
                "team": session._team(player),
                "positions": session._positions(player),
                "protected": name in protected,
                "injury": injury_tag(data, name),
                "game": {field: game[field] for field in ("opp", "home", "tip_utc", "b2b")} if game else None,
                "chance": round(float(entry["p"]), 2) if entry and entry.get("line") is not None else None,
                "banked": bool(entry and entry.get("fixed") is not None),
                "worth": round(sum(swing.values()), 2) if swing else None,
                "stats": player_stats(
                    data,
                    name,
                    chosen,
                    entry.get("line") if entry else None,
                    week_start,
                    entry.get("fixed") if entry else None,
                ),
            }
        )
    playing = sum(1 for entry in day_entries.values() if entry.get("line") is not None or entry.get("fixed") is not None)
    return {
        "date": iso,
        "past": iso < today.isoformat(),
        "rows": rows,
        "moves": [] if iso < today.isoformat() else lineup_moves(current, recommended, day_entries, weights),
        "benched": [] if iso < today.isoformat() else bench_reasons(recommended, day_entries, weights),
        "playing": playing,
        "seated": len(recommended),
        "empty": [seat for seat in lineup.SEATS if seat not in recommended],
        "matchup_aware": bool(weights),
    }


def _totals(entries: list[dict]) -> np.ndarray | None:
    banked = [entry["fixed"] for entry in entries if entry.get("fixed") is not None]
    return np.sum(banked, axis=0)[None, :] if banked else None


def score_so_far(plan: dict, today: str) -> dict | None:
    """Categories as they stand from the days already played, starts as the pad seated them."""
    mine = _totals([entry for entry in lineup.started(plan["mine"], plan["lineups"]) if entry["date"] < today])
    if mine is None or "their_games" not in plan:
        return None
    theirs = _totals([entry for entry in plan["their_games"] if entry["date"] < today])
    if theirs is None:
        theirs = np.zeros_like(mine)
    my_values = matchup.category_values(mine)
    their_values = matchup.category_values(theirs)
    cats = []
    for category in ALL_CATEGORIES:
        sign = -1.0 if category in NEGATIVE_CATEGORIES else 1.0
        gap = sign * float(my_values[category][0] - their_values[category][0])
        cats.append(
            {
                "cat": category,
                "mine": float(my_values[category][0]),
                "theirs": float(their_values[category][0]),
                "call": "win" if gap > 1e-9 else "hole" if gap < -1e-9 else "ok",
            }
        )
    return {
        "cats": cats,
        "won": sum(row["call"] == "win" for row in cats),
        "lost": sum(row["call"] == "hole" for row in cats),
        "tied": sum(row["call"] == "ok" for row in cats),
    }


def brief(session, plan: dict, week: dict, today: date) -> dict:
    """What to read first in the morning: the score, last night, today, the days ahead."""
    data = session.data
    iso = today.isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    last_night = []
    no_show = []
    for name, _, team in session._my_players():
        played = data.actual(name, yesterday)
        if played is not None:
            line = vector_line(played)
            last_night.append({"player_name": name, **line})
        elif any(game["date"] == yesterday for game in slate.team_games(data.schedule, team, today - timedelta(days=1), today - timedelta(days=1))):
            no_show.append(name)
    last_night.sort(key=lambda row: -(row["pts"] + row["reb"] + row["ast"]))
    hurt = [
        {"player_name": name, **tag}
        for name, _, _ in session._my_players()
        if (tag := injury_tag(data, name)) is not None
    ]
    # Every game on the schedule counts, even for a player with no line yet (the grid does the same).
    scheduled: dict[str, int] = {}
    for _, _, team in session._my_players():
        for game in slate.team_games(data.schedule, team, week["start"], week["end"]):
            scheduled[game["date"]] = scheduled.get(game["date"], 0) + 1
    ahead = []
    for day in slate.week_days(week):
        key = day.isoformat()
        if key < iso:
            continue
        games = scheduled.get(key, 0)
        seated = len(plan["lineups"].get(key, {}))
        ahead.append(
            {
                "date": key,
                "dow": day.strftime("%a"),
                "games": games,
                "sits": max(0, games - SEAT_COUNT),
                "empty": SEAT_COUNT - seated if games else SEAT_COUNT,
            }
        )
    started = week["start"].isoformat() <= iso
    return {
        "today": iso,
        "week": week["week"],
        "opponent": plan.get("opponent"),
        "started": started,
        "starts_on": week["start"].isoformat(),
        "so_far": score_so_far(plan, iso) if started else None,
        "yesterday": yesterday,
        "last_night": last_night,
        "no_show": no_show,
        "hurt": hurt,
        "ahead": ahead,
    }
