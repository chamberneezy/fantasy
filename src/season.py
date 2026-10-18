"""In-season pad: daily lineup, 4 adds/week. This Yahoo league has no IL."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

import lineup
import matchup
import schedule as slate
import season_data
from coach import match_player
from availability import attach_games_forecast, name_key
from draft_room import (
    FORECAST,
    PROJECTIONS,
    ROSTER_SIZE,
    SLOTS,
    eligible_for_slot,
    first_open_slot,
    player_positions,
    _attach_double_doubles,
)
from data_loader import ProjectionLoader
from math_engine import ALL_CATEGORIES, FantasyMathEngine

ADDS_PER_WEEK = 4
IL_SLOTS = 0
STREAM_LISTED_CAP = 8
OPENING_ADDS_USED = 1
PROTECTED = frozenset({"Mario Hezonja"})
SEASON_PATH = Path(__file__).resolve().parents[1] / "data" / "season_session.json"

OPENING_ROSTER: tuple[tuple[str, str], ...] = (
    ("PG", "Keyonte George"),
    ("SG", "Kawhi Leonard"),
    ("SF", "Jalen Williams"),
    ("PF", "John Collins"),
    ("C", "Nikola Jokić"),
    ("BN1", "Mario Hezonja"),
    ("BN2", "Jrue Holiday"),
    ("BN3", "Neemias Queta"),
    ("BN4", "Dillon Brooks"),
    ("BN5", "Tre Jones"),
)

EXTRA_PLAYERS: tuple[dict, ...] = (
    {
        "player_name": "Mario Hezonja",
        "positions": "SF/PF",
        "team": "CLE",
        "total_value": 0.0,
        "auction_value": 1,
        "yahoo_listed": None,
        "predicted_games": None,
        "unlisted": True,
        "z": {category: 0.0 for category in ALL_CATEGORIES},
    },
)

HOLE_HELP = ("TO", "PF", "BLK")
# A game is said to cost a category only past this much of a category-win.
COST_SHOWN = -0.02
# Free agents scored in full for an add, and how many of those are shown.
STREAM_SHORTLIST = 25
STREAM_SHOWN = 5
# A free agent needs this many NBA games on file to be offered. A hot week or a
# rookie translation is not enough to spend one of four adds on.
STREAM_MIN_GAMES = 20
# Seats that can be given up for a streamer: the lowest season lines, never a protected name.
STREAM_DROPS = 3
# Yahoo files a game under its US Eastern date.
LEAGUE_ZONE = ZoneInfo("America/New_York")
LINE_FIELDS = ("mp", "pts", "reb", "ast", "stl", "blk", "fg3m", "to", "pf", "fgm", "fga", "ftm", "fta", "dd")


def league_today() -> date:
    return datetime.now(LEAGUE_ZONE).date()


def _shown_line(line: dict | None, base: dict | None = None) -> dict | None:
    """The line as the page prints it. ``base`` is the same line before tonight's context."""
    if line is None:
        return None
    shown = {field: round(float(line[field]), 2 if field == "dd" else 1) for field in LINE_FIELDS}
    shown["fg_pct"] = round(float(line["fg_pct"]), 3)
    shown["ft_pct"] = round(float(line["ft_pct"]), 3)
    for field in ("value", "z", "basis", "new_team", "games"):
        shown[field] = line[field]
    if base and base["pts"]:
        shown["context"] = round(float(line["pts"]) / float(base["pts"]) - 1.0, 3)
    return shown


def _blank_z() -> dict[str, float]:
    return {category: 0.0 for category in ALL_CATEGORIES}


def _enrich(players: list[dict]) -> dict[str, dict]:
    engine = FantasyMathEngine()
    loaded = _attach_double_doubles(ProjectionLoader(PROJECTIONS).load())
    engine.load_data(loaded)
    ranked = engine.get_ranked_players()
    if FORECAST.exists():
        import pandas as pd

        ranked = attach_games_forecast(ranked, pd.read_csv(FORECAST))
    zmap: dict[str, dict] = {}
    for _, row in ranked.iterrows():
        zmap[str(row["player_name"])] = {
            category: round(float(row[f"z_{category}"]), 3) for category in ALL_CATEGORIES
        }
    by_name: dict[str, dict] = {}
    for player in players:
        item = dict(player)
        item["z"] = zmap.get(item["player_name"], item.get("z") or _blank_z())
        item["unlisted"] = bool(item.get("unlisted"))
        by_name[item["player_name"]] = item
    for extra in EXTRA_PLAYERS:
        if extra["player_name"] not in by_name:
            by_name[extra["player_name"]] = dict(extra)
            by_name[extra["player_name"]]["z"] = dict(extra["z"])
    return by_name


def team_tape(roster: list[dict]) -> dict[str, float]:
    tape = _blank_z()
    for seat in roster:
        player = seat.get("player") or {}
        z_scores = player.get("z") or _blank_z()
        for category in ALL_CATEGORIES:
            tape[category] += float(z_scores.get(category) or 0)
    return {category: round(tape[category], 2) for category in ALL_CATEGORIES}


def cat_call(value: float) -> str:
    if value < 0:
        return "hole"
    if value >= 4:
        return "win"
    return "ok"


class SeasonSession:
    mode = "season"

    def __init__(self, players: list[dict], data: season_data.SeasonData | None = None) -> None:
        self.pool = _enrich(players)
        self._data = data
        self.status: dict[str, str] = {}
        self._entry_cache: dict[tuple, list[dict]] = {}
        self._plan_cache: dict = {}
        self.roster: list[dict] = []
        self.il: list[dict] = []
        self.adds_used = OPENING_ADDS_USED
        self.week = 1
        self._seed()

    def _lookup(self, name: str) -> dict:
        try:
            return dict(match_player(name, list(self.pool.values())))
        except ValueError:
            extra = next(
                (dict(item) for item in EXTRA_PLAYERS if name_key(item["player_name"]) == name_key(name)),
                None,
            )
            if extra:
                return extra
            raise

    def _seed(self) -> None:
        self.roster = []
        filled: set[str] = set()
        for slot_id, name in OPENING_ROSTER:
            player = self._lookup(name)
            self.roster.append({"slot_id": slot_id, "player": player})
            filled.add(slot_id)
        if len(self.roster) != ROSTER_SIZE:
            raise ValueError("Opening roster must fill 10 seats.")

    @property
    def data(self) -> season_data.SeasonData:
        return self._data or season_data.load()

    def _team(self, player: dict) -> str:
        return self.data.team_of(player["player_name"], player.get("team"))

    def _positions(self, player: dict) -> str:
        return self.data.positions_for(player["player_name"], player.get("positions"))[0]

    def _games_for(self, name: str, positions: str, team: str, week: dict, today: date, score: bool = True) -> list[dict]:
        """One entry per game this player has in the week, ready to seat and simulate.

        Days before ``today`` are banked: what he really did, or nothing if he sat.
        A player with no line and no banked game has no entry.
        """
        key = (name, positions, team, week["week"], today, self.status.get(name), score, id(self.data))
        if key in self._entry_cache:
            return self._entry_cache[key]
        data = self.data
        entries = []
        for game in slate.team_games(data.schedule, team, week["start"], week["end"]):
            entry = {"name": name, "date": game["date"], "positions": player_positions(positions), "game": game}
            if game["date"] < today.isoformat():
                actual = data.actual(name, game["date"])
                entry.update(
                    fixed=actual if actual is not None else np.zeros(len(matchup.STATS)),
                    mean=actual if actual is not None else np.zeros(len(matchup.STATS)),
                    p=1.0,
                    why="played" if actual is not None else "did not play",
                    line=None,
                    value=float(actual[matchup.AT["mp"]]) if actual is not None else 0.0,
                )
            else:
                line = data.game_line(name, game, score=score)
                if line is None:
                    continue
                chance, why = data.play_chance(name, game, self.status.get(name))
                entry.update(
                    mean=matchup.line_vector(line),
                    hist=data.history(name),
                    p=chance,
                    why=why,
                    line=line,
                    value=float(line.get("value", 0.0)) * chance,
                )
            entries.append(entry)
        self._entry_cache[key] = entries
        return entries

    def _by_day(self, players: list[tuple[str, str, str]], week: dict, today: date, score: bool = True) -> dict[str, list[dict]]:
        by_day: dict[str, list[dict]] = {day.isoformat(): [] for day in slate.week_days(week)}
        for name, positions, team in players:
            for entry in self._games_for(name, positions, team, week, today, score):
                by_day[entry["date"]].append(entry)
        return by_day

    def _my_players(self) -> list[tuple[str, str, str]]:
        return [
            (seat["player"]["player_name"], self._positions(seat["player"]), self._team(seat["player"]))
            for seat in self.roster
        ]

    def week_plan(self, week: dict, today: date) -> dict:
        """My five for each day of the week, and the matchup if the opponent is known."""
        key = (week["week"], today, tuple(self._my_players()), tuple(sorted(self.status.items())), id(self.data))
        if self._plan_cache.get("key") == key:
            return self._plan_cache["plan"]
        data = self.data
        mine = self._by_day(self._my_players(), week, today)
        opponent = data.matchups.get(week["week"])
        their_names = data.team_names(opponent) if opponent else []
        if their_names:
            theirs = self._by_day(
                [(name, data.positions_for(name)[0], data.team_of(name)) for name in their_names], week, today
            )
            plan = lineup.plan_week(mine, theirs, today.isoformat())
            plan["opponent"] = opponent
            plan["theirs"] = theirs
        else:
            plan = {"lineups": {day: lineup.by_value(entries) for day, entries in mine.items()}, "result": None, "weights": None}
        plan["mine"] = mine
        self._plan_cache = {"key": key, "plan": plan}
        return plan

    def calendar(self, day: date | None = None, today: date | None = None) -> dict | None:
        """This week's grid and the chosen day's card. ``None`` until the schedule is pulled."""
        data = self.data
        if not data.weeks:
            return None
        now = today or league_today()
        first = data.weeks[0]["start"]
        last = data.weeks[-1]["end"]
        chosen = min(max(day or now, first), last)
        week = slate.week_for(chosen, data.weeks)
        seats = [
            {"player_name": seat["player"]["player_name"], "team": self._team(seat["player"])}
            for seat in self.roster
        ]
        grid = slate.week_grid(data.schedule, seats, week, now)
        plan = self.week_plan(week, now)
        for row in grid["rows"]:
            for cell in row["cells"]:
                if cell:
                    seated = plan["lineups"].get(cell["date"], {})
                    cell["seat"] = next((seat for seat, name in seated.items() if name == row["player_name"]), None)
        position = data.weeks.index(week)
        grid["prev"] = data.weeks[position - 1]["start"].isoformat() if position else None
        grid["next"] = data.weeks[position + 1]["start"].isoformat() if position + 1 < len(data.weeks) else None
        grid["day"] = self._day_card(chosen, grid, plan)
        grid["today"] = now.isoformat()
        grid["matchup"] = self._matchup_card(plan)
        grid["plans"] = self.stream_plans(week, now, plan) if week is slate.week_for(now, data.weeks) else []
        return grid

    def _day_card(self, chosen: date, grid: dict, plan: dict) -> dict:
        iso = chosen.isoformat()
        index = next(i for i, day in enumerate(grid["days"]) if day["date"] == iso)
        entries = {entry["name"]: entry for entry in plan["mine"].get(iso, [])}
        seated = {name: seat for seat, name in plan["lineups"].get(iso, {}).items()}
        weights = plan.get("weights")
        playing = []
        off = []
        for row in grid["rows"]:
            game = row["cells"][index]
            if not game:
                off.append(row["player_name"])
                continue
            name = row["player_name"]
            entry = entries.get(name)
            swing = matchup.game_swing(entry, weights) if entry and weights and entry.get("line") else None
            playing.append(
                {
                    "player_name": name,
                    "positions": self.data.positions_for(name)[0],
                    "team": row["team"],
                    **{field: game[field] for field in ("opp", "home", "tip_utc", "b2b")},
                    "line": _shown_line(entry["line"], self.data.line_for(name)) if entry and entry.get("line") else None,
                    "seat": seated.get(name),
                    "chance": round(entry["p"], 2) if entry else None,
                    "why": entry["why"] if entry else "",
                    "status": self.status.get(name),
                    "swing": round(sum(swing.values()), 3) if swing else None,
                    "costs": sorted((cat for cat, value in swing.items() if value < COST_SHOWN), key=lambda cat: swing[cat]) if swing else [],
                }
            )
        order = {seat: number for number, seat in enumerate(lineup.SEATS)}
        playing.sort(key=lambda row: (row["seat"] is None, order.get(row["seat"], 9), -(row["swing"] or 0)))
        return {**grid["days"][index], "playing": playing, "off": off, "matchup_aware": bool(weights)}

    def _matchup_card(self, plan: dict) -> dict | None:
        result = plan.get("result")
        if not result:
            return None
        their_games: dict[str, int] = {}
        for entry in plan["their_games"]:
            their_games[entry["name"]] = their_games.get(entry["name"], 0) + 1
        no_line = [
            name
            for name in self.data.team_names(plan["opponent"])
            if self.data.line_for(name) is None
        ]
        return {
            "opponent": plan["opponent"],
            "cats": [
                {
                    "cat": row["cat"],
                    "mine": round(row["mine"], 3 if "%" in row["cat"] else 1),
                    "theirs": round(row["theirs"], 3 if "%" in row["cat"] else 1),
                    "win": round(row["win"] + 0.5 * row["tie"], 2),
                }
                for row in result["cats"]
            ],
            "expected": round(result["expected"], 1),
            "win": round(result["win"], 2),
            "tie": round(result["tie"], 2),
            "lose": round(result["lose"], 2),
            "my_starts": sum(len(seats) for seats in plan["lineups"].values()),
            "their_starts": len(plan["their_games"]),
            "their_no_line": no_line,
        }

    def stream_plans(self, week: dict, today: date, plan: dict) -> list[dict]:
        """Add-and-drop pairs that win the most extra categories this week.

        Only names nobody in the league owns. Only the pad's usual drop
        candidates give up a seat, so a star on a two-game week is never offered.
        """
        weights = plan.get("weights")
        if not weights or self.adds_used >= ADDS_PER_WEEK:
            return []
        data = self.data
        iso = today.isoformat()
        mine = self._my_players()
        owned = self.owned_names()
        base = lineup.swing_total(plan["mine"], weights, iso)
        free = []
        for player in self.pool.values():
            name = player["player_name"]
            if name in owned or data.rostered_by(name) or "average" in name.lower():
                continue
            if data.line_for(name) is None or data.games_on_file(name) < STREAM_MIN_GAMES:
                continue
            positions, verified = data.positions_for(name, player.get("positions"))
            games = [
                entry
                for entry in self._games_for(name, positions, self._team(player), week, today, score=False)
                if entry["date"] >= iso
            ]
            quick = sum(max(0.0, sum(matchup.game_swing(entry, weights).values())) for entry in games)
            if quick > 0:
                free.append((quick, name, positions, self._team(player), verified, len(games)))
        free.sort(reverse=True)
        droppable = self._droppable()
        plans = []
        for _, name, positions, team, verified, games in free[:STREAM_SHORTLIST]:
            best = None
            for drop in droppable:
                players = [row for row in mine if row[0] != drop] + [(name, positions, team)]
                gain = lineup.swing_total(self._by_day(players, week, today, score=False), weights, iso) - base
                if best is None or gain > best[0]:
                    best = (gain, drop)
            if best and best[0] > 0:
                plans.append(
                    {
                        "add": name,
                        "drop": best[1],
                        "gain": round(float(best[0]), 2),
                        "positions": positions,
                        "verified": verified,
                        "team": team,
                        "games": games,
                    }
                )
        plans.sort(key=lambda row: -row["gain"])
        return [self._confirm(row, week, today, plan) for row in plans[:STREAM_SHOWN]]

    def _droppable(self) -> list[str]:
        valued = []
        for seat in self.roster:
            name = seat["player"]["player_name"]
            line = self.data.line_for(name)
            if name not in PROTECTED and line is not None:
                valued.append((line["value"], name))
        return [name for _, name in sorted(valued)[:STREAM_DROPS]]

    def _confirm(self, row: dict, week: dict, today: date, plan: dict) -> dict:
        """Replay the week with the swap made, so the gain shown is simulated, not estimated."""
        players = [seat for seat in self._my_players() if seat[0] != row["drop"]]
        players.append((row["add"], row["positions"], row["team"]))
        swapped = lineup.plan_week(self._by_day(players, week, today), plan["theirs"], today.isoformat())["result"]
        before = plan["result"]
        add_line = self.data.line_for(row["add"])
        drop_line = self.data.line_for(row["drop"])
        return {
            **row,
            "cats": round(swapped["expected"] - before["expected"], 2),
            "win": round(swapped["win"] - before["win"], 2),
            "add_value": add_line["value"] if add_line else None,
            "drop_value": drop_line["value"] if drop_line else None,
            "basis": add_line["basis"] if add_line else "",
        }

    def set_status(self, query: str, status: str) -> None:
        """Mark anyone out or in for the pad's sums, or clear the mark. Beats the injury report."""
        if status not in ("out", "in", "clear"):
            raise ValueError("Status is out, in or clear.")
        known = list(self.pool.values()) + [{"player_name": name} for name in self.data.rosters["player_name"]]
        name = match_player(query, known)["player_name"]
        if status == "clear":
            self.status.pop(name, None)
        else:
            self.status[name] = status

    def owned_names(self) -> set[str]:
        names = {seat["player"]["player_name"] for seat in self.roster if seat.get("player")}
        names.update(item["player"]["player_name"] for item in self.il if item.get("player"))
        return names

    def tape(self) -> dict[str, float]:
        return team_tape(self.roster)

    def holes(self) -> list[str]:
        tape = self.tape()
        return [category for category in HOLE_HELP if tape[category] < 4]

    def drops(self) -> list[dict]:
        ranked = []
        for seat in self.roster:
            player = seat["player"]
            games = player.get("predicted_games")
            ranked.append(
                {
                    "player_name": player["player_name"],
                    "slot_id": seat["slot_id"],
                    "games": games,
                    "unlisted": bool(player.get("unlisted") or player["player_name"] == "Mario Hezonja"),
                    "total_value": float(player.get("total_value") or 0),
                    "protected": player["player_name"] in PROTECTED,
                }
            )
        ranked = [row for row in ranked if not row["protected"]]
        ranked.sort(
            key=lambda row: (
                0 if row["unlisted"] else 1,
                0 if row["games"] is None else 1,
                row["games"] if row["games"] is not None else 0,
                row["total_value"],
            )
        )
        return ranked[:4]

    def streamers(self) -> list[dict]:
        owned = self.owned_names()
        holes = self.holes()
        data = self.data
        now = league_today()
        week = slate.week_for(now, data.weeks)
        ranked = []
        for player in self.pool.values():
            name = player["player_name"]
            if name in owned or data.rostered_by(name):
                continue
            if "average" in name.lower():
                continue
            listed = player.get("yahoo_listed")
            if listed not in (None, "") and int(listed) > STREAM_LISTED_CAP:
                continue
            games = int(player.get("predicted_games") or 0)
            if games and games < 55:
                continue
            z_scores = player.get("z") or _blank_z()
            help_score = sum(float(z_scores.get(category) or 0) for category in holes) if holes else float(
                player.get("total_value") or 0
            )
            why = []
            if "TO" in holes and float(z_scores.get("TO") or 0) > 0:
                why.append("low TO")
            if "PF" in holes and float(z_scores.get("PF") or 0) > 0:
                why.append("low PF")
            if "BLK" in holes and float(z_scores.get("BLK") or 0) > 0.4:
                why.append("BLK")
            if games:
                why.append(f"{games} g")
            if week:
                left = len(slate.team_games(data.schedule, self._team(player), max(now, week["start"]), week["end"]))
                why.append(f"{left} this wk")
            ranked.append(
                {
                    "player_name": name,
                    "positions": player.get("positions") or "",
                    "listed": 1 if listed in (None, "") else int(listed),
                    "games": games or None,
                    "help": round(help_score, 2),
                    "why": " · ".join(why) or "depth",
                }
            )
        ranked.sort(key=lambda row: (-row["help"], -(row["games"] or 0)))
        return ranked[:8]

    def add(self, query: str) -> None:
        if self.adds_used >= ADDS_PER_WEEK:
            raise ValueError(f"You already used {ADDS_PER_WEEK} adds this week.")
        player = self._lookup(query)
        name = player["player_name"]
        if name in self.owned_names():
            raise ValueError(f"{name} is already on your roster.")
        slot_id = self._open_seat(player.get("positions"))
        self.roster.append({"slot_id": slot_id, "player": player})
        self.adds_used += 1

    def _fill_starters(self) -> None:
        for slot_id, label in SLOTS:
            occupied = {seat["slot_id"] for seat in self.roster}
            if slot_id in occupied or label == "BN":
                continue
            for seat in self.roster:
                if not str(seat["slot_id"]).startswith("BN"):
                    continue
                if eligible_for_slot(seat["player"].get("positions"), label):
                    seat["slot_id"] = slot_id
                    break

    def _open_seat(self, positions: object) -> str:
        filled = {seat["slot_id"] for seat in self.roster}
        try:
            return first_open_slot(positions, filled)
        except ValueError:
            empty_bn = [slot_id for slot_id, label in SLOTS if slot_id not in filled and label == "BN"]
            if empty_bn:
                return empty_bn[0]
            raise ValueError("No empty eligible seat. Drop a bench name first.") from None

    def drop(self, query: str) -> None:
        player = match_player(query, [seat["player"] for seat in self.roster] + [item["player"] for item in self.il])
        name = player["player_name"]
        if name in PROTECTED:
            raise ValueError("Hezonja stays.")
        self.roster = [seat for seat in self.roster if seat["player"]["player_name"] != name]
        self.il = [item for item in self.il if item["player"]["player_name"] != name]
        self._fill_starters()
        if len(self.roster) < 1:
            raise ValueError("Keep at least one player.")

    def to_il(self, query: str) -> None:
        if IL_SLOTS <= 0:
            raise ValueError("This league has no IL. Drop someone to add a replacement.")
        player = match_player(query, [seat["player"] for seat in self.roster])
        name = player["player_name"]
        seat = next(item for item in self.roster if item["player"]["player_name"] == name)
        self.roster = [item for item in self.roster if item["player"]["player_name"] != name]
        self.il.append({"slot_id": "IL" if not self.il else "IL+", "player": seat["player"]})
        self._fill_starters()

    def from_il(self, query: str) -> None:
        player = match_player(query, [item["player"] for item in self.il])
        name = player["player_name"]
        slot_id = self._open_seat(player.get("positions"))
        held = next(item for item in self.il if item["player"]["player_name"] == name)
        self.il = [item for item in self.il if item["player"]["player_name"] != name]
        self.roster.append({"slot_id": slot_id, "player": held["player"]})

    def new_week(self) -> None:
        self.week += 1
        self.adds_used = 0

    def state(self, day: date | None = None) -> dict:
        tape = self.tape()
        data = self.data
        return {
            "calendar": self.calendar(day),
            "feed": {
                "fetched_at": data.meta.get("fetched_at"),
                "errors": data.meta.get("errors") or {},
                "logs_through": data.logs_through(),
                "games_logged": int(len(data.logs)),
            },
            "started": True,
            "mode": self.mode,
            "week": self.week,
            "adds_used": self.adds_used,
            "adds_left": ADDS_PER_WEEK - self.adds_used,
            "adds_per_week": ADDS_PER_WEEK,
            "categories": list(ALL_CATEGORIES),
            "tape": tape,
            "calls": {category: cat_call(tape[category]) for category in ALL_CATEGORIES},
            "roster": [
                {
                    "slot_id": seat["slot_id"],
                    "label": dict(SLOTS).get(seat["slot_id"], seat["slot_id"]),
                    "player_name": seat["player"]["player_name"],
                    "positions": seat["player"].get("positions") or "",
                    "team": self._team(seat["player"]),
                    "games": seat["player"].get("predicted_games"),
                    "unlisted": bool(seat["player"].get("unlisted")),
                    "protected": seat["player"]["player_name"] in PROTECTED,
                }
                for seat in self.roster
            ],
            "il": [
                {
                    "slot_id": item["slot_id"],
                    "player_name": item["player"]["player_name"],
                    "positions": item["player"].get("positions") or "",
                    "games": item["player"].get("predicted_games"),
                }
                for item in self.il
            ],
            "drops": self.drops(),
            "streamers": self.streamers(),
            "il_enabled": IL_SLOTS > 0,
            "note": "Daily – Today. 4 adds/week. No waivers. No IL. Type a FA, then Add. Hezonja stays.",
        }


def idle_season() -> dict:
    return {
        "started": False,
        "mode": "season",
        "categories": list(ALL_CATEGORIES),
        "adds_per_week": ADDS_PER_WEEK,
        "il_enabled": IL_SLOTS > 0,
    }


def save_season(session: SeasonSession, path: Path | None = None) -> None:
    target = path or SEASON_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "season",
        "week": session.week,
        "adds_used": session.adds_used,
        "roster": [[seat["slot_id"], seat["player"]["player_name"]] for seat in session.roster],
        "il": [[item["slot_id"], item["player"]["player_name"]] for item in session.il],
        "status": dict(session.status),
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_season(players: list[dict], path: Path | None = None) -> SeasonSession:
    target = path or SEASON_PATH
    session = SeasonSession(players)
    if not target.exists():
        return session
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("mode") != "season":
        return session
    session.week = int(payload.get("week") or 1)
    session.adds_used = int(payload.get("adds_used") or 0)
    roster = payload.get("roster") or []
    if roster:
        session.roster = []
        for slot_id, name in roster:
            session.roster.append({"slot_id": slot_id, "player": session._lookup(name)})
    session.status = {str(name): str(mark) for name, mark in (payload.get("status") or {}).items()}
    session.il = []
    for slot_id, name in payload.get("il") or []:
        session.il.append({"slot_id": slot_id, "player": session._lookup(name)})
    return session


def reset_season(path: Path | None = None) -> None:
    target = path or SEASON_PATH
    if target.exists():
        target.unlink()
