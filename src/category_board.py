"""The morning report: every player and every decision across all 12 categories.

Each category counts the same. A player's value is the plain sum of his 12
z-scores from ``math_engine``, and a move is judged by the change in the chance
of each category. Yahoo's totals (``yahoo_scores.csv``) start the week when typed in.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import lineup
import matchup
from app_feed import lean_word
from espn_feed import name_key
from math_engine import ALL_CATEGORIES, NEGATIVE_CATEGORIES, FantasyMathEngine

MIN_GAMES = 3
# Replay of 20 weeks of 2025-26 (1,846 category calls): the fairest chance is this share
# of the model's log-odds. Said 91% happened 83%, said 9% happened 22%.
CONFIDENCE_SHRINK = 0.6
LOCKED = 0.995
GONE = 0.005
# A free agent absent from this many of his team's latest games, listed or not, has no usable line.
MISSED_GAMES_OUT = 2
MINUTE_SWING = 3.0
RECENT_GAMES = 3
MOVE_RUNS = 20000
MOVES_SIMULATED = 12
MOVES_SHOWN = 6
LONG_RUN_MOVES = 4
LONG_RUN_WEEKS = 3
OPPONENT_ADDS = 2
FORECAST_COLUMNS = ("made_on", "week", "opponent", "cat", "chance", "fair")


def per_game_frame(logs: pd.DataFrame) -> pd.DataFrame:
    """One row per player: his per-game line this season, in the engine's columns."""
    if logs.empty:
        return pd.DataFrame()
    grouped = logs.sort_values("date", kind="mergesort").groupby("player_name")
    frame = grouped[["fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd"]].mean()
    frame["mp"] = grouped["min"].mean()
    frame["games"] = grouped.size()
    frame["fg_pct"] = (frame["fgm"] / frame["fga"].where(frame["fga"] > 0)).fillna(0.0)
    frame["ft_pct"] = (frame["ftm"] / frame["fta"].where(frame["fta"] > 0)).fillna(0.0)
    frame["recent_mp"] = grouped["min"].apply(lambda minutes: float(minutes.tail(RECENT_GAMES).mean()))
    # No position bonus in a value: the 1.12x stays unused.
    frame["positions"] = ""
    return frame.reset_index()


def player_values(logs: pd.DataFrame, rostered: dict[str, str], extra: list[str] | None = None, min_games: int = MIN_GAMES) -> pd.DataFrame:
    """12 z-scores, their sum and a rank for each player, against this league's rostered players.

    ``rostered`` maps player to fantasy team. Ranks count rostered players with
    ``min_games`` or more. ``extra`` names (free agents) are scored against that
    same pool and given the rank they would hold.
    """
    frame = per_game_frame(logs)
    if frame.empty:
        return frame
    frame = frame[frame["games"] >= min_games].copy()
    # Yahoo and ESPN spell some names differently: "Tristan da Silva", "Tristan Da Silva".
    frame["key"] = frame["player_name"].map(name_key)
    teams = {name_key(name): team for name, team in rostered.items()}
    pool = frame[frame["key"].isin(teams)]
    wanted = frame[frame["key"].isin(set(teams) | {name_key(name) for name in extra or []})].copy()
    engine = FantasyMathEngine()
    scored = engine.score_with_baselines(wanted, engine.category_baselines(pool))
    columns = [f"z_{category}" for category in ALL_CATEGORIES]
    scored["total"] = scored[columns].sum(axis=1)
    scored["team"] = scored["key"].map(teams).fillna("")
    league = scored[scored["team"] != ""]
    scored["rank"] = scored["total"].map(lambda value: int((league["total"] > value).sum()) + 1)
    for category in ALL_CATEGORIES:
        column = f"z_{category}"
        scored[f"rank_{category}"] = scored[column].map(lambda value: int((league[column] > value).sum()) + 1)
    return scored.sort_values("total", ascending=False).reset_index(drop=True)


def team_values(values: pd.DataFrame) -> pd.DataFrame:
    """Each team's z-score sum per category, with its rank among the teams in that category."""
    league = values[values["team"] != ""]
    columns = [f"z_{category}" for category in ALL_CATEGORIES]
    teams = league.groupby("team")[columns].sum()
    teams["total"] = teams[columns].sum(axis=1)
    for category in ALL_CATEGORIES:
        teams[f"rank_{category}"] = teams[f"z_{category}"].rank(ascending=False, method="min").astype(int)
    teams["rank"] = teams["total"].rank(ascending=False, method="min").astype(int)
    return teams.sort_values("total", ascending=False)


def fair_chance(chance: float) -> float:
    """The model's chance pulled toward even by the measured overconfidence."""
    if chance <= 0.0 or chance >= 1.0:
        return float(chance)
    odds = math.log(chance / (1.0 - chance))
    return 1.0 / (1.0 + math.exp(-CONFIDENCE_SHRINK * odds))


def category_word(chance: float) -> str:
    """Locked or gone from the raw chance; otherwise a lean word from the fair one."""
    if chance >= LOCKED:
        return "locked yours"
    if chance <= GONE:
        return "gone"
    return lean_word(fair_chance(chance)).replace("his", "theirs")


def day_grid(by_day: dict[str, list[dict]], lineups: dict[str, dict[str, str]]) -> list[dict]:
    """Per day: who has a game, who starts, who sits with a game, and empty seats."""
    rows = []
    for day, entries in by_day.items():
        seated = lineups.get(day, {})
        names = set(seated.values())
        playing = [entry["name"] for entry in entries if entry.get("p", 1.0) > 0]
        rows.append(
            {
                "date": day,
                "plays": len(playing),
                "starts": len(names),
                "sits": [name for name in playing if name not in names],
                "empty": [seat for seat in lineup.SEATS if seat not in seated],
                "seats": dict(seated),
            }
        )
    return rows


def _category_rows(result: dict) -> dict[str, dict]:
    return {row["cat"]: row for row in result["cats"]}


def _players(session, names_out: tuple[str, ...] = (), added: list[tuple[str, str, str]] | None = None) -> list[tuple[str, str, str]]:
    return [row for row in session._my_players() if row[0] not in names_out] + list(added or [])


def _replay(session, week: dict, today: date, players: list[tuple[str, str, str]], plan: dict, runs: int, theirs: dict | None = None) -> dict:
    """The week with these players from today on. Days already played stay as they were."""
    by_day = session._by_day(players, week, today)
    iso = today.isoformat()
    for day in by_day:
        if day < iso and day in plan["mine"]:
            by_day[day] = plan["mine"][day]
    return lineup.plan_week(by_day, theirs if theirs is not None else plan["theirs"], iso, runs=runs, banked=plan.get("banked"))


def _team_games_missed(logs: pd.DataFrame, games: pd.DataFrame) -> int:
    """Games his team has played since his last one."""
    last = games.iloc[-1]
    return int(logs.loc[(logs["team"] == last["team"]) & (logs["date"] > last["date"]), "date"].nunique())


def free_agents(session) -> list[tuple[str, str, str]]:
    """Listed free agents with a line, enough games this season, playing, and not out."""
    data = session.data
    rows = []
    # The table holds each player under more than one spelling.
    for shown, listed in {str(row["player_name"]): row for row in (data.free_agents or {}).values()}.items():
        if str(listed.get("yahoo_status") or "").upper() == "O" or data.line_for(shown) is None:
            continue
        games = data.season_games(shown)
        if len(games) < MIN_GAMES or _team_games_missed(data.logs, games) >= MISSED_GAMES_OUT:
            continue
        rows.append((shown, data.positions_for(shown)[0], data.team_of(shown)))
    return rows


def _with_opponent_adds(session, week: dict, today: date, plan: dict, adds: int = OPPONENT_ADDS) -> dict:
    """The opponent's week if they also pick up the best free agents by this week's games."""
    candidates = free_agents(session)
    scored = []
    for row in candidates:
        games = session._games_for(row[0], row[1], row[2], week, today, score=True)
        scored.append((sum(entry["value"] for entry in games if entry["date"] >= today.isoformat()), row))
    scored.sort(key=lambda item: -item[0])
    extra = session._by_day([row for _, row in scored[:adds]], week, today)
    return {day: [*plan["theirs"].get(day, []), *extra.get(day, [])] for day in plan["theirs"]}


def move_rows(session, week: dict, today: date, plan: dict, protected: set[str], runs: int = MOVE_RUNS) -> list[dict]:
    """Every free agent for every droppable player, shortlisted fast, then replayed in all 12 categories."""
    weights = plan.get("weights")
    if not weights:
        return []
    iso = today.isoformat()
    droppable = [row[0] for row in session._my_players() if row[0] not in protected]
    base_fast = lineup.swing_total(plan["mine"], weights, iso)
    shortlist = []
    for add in free_agents(session):
        for drop in droppable:
            gain = lineup.swing_total(session._by_day(_players(session, (drop,), [add]), week, today, score=False), weights, iso) - base_fast
            shortlist.append((gain, add, drop))
    shortlist.sort(key=lambda item: -item[0])
    base = lineup.plan_week(plan["mine"], plan["theirs"], iso, runs=runs, banked=plan.get("banked"))
    opponent = _with_opponent_adds(session, week, today, plan)
    base_stress = lineup.plan_week(plan["mine"], opponent, iso, runs=runs, banked=plan.get("banked"))
    base_rows = _category_rows(base["result"])
    rows = []
    for _, add, drop in shortlist[:MOVES_SIMULATED]:
        players = _players(session, (drop,), [add])
        replay = _replay(session, week, today, players, plan, runs)
        stress = _replay(session, week, today, players, plan, runs, theirs=opponent)
        changed = _category_rows(replay["result"])
        rows.append(
            {
                "add": add[0],
                "add_team": add[2],
                "positions": add[1],
                "drop": drop,
                "cats": replay["result"]["expected"] - base["result"]["expected"],
                "cats_if_opponent_adds": stress["result"]["expected"] - base_stress["result"]["expected"],
                "by_category": {category: changed[category]["win"] - base_rows[category]["win"] for category in ALL_CATEGORIES},
                "starts": sum(len(seats) for seats in replay["lineups"].values()) - sum(len(seats) for seats in base["lineups"].values()),
            }
        )
    rows.sort(key=lambda row: -row["cats"])
    return rows[:MOVES_SHOWN]


def long_run(session, weeks: list[dict], move: dict, runs: int = MOVE_RUNS) -> list[dict]:
    """The same move in the coming weeks, each against that week's opponent."""
    rows = []
    add = (move["add"], move["positions"], move["add_team"])
    for week in weeks:
        start = week["start"]
        today = start if isinstance(start, date) else date.fromisoformat(str(start))
        plan = session.week_plan(week, today)
        if not plan.get("result"):
            continue
        base = lineup.plan_week(plan["mine"], plan["theirs"], today.isoformat(), runs=runs)
        replay = _replay(session, week, today, _players(session, (move["drop"],), [add]), plan, runs)
        rows.append({"week": week["week"], "opponent": plan.get("opponent"), "cats": replay["result"]["expected"] - base["result"]["expected"]})
    return rows


def week_report(session, week: dict, today: date, rostered: dict[str, str], later_weeks: list[dict] | None = None, protected: set[str] | None = None) -> dict:
    """Everything the morning report shows, as data."""
    data = session.data
    plan = session.week_plan(week, today)
    names = [row[0] for row in session._my_players()]
    agents = [row[0] for row in free_agents(session)]
    values = player_values(data.logs, rostered, extra=agents)
    report: dict = {
        "date": today.isoformat(),
        "week": week["week"],
        "opponent": plan.get("opponent"),
        "values": values,
        "team_values": team_values(values),
        "roster": names,
        "team": session.team,
        "grid": day_grid(plan["mine"], plan["lineups"]),
        "banked": plan.get("banked"),
    }
    if not plan.get("result"):
        report.update(categories=[], moves=[])
        return report
    report["their_grid"] = day_grid(plan["theirs"], plan.get("their_lineups") or {})
    opponent = _with_opponent_adds(session, week, today, plan)
    stressed = lineup.plan_week(plan["mine"], opponent, today.isoformat(), banked=plan.get("banked"))
    after = _category_rows(stressed["result"])
    report["categories"] = [
        {
            "cat": row["cat"],
            "mine": row["mine"],
            "theirs": row["theirs"],
            "chance": row["win"],
            "fair": fair_chance(row["win"]),
            "word": category_word(row["win"]),
            "word_if_opponent_adds": category_word(after[row["cat"]]["win"]),
        }
        for row in plan["result"]["cats"]
    ]
    moves = move_rows(session, week, today, plan, protected if protected is not None else set(session.protected))
    for move in moves[:LONG_RUN_MOVES]:
        move["long_run"] = long_run(session, (later_weeks or [])[:LONG_RUN_WEEKS], move)
    report["moves"] = moves
    return report


def record_forecast(path: Path, report: dict) -> None:
    """Append this morning's category chances, once a day, so they can be graded."""
    if not report.get("categories"):
        return
    fresh = pd.DataFrame(
        [
            {"made_on": report["date"], "week": report["week"], "opponent": report["opponent"], "cat": row["cat"], "chance": round(row["chance"], 4), "fair": round(row["fair"], 4)}
            for row in report["categories"]
        ],
        columns=list(FORECAST_COLUMNS),
    )
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=list(FORECAST_COLUMNS))
    old = old[~((old["made_on"] == report["date"]) & (old["week"] == report["week"]))]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([frame for frame in (old, fresh) if len(frame)], ignore_index=True).to_csv(path, index=False)


def category_results(mine: np.ndarray, theirs: np.ndarray) -> dict[str, float]:
    """1 won, 0.5 tied, 0 lost, per category, from two final ``matchup.STATS`` vectors."""
    my_values = matchup.category_values(mine[None, :])
    their_values = matchup.category_values(theirs[None, :])
    results = {}
    for category in ALL_CATEGORIES:
        sign = -1.0 if category in NEGATIVE_CATEGORIES else 1.0
        gap = sign * float(my_values[category][0] - their_values[category][0])
        results[category] = 1.0 if gap > 1e-9 else 0.5 if gap >= -1e-9 else 0.0
    return results


def grade_forecasts(forecasts: pd.DataFrame, finals: dict[int, dict[str, float]]) -> pd.DataFrame:
    """Each finished week's first forecast against what happened. Lower Brier is better; a coin is 0.25."""
    rows = []
    for week, results in sorted(finals.items()):
        made = forecasts[forecasts["week"] == week]
        if made.empty:
            continue
        first = made[made["made_on"] == made["made_on"].min()]
        said = first.set_index("cat")
        cats = [category for category in ALL_CATEGORIES if category in said.index and category in results]
        fair = np.array([said.loc[category, "fair"] for category in cats], dtype=float)
        real = np.array([results[category] for category in cats], dtype=float)
        rows.append({"week": int(week), "made_on": str(first["made_on"].iloc[0]), "expected": float(fair.sum()), "won": float(real.sum()), "brier": float(((fair - real) ** 2).mean())})
    return pd.DataFrame(rows)


def _signed(value: float) -> str:
    return f"{value:+.1f}"


def _stat(category: str, value: float) -> str:
    return f"{value:.3f}".lstrip("0") if category.endswith("%") else f"{value:.0f}"


def _player_table(values: pd.DataFrame, names: list[str]) -> list[str]:
    head = "| Rank | Player | " + " | ".join(ALL_CATEGORIES) + " | Sum |"
    lines = [head, "|---:|---|" + "---:|" * (len(ALL_CATEGORIES) + 1)]
    keys = {name_key(name) for name in names}
    for row in values[values["key"].isin(keys)].to_dict("records"):
        cells = [f"{_signed(row[f'z_{category}'])} ({row[f'rank_{category}']})" for category in ALL_CATEGORIES]
        lines.append(f"| {row['rank']} | {row['player_name']} | " + " | ".join(cells) + f" | **{_signed(row['total'])}** |")
    return lines


def render(report: dict, flags: list[str] | None = None, grades: pd.DataFrame | None = None) -> str:
    """The morning report as Markdown. Facts first, words for the odds, no headline win chance."""
    lines = [f"# Week {report['week']} vs {report.get('opponent') or 'unknown'}, {report['date']}", ""]
    banked = report.get("banked")
    lines.append(f"Totals from Yahoo through {banked['through']}." if banked else "No Yahoo totals on file for this week yet.")
    lines += ["", "## Games and seats", "", "| Day | Play | Start | Sit with a game | Empty seats | Their starts |", "|---|---:|---:|---|---|---:|"]
    theirs = {row["date"]: row for row in report.get("their_grid", [])}
    for row in report["grid"]:
        lines.append(f"| {row['date']} | {row['plays']} | {row['starts']} | {', '.join(row['sits']) or '-'} | {', '.join(row['empty']) or '-'} | {theirs.get(row['date'], {}).get('starts', '-')} |")
    if report.get("categories"):
        lines += ["", "## All 12 categories", "", "| Category | You | Them | Outlook | If they make 2 adds |", "|---|---:|---:|---|---|"]
        for row in report["categories"]:
            lines.append(f"| {row['cat']} | {_stat(row['cat'], row['mine'])} | {_stat(row['cat'], row['theirs'])} | {row['word']} | {row['word_if_opponent_adds']} |")
    today_row = next((row for row in report["grid"] if row["date"] == report["date"]), None)
    if today_row:
        seats = ", ".join(f"{seat} {today_row['seats'][seat]}" for seat in lineup.SEATS if seat in today_row["seats"]) or "nobody plays"
        lines += ["", "## Today's five", "", seats + ".", ""]
        lines += ["Each game is scored by how much it moves the categories still in play, not by points."]
    lines += ["", "## Your players, 12-category value this season", "", "Value per game, with the league rank in brackets. The sum is all 12 added together, equally.", ""]
    lines += _player_table(report["values"], report["roster"])
    teams = report.get("team_values")
    me = report.get("team")
    if teams is not None and me in teams.index:
        row = teams.loc[me]
        lines += ["", f"**Team rank by category, of {len(teams)}:** " + ", ".join(f"{category} {int(row[f'rank_{category}'])}" for category in ALL_CATEGORIES) + f". Overall {int(row['rank'])}."]
    if flags:
        lines += ["", "## Watch", ""] + [f"- {flag}" for flag in flags]
    if report.get("moves"):
        lines += ["", "## Best adds and drops, all 12 categories", "", "Change in the chance of each category, in points. Small changes are inside the model's error.", ""]
        for move in report["moves"]:
            changes = sorted(move["by_category"].items(), key=lambda item: -item[1])
            gains = ", ".join(f"{category} {value * 100:+.0f}" for category, value in changes if value >= 0.02) or "nothing clear"
            costs = ", ".join(f"{category} {value * 100:+.0f}" for category, value in changes[::-1] if value <= -0.02) or "nothing clear"
            later = ", ".join(f"week {row['week']} {_signed(row['cats'])}" for row in move.get("long_run", [])) or "not run"
            table = report["values"].set_index("key")
            ranks = " / ".join(f"#{int(table.loc[name_key(name), 'rank'])}" if name_key(name) in table.index else "unranked" for name in (move["drop"], move["add"]))
            lines.append(f"- **{move['drop']} → {move['add']}** ({move['add_team']}, {move['positions']}, league ranks {ranks}): {move['cats']:+.2f} categories ({move['cats_if_opponent_adds']:+.2f} if they make 2 adds), {move['starts']:+d} starts. Gains {gains}. Costs {costs}. Later: {later}.")
    if grades is not None and len(grades):
        lines += ["", "## How the forecasts did", "", "| Week | Forecast on | Expected wins | Real wins | Error (a coin is .25) |", "|---:|---|---:|---:|---:|"]
        for row in grades.to_dict("records"):
            lines.append(f"| {row['week']} | {row['made_on']} | {row['expected']:.1f} | {row['won']:.1f} | {row['brier']:.3f} |")
    return "\n".join(lines) + "\n"


def watch_flags(session, values: pd.DataFrame, names: list[str], notes: dict[str, dict], today: date) -> list[str]:
    """Minutes moving, injuries, whether he started last time, tonight's betting lines."""
    data = session.data
    flags = []
    table = values.set_index("key")
    for name in [*names, *(row["player"]["player_name"] for row in session.il)]:
        if name_key(name) in table.index:
            row = table.loc[name_key(name)]
            if abs(row["recent_mp"] - row["mp"]) >= MINUTE_SWING:
                flags.append(f"{name}: minutes {row['mp']:.1f} this season, {row['recent_mp']:.1f} over his last {RECENT_GAMES}.")
        injury = data.injury(name)
        if injury:
            flags.append(f"{name}: {injury.get('status')}, ESPN return {injury.get('return_date') or 'unknown'}.")
        games = data.season_games(name)
        if len(games):
            started = notes.get(str(games.iloc[-1]["game_id"]), {}).get("starters", {}).get(name_key(name))
            if started is False:
                flags.append(f"{name}: came off the bench last game.")
    for game in data.schedule[data.schedule["date"].astype(str) == today.isoformat()].to_dict("records"):
        line = notes.get(str(game["game_id"]), {}).get("line")
        if line:
            flags.append(f"{game['away']} at {game['home']}: {line['details']}, total {line['total']}.")
    return flags
