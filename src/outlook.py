"""Season outlook: next season's per-game line from the last three seasons and age.

Last season's per-game line is the naive guess. This fits, on past seasons,
how much each of the last three seasons, the league average and age say about
the next one, per stat. It only feeds the in-season pad's anchor line. The
draft board and the 12-cat z contract are untouched.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RATE_STATS: tuple[str, ...] = ("fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd")
# League-average minutes mixed into a season's rate, so a short season is not taken at face value.
SHRINK_MINUTES = 400.0
# A season counts for fitting and projecting only past this many minutes.
MIN_MINUTES = 300.0
PRIME_AGE = 27.0
# Share of the fitted model in the written line; the rest is last season as played.
# On three held-out seasons the model alone pulled top scorers about half a point
# too low and last season alone left them over a point too high. Half and half
# was best for them and within 2% of the model alone for everyone.
MODEL_SHARE = 0.5
LOOKBACK = 3


def season_totals(logs: pd.DataFrame) -> pd.DataFrame:
    """Games, minutes and stat totals per player per season."""
    grouped = logs.groupby(["season", "player_id"])
    totals = grouped[["min", *RATE_STATS]].sum()
    totals["g"] = grouped.size()
    return totals.reset_index()


def _league_rates(totals: pd.DataFrame) -> dict[str, dict[str, float]]:
    rates = {}
    for season, rows in totals.groupby("season"):
        minutes = float(rows["min"].sum())
        rates[season] = {stat: float(rows[stat].sum()) / minutes for stat in RATE_STATS}
    return rates


def feature_table(totals: pd.DataFrame, ages: pd.DataFrame, target: str, seasons: list[str]) -> pd.DataFrame:
    """One row per player with enough minutes in the season before ``target``.

    A missing older season repeats the nearest newer one. ``y_`` and ``mpg``
    columns for ``target`` are present only when that season has been played.
    """
    index = seasons.index(target) if target in seasons else len(seasons)
    league = _league_rates(totals)
    by_season = {season: rows.set_index("player_id") for season, rows in totals.groupby("season")}
    age_of = {(row.season, int(row.player_id)): float(row.age) for row in ages.itertuples()}
    previous = [seasons[index - back] if index - back >= 0 else None for back in range(1, LOOKBACK + 1)]
    if previous[0] is None:
        return pd.DataFrame()
    current = by_season.get(target)
    rows = []
    for player_id, last in by_season[previous[0]].iterrows():
        if last["min"] < MIN_MINUTES:
            continue
        age = age_of.get((previous[0], int(player_id)))
        row = {"player_id": int(player_id), "age": (age + 1.0) if age is not None else PRIME_AGE}
        nearest = None
        for back, season in enumerate(previous, start=1):
            table = by_season.get(season) if season else None
            if table is not None and player_id in table.index and table.loc[player_id, "min"] > 0:
                played = table.loc[player_id]
                row[f"mpg{back}"] = float(played["min"]) / float(played["g"])
                row[f"g{back}"] = float(played["g"])
                for stat in RATE_STATS:
                    row[f"r{back}_{stat}"] = (float(played[stat]) + SHRINK_MINUTES * league[season][stat]) / (
                        float(played["min"]) + SHRINK_MINUTES
                    )
                nearest = back
            else:
                row[f"mpg{back}"] = row[f"mpg{nearest}"]
                row[f"g{back}"] = 0.0
                for stat in RATE_STATS:
                    row[f"r{back}_{stat}"] = row[f"r{nearest}_{stat}"]
        for stat in RATE_STATS:
            row[f"lg_{stat}"] = league[previous[0]][stat]
        if current is not None and player_id in current.index and current.loc[player_id, "min"] >= MIN_MINUTES:
            now = current.loc[player_id]
            row["minutes"] = float(now["min"])
            row["games"] = float(now["g"])
            row["mpg"] = float(now["min"]) / float(now["g"])
            for stat in RATE_STATS:
                row[f"y_{stat}"] = float(now[stat]) / float(now["min"])
        rows.append(row)
    return pd.DataFrame(rows)


def _rate_inputs(table: pd.DataFrame, stat: str) -> np.ndarray:
    years = (table["age"] - PRIME_AGE).to_numpy()
    league = table[f"lg_{stat}"].to_numpy()
    return np.column_stack(
        [table[f"r1_{stat}"], table[f"r2_{stat}"], table[f"r3_{stat}"], league, years * league, years * years * league]
    )


def _minute_inputs(table: pd.DataFrame) -> np.ndarray:
    years = (table["age"] - PRIME_AGE).to_numpy()
    return np.column_stack(
        [table["mpg1"], table["mpg2"], table["mpg3"], np.ones(len(table)), years, years * years, table["g1"] / 82.0]
    )


def _weighted_fit(inputs: np.ndarray, target: np.ndarray, weight: np.ndarray) -> np.ndarray:
    root = np.sqrt(weight)
    return np.linalg.lstsq(inputs * root[:, None], target * root, rcond=None)[0]


def fit(totals: pd.DataFrame, ages: pd.DataFrame, targets: list[str], seasons: list[str]) -> dict:
    """Weights per stat and for minutes, fitted on the ``targets`` seasons."""
    tables = [feature_table(totals, ages, target, seasons) for target in targets]
    table = pd.concat([part for part in tables if len(part)], ignore_index=True).dropna(subset=["mpg"])
    model = {"minutes": _weighted_fit(_minute_inputs(table), table["mpg"].to_numpy(), table["games"].to_numpy())}
    for stat in RATE_STATS:
        model[stat] = _weighted_fit(_rate_inputs(table, stat), table[f"y_{stat}"].to_numpy(), table["minutes"].to_numpy())
    return model


def project(model: dict, table: pd.DataFrame) -> pd.DataFrame:
    """Per-game lines for the rows of a feature table."""
    lines = pd.DataFrame({"player_id": table["player_id"].astype(int)})
    lines["mp"] = np.clip(_minute_inputs(table) @ model["minutes"], 0.0, 40.0)
    for stat in RATE_STATS:
        lines[stat] = np.clip(_rate_inputs(table, stat) @ model[stat], 0.0, None) * lines["mp"]
    lines["fg_pct"] = (lines["fgm"] / lines["fga"]).where(lines["fga"] > 0, 0.0)
    lines["ft_pct"] = (lines["ftm"] / lines["fta"]).where(lines["fta"] > 0, 0.0)
    return lines


def naive(table: pd.DataFrame, totals: pd.DataFrame, season: str) -> pd.DataFrame:
    """Last season's per-game line for the same rows: the guess the model has to beat."""
    last = totals.loc[totals["season"] == season].set_index("player_id").loc[table["player_id"]]
    lines = pd.DataFrame({"player_id": table["player_id"].astype(int).to_numpy()})
    lines["mp"] = (last["min"] / last["g"]).to_numpy()
    for stat in RATE_STATS:
        lines[stat] = (last[stat] / last["g"]).to_numpy()
    return lines


def blend(model_lines: pd.DataFrame, last_lines: pd.DataFrame, share: float = MODEL_SHARE) -> pd.DataFrame:
    """Model and last season mixed stat by stat. Shooting rates come from the mixed makes and tries."""
    lines = pd.DataFrame({"player_id": model_lines["player_id"].to_numpy()})
    for stat in ("mp", *RATE_STATS):
        lines[stat] = share * model_lines[stat].to_numpy() + (1.0 - share) * last_lines[stat].to_numpy()
    lines["fg_pct"] = (lines["fgm"] / lines["fga"]).where(lines["fga"] > 0, 0.0)
    lines["ft_pct"] = (lines["ftm"] / lines["fta"]).where(lines["fta"] > 0, 0.0)
    return lines


def score(lines: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """Games-weighted error per stat against what happened, with the spread of the stat."""
    weight = table["games"].to_numpy()
    rows = []
    for stat in ("mp", *RATE_STATS):
        actual = table["mpg"].to_numpy() if stat == "mp" else (table[f"y_{stat}"] * table["mpg"]).to_numpy()
        centre = np.average(actual, weights=weight)
        rows.append(
            {
                "stat": stat,
                "error": float(np.average(np.abs(lines[stat].to_numpy() - actual), weights=weight)),
                "spread": float(np.sqrt(np.average((actual - centre) ** 2, weights=weight))),
            }
        )
    return pd.DataFrame(rows).set_index("stat")


def load_history(history_dir: Path, last_logs: pd.DataFrame, last_season: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Season totals, ages and the season list from the history folder plus last season."""
    frames = [pd.read_csv(path) for path in sorted(Path(history_dir).glob("gamelogs_*.csv"))]
    latest = last_logs.copy()
    latest["season"] = last_season
    totals = season_totals(pd.concat([*frames, latest], ignore_index=True))
    ages = pd.read_csv(Path(history_dir) / "ages.csv")
    return totals, ages, sorted(totals["season"].unique())


def build(history_dir: Path, last_logs: pd.DataFrame, last_season: str, next_season: str, out_path: Path) -> int:
    """Fit on every played season and write next season's lines. Returns players written."""
    totals, ages, seasons = load_history(history_dir, last_logs, last_season)
    model = fit(totals, ages, seasons[2:], seasons)
    table = feature_table(totals, ages, next_season, seasons)
    lines = blend(project(model, table), naive(table, totals, last_season))
    lines.to_csv(out_path, index=False)
    return int(len(lines))
