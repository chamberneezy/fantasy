"""Grade the category forecasts on past seasons: predict every Monday, compare with the week that happened.

The test league: 16 teams of 10, snake-drafted before the season from the previous season's
per-game value, kept all season (injuries and rest then cost games, as in a real league).
Each day the five best projected players with a game sit; a seated player who does not play
scores nothing. The same rule makes the forecast and the real week, so only the forecast is graded.

Forecast inputs are what the pad has on a Monday morning: the previous season's per-game line
as anchor, this season's games before Monday, the last 60 games for the spread. A player who
missed his team's last two games stands in for "on the injury report".

Model variants (``Variant``):
- ``plays_always``: today's pad. Healthy players play every game; every game is drawn on its own.
- ``misses``: a healthy player can miss a game, and misses come in runs (a two-state chain
  measured on a fitting season).
- ``week_form``: each player's week also shares one form factor (role, minutes, shooting
  touch), so his games move together.
Anything fitted is fitted on one season and graded on others.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

import daily
import matchup
from math_engine import ALL_CATEGORIES, NEGATIVE_CATEGORIES, FantasyMathEngine

TEAMS = 16
ROSTER = 10
SEATS = 5
HISTORY = 60
LISTED_AFTER_MISSED = 2
DD_STATS = ("pts", "reb", "ast", "stl", "blk")
LOG_COLUMNS = ("player_id", "team", "date", "min", "fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd")


@dataclass(frozen=True)
class Variant:
    name: str
    miss_after_play: float = 0.0  # chance a healthy player misses the next game
    miss_after_miss: float = 0.0  # chance he misses again once he missed
    listed_plays: float = 0.0  # chance a player who missed his last two games plays
    form_sd: float = 0.0  # spread of the shared weekly form factor (log scale)
    dd_from_stats: bool = False  # recount double-doubles from the drawn stats instead of scaling the flag


def load_logs(path: Path) -> pd.DataFrame:
    logs = pd.read_csv(path, usecols=lambda column: column in LOG_COLUMNS)
    return logs.sort_values(["date", "player_id"], kind="mergesort").reset_index(drop=True)


def miss_rates(logs: pd.DataFrame, min_minutes: float = 24.0, min_games: int = 40) -> dict[str, float]:
    """For regulars: chance of missing a team game after playing the last one, and after missing it."""
    team_days = logs.groupby("team")["date"].apply(lambda days: sorted(set(days))).to_dict()
    regulars = logs.groupby("player_id").agg(mp=("min", "mean"), n=("min", "size"))
    regulars = regulars[(regulars["mp"] >= min_minutes) & (regulars["n"] >= min_games)].index
    after_play = [0, 0]
    after_miss = [0, 0]
    after_two = [0, 0]
    for player_id in regulars:
        games = logs[logs["player_id"] == player_id]
        played = set(games["date"])
        for team, stint in games.groupby("team"):
            days = [day for day in team_days[team] if stint["date"].min() <= day <= stint["date"].max()]
            for index in range(1, len(days)):
                before, now = days[index - 1], days[index]
                bucket = after_play if before in played else after_miss
                bucket[0] += now not in played
                bucket[1] += 1
                if index >= 2 and before not in played and days[index - 2] not in played:
                    after_two[0] += now in played
                    after_two[1] += 1
    return {
        "miss_after_play": after_play[0] / after_play[1],
        "miss_after_miss": after_miss[0] / after_miss[1],
        "plays_after_two_missed": after_two[0] / after_two[1],
        "cases_after_play": after_play[1],
        "cases_after_miss": after_miss[1],
    }


def mondays(logs: pd.DataFrame) -> list[date]:
    """Every Monday from the second week of the season to the last full week."""
    first = date.fromisoformat(logs["date"].min())
    last = date.fromisoformat(logs["date"].max())
    monday = first + timedelta(days=(7 - first.weekday()) % 7 or 7)
    out = []
    while monday + timedelta(days=6) <= last:
        out.append(monday)
        monday += timedelta(days=7)
    return out


def _per_game(logs: pd.DataFrame) -> pd.DataFrame:
    grouped = logs.groupby("player_id")
    frame = grouped[list(daily.STAT_COLUMNS) + ["dd"]].mean()
    frame["mp"] = grouped["min"].mean()
    frame["games"] = grouped.size()
    frame["fg_pct"] = (frame["fgm"] / frame["fga"].where(frame["fga"] > 0)).fillna(0.0)
    frame["ft_pct"] = (frame["ftm"] / frame["fta"].where(frame["fta"] > 0)).fillna(0.0)
    frame["positions"] = ""
    return frame


def draft(prior: pd.DataFrame, min_games: int = 30) -> tuple[list[list[int]], dict]:
    """Snake draft of the previous season's best per-game values. Returns teams and the value baselines."""
    pool = _per_game(prior)
    pool = pool[pool["games"] >= min_games]
    engine = FantasyMathEngine()
    top = pool.sort_values("mp", ascending=False).head(TEAMS * ROSTER * 2)
    baselines = engine.category_baselines(top)
    scored = engine.score_with_baselines(pool, baselines)
    value = sum(scored[f"z_{category}"] for category in ALL_CATEGORIES)
    order = list(value.sort_values(ascending=False).index[: TEAMS * ROSTER])
    teams: list[list[int]] = [[] for _ in range(TEAMS)]
    for pick, player_id in enumerate(order):
        rnd, slot = divmod(pick, TEAMS)
        teams[slot if rnd % 2 == 0 else TEAMS - 1 - slot].append(int(player_id))
    return teams, baselines


@dataclass
class TeamWeek:
    """One fantasy team's week: the seated player-games, the forecast inputs, and what really happened."""

    games: list[dict]  # player_id, date, mean, hist, listed
    actual: np.ndarray


def week_inputs(teams: list[list[int]], prior: pd.DataFrame, season: pd.DataFrame, monday: date, baselines: dict, days_known: int = 0) -> list[TeamWeek]:
    """``days_known`` days from Monday are already played: those games are fixed, the rest forecast from then."""
    start, end = monday.isoformat(), (monday + timedelta(days=6)).isoformat()
    cut = (monday + timedelta(days=days_known)).isoformat()
    before = season[season["date"] < cut]
    team_days = season.groupby("team")["date"].apply(lambda days: sorted(set(days))).to_dict()
    prior_games = {player_id: games for player_id, games in prior.groupby("player_id")}
    this_games = {player_id: games for player_id, games in before.groupby("player_id")}
    week_logs = season[(season["date"] >= start) & (season["date"] <= end)]
    real = {(int(row.player_id), row.date): row for row in week_logs.itertuples()}

    lines, info = {}, {}
    for player_id in {player for team in teams for player in team}:
        old = prior_games.get(player_id, pd.DataFrame())
        now = this_games.get(player_id, pd.DataFrame())
        anchor = daily.anchor_from_games(old) if len(old) else None
        line = daily.project_line(anchor, now if len(now) else None)
        if line is None:
            continue
        team = (now["team"].iloc[-1] if len(now) else old["team"].iloc[-1]) if (len(now) or len(old)) else None
        if team not in team_days:
            continue
        past_team_days = [day for day in team_days[team] if day < cut]
        missed = past_team_days[-LISTED_AFTER_MISSED:]
        played_days = set(now["date"]) if len(now) else set()
        listed = len(missed) == LISTED_AFTER_MISSED and not (set(missed) & played_days)
        stacked = pd.concat([frame for frame in (old, now) if len(frame)]).tail(HISTORY).rename(columns={"min": "mp"})
        lines[player_id] = line
        info[player_id] = {
            "team": team,
            "listed": listed,
            "hist": stacked[list(matchup.STATS)].to_numpy(dtype=float),
            "days": [day for day in team_days[team] if start <= day <= end],
        }
    if not lines:
        return []
    ids = list(lines)
    values = dict(zip(ids, (result["value"] for result in daily.score_lines([lines[player_id] for player_id in ids], baselines))))

    out = []
    for team in teams:
        by_day: dict[str, list[int]] = {}
        for player_id in team:
            if player_id in info:
                for day in info[player_id]["days"]:
                    by_day.setdefault(day, []).append(player_id)
        games, actual = [], np.zeros(len(matchup.STATS))
        for day, players in by_day.items():
            # The pad's rule: the five best by projected value, a listed player only if nobody else.
            ranked = sorted(players, key=lambda player_id: (info[player_id]["listed"], -values[player_id]))[:SEATS]
            for player_id in ranked:
                row = real.get((player_id, day))
                line = np.array([float(getattr(row, "min" if stat == "mp" else stat)) for stat in matchup.STATS]) if row is not None else np.zeros(len(matchup.STATS))
                actual += line
                games.append({"player_id": player_id, "date": day, "mean": matchup.line_vector(lines[player_id]), "hist": info[player_id]["hist"],
                              "listed": info[player_id]["listed"], "fixed": line if day < cut else None})
        out.append(TeamWeek(games=games, actual=actual))
    return out


def _dd(games: np.ndarray) -> np.ndarray:
    tens = sum((games[:, matchup.AT[stat]] >= 10).astype(int) for stat in DD_STATS)
    return (tens >= 2).astype(float)


def simulate(team: TeamWeek, variant: Variant, runs: int, rng: np.random.Generator) -> np.ndarray:
    """``runs`` versions of this team's week under ``variant``."""
    totals = np.zeros((runs, len(matchup.STATS)))
    by_player: dict[int, list[dict]] = {}
    for game in team.games:
        by_player.setdefault(game["player_id"], []).append(game)
    for player_games in by_player.values():
        player_games.sort(key=lambda game: game["date"])
        for game in player_games:
            if game.get("fixed") is not None:
                totals += game["fixed"]
        player_games = [game for game in player_games if game.get("fixed") is None]
        if not player_games:
            continue
        form = np.exp(rng.normal(-0.5 * variant.form_sd**2, variant.form_sd, runs)) if variant.form_sd else None
        listed = player_games[0]["listed"]
        chained = bool(variant.miss_after_play or variant.miss_after_miss)
        playing = rng.random(runs) < (variant.listed_plays if listed else 1.0 - variant.miss_after_play)
        for index, game in enumerate(player_games):
            if index:
                if chained:
                    playing = rng.random(runs) >= np.where(playing, variant.miss_after_play, variant.miss_after_miss)
                elif listed:
                    playing = rng.random(runs) < variant.listed_plays
            entry = {"mean": game["mean"], "hist": game["hist"], "p": 1.0}
            draws = matchup.draw(entry, runs, rng)
            if variant.dd_from_stats and game["hist"] is not None and len(game["hist"]):
                draws[:, matchup.AT["dd"]] = _dd(draws)
            if form is not None:
                volume = [index for stat, index in matchup.AT.items() if stat != "dd"]
                draws[:, volume] *= form[:, None]
                if variant.dd_from_stats:
                    draws[:, matchup.AT["dd"]] = _dd(draws)
            totals += draws * playing[:, None]
    return totals


def forecasts(week: list[TeamWeek], variant: Variant, runs: int, seed: int) -> pd.DataFrame:
    """Every pair of teams, every category: the forecast chance and the real result (1, 0.5, 0)."""
    rng = np.random.default_rng(seed)
    sims = [matchup.category_values(simulate(team, variant, runs, rng)) for team in week]
    reals = [matchup.category_values(team.actual[None, :]) for team in week]
    rows = []
    for first, second in combinations(range(len(week)), 2):
        for category in ALL_CATEGORIES:
            sign = -1.0 if category in NEGATIVE_CATEGORIES else 1.0
            gap = sign * (sims[first][category] - sims[second][category])
            chance = float((gap > 1e-9).mean() + 0.5 * (np.abs(gap) <= 1e-9).mean())
            real_gap = sign * float(reals[first][category][0] - reals[second][category][0])
            result = 1.0 if real_gap > 1e-9 else 0.5 if real_gap >= -1e-9 else 0.0
            rows.append({"pair": f"{first}-{second}", "cat": category, "chance": chance, "result": result})
    return pd.DataFrame(rows)


def shrink(chance: np.ndarray, slope: float) -> np.ndarray:
    clipped = np.clip(chance, 1e-4, 1 - 1e-4)
    odds = np.log(clipped / (1 - clipped))
    return 1 / (1 + np.exp(-slope * odds))


def fit_slope(chance: np.ndarray, result: np.ndarray) -> float:
    """The log-odds slope that minimises the Brier score (1 = no change, below 1 = pull toward even)."""
    slopes = np.linspace(0.2, 1.6, 141)
    scores = [float(((shrink(chance, slope) - result) ** 2).mean()) for slope in slopes]
    return float(slopes[int(np.argmin(scores))])


def scores(chance: np.ndarray, result: np.ndarray) -> dict[str, float]:
    clipped = np.clip(chance, 1e-3, 1 - 1e-3)
    return {
        "brier": float(((chance - result) ** 2).mean()),
        "log_loss": float(-(result * np.log(clipped) + (1 - result) * np.log(1 - clipped)).mean()),
        "n": int(len(chance)),
    }


def calibration(chance: np.ndarray, result: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Forecasts in bins of 10 points: how often the side said to be ahead really won."""
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(chance, edges) - 1, 0, bins - 1)
    frame = pd.DataFrame({"bin": index, "chance": chance, "result": result})
    table = frame.groupby("bin").agg(said=("chance", "mean"), happened=("result", "mean"), n=("result", "size"))
    return table.reset_index(drop=True)
