"""Stats board for the apps: per-game averages and 12-cat value over a rolling window.

Three windows (last 7 days, last 30 days, season), three views (my ten, this
week's opponent, the league's top players by value). Value is the pad's z-score
sum (``daily.score_lines`` against the season baselines) of the per-game
averages in the window, so it compares directly with the pad's own numbers.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd

import daily

WINDOWS: tuple[tuple[str, str, int | None], ...] = (("7d", "Last 7 days", 7), ("30d", "Last 30 days", 30), ("season", "Season", None))
LEAGUE_TOP = 50
# A player needs this share of the most games anyone played in the window to be ranked.
MIN_GAME_SHARE = 0.4
SUM_STATS = ("min", "fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd")
SHOWN = ("min", "pts", "reb", "ast", "fg3m", "stl", "blk", "to")


def window_games(logs: pd.DataFrame, today: date, days: int | None) -> pd.DataFrame:
    """Games before ``today``, the last ``days`` days of them (all season when ``None``)."""
    if logs.empty:
        return logs
    before = logs.loc[logs["date"].astype(str) < today.isoformat()]
    if days is None:
        return before
    return before.loc[before["date"].astype(str) >= (today - timedelta(days=days)).isoformat()]


def averages(games: pd.DataFrame) -> pd.DataFrame:
    """One row per player: games, per-game means, made/attempted totals for the percentages."""
    if games.empty:
        return pd.DataFrame()
    grouped = games.groupby("player_id")
    frame = grouped[list(SUM_STATS)].sum()
    frame["games"] = grouped.size()
    frame["player_name"] = grouped["player_name"].last()
    frame["team"] = grouped["team"].last()
    return frame.reset_index()


def score(frame: pd.DataFrame, baselines: dict) -> pd.DataFrame:
    """Add per-game lines, FG% / FT% and the 12-cat value."""
    if frame.empty:
        return frame
    lines = []
    for row in frame.itertuples():
        line = {"mp": row.min / row.games, **{stat: getattr(row, stat) / row.games for stat in daily.STAT_COLUMNS}, "dd": row.dd / row.games}
        line["fg_pct"] = row.fgm / row.fga if row.fga else 0.0
        line["ft_pct"] = row.ftm / row.fta if row.fta else 0.0
        lines.append(line)
    values = daily.score_lines(lines, baselines)
    frame = frame.copy()
    frame["value"] = [result["value"] for result in values]
    return frame


def _row(record: dict, owner: str, positions: str, rank: int | None, enough: bool) -> dict:
    games = int(record["games"])
    row = {
        "player_name": str(record["player_name"]),
        "team": str(record["team"]),
        "positions": positions,
        "owner": owner,
        "games": games,
        **{stat: round(float(record[stat]) / games, 1) for stat in SHOWN},
        "fg_pct": round(float(record["fgm"]) / float(record["fga"]), 3) if record["fga"] else None,
        "ft_pct": round(float(record["ftm"]) / float(record["fta"]), 3) if record["fta"] else None,
        "dd": int(record["dd"]),
        "value": round(float(record["value"]), 2),
        "rank": rank,
    }
    if not enough:
        row["few_games"] = True
    return row


def board(data, today: date, mine: list[str], theirs: list[str]) -> dict:
    """The three windows, each with the league's top players and my and my opponent's ten."""
    mine_set = {name.casefold() for name in mine}
    their_set = {name.casefold() for name in theirs}

    def owner(name: str) -> str:
        if name.casefold() in mine_set:
            return "mine"
        if name.casefold() in their_set:
            return "theirs"
        return data.rostered_by(name) or "free"

    windows, rows = [], {}
    for key, label, days in WINDOWS:
        games = window_games(data.logs, today, days)
        scored = score(averages(games), data.baselines)
        if scored.empty:
            rows[key] = {"league": [], "mine": [], "theirs": []}
            windows.append({"key": key, "label": label, "min_games": 0})
            continue
        floor = max(1, math.ceil(MIN_GAME_SHARE * int(scored["games"].max())))
        scored["enough"] = scored["games"] >= floor
        ranked = scored.loc[scored["enough"]].sort_values("value", ascending=False).reset_index(drop=True)
        ranks = {int(player_id): index + 1 for index, player_id in enumerate(ranked["player_id"])}
        by_name = {str(record["player_name"]).casefold(): record for record in scored.to_dict("records")}

        def shaped(record: dict) -> dict:
            name = str(record["player_name"])
            return _row(record, owner(name), data.positions_for(name)[0], ranks.get(int(record["player_id"])), bool(record["enough"]))

        def team_rows(names: list[str]) -> list[dict]:
            found = [by_name[name.casefold()] for name in names if name.casefold() in by_name]
            return sorted((shaped(record) for record in found), key=lambda row: -row["value"])

        rows[key] = {
            "league": [shaped(record) for record in ranked.head(LEAGUE_TOP).to_dict("records")],
            "mine": team_rows(mine),
            "theirs": team_rows(theirs),
        }
        dates = games["date"].astype(str)
        windows.append({"key": key, "label": label, "from": dates.min(), "to": dates.max(), "min_games": floor})
    return {"windows": windows, "rows": rows}
