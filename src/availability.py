"""Predict next-season games played without changing draft value.

The forecast is a recency-weighted average of the player's own regular-season
games. It is informational. Ranking stays on per-game 9-category value.
"""

from __future__ import annotations

import unicodedata

import pandas as pd

HISTORY_SEASONS: tuple[str, ...] = ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")

# Most recent season counts as 1. Older seasons count less.
# A player who missed a season is left blank. That year is not a zero.
SEASON_WEIGHTS: dict[str, float] = {
    "2021-22": 0.15,
    "2022-23": 0.25,
    "2023-24": 0.50,
    "2024-25": 0.75,
    "2025-26": 1.00,
}

MAX_GAMES = 82


_SUFFIXES = (" jr", " sr", " ii", " iii", " iv")


def name_key(name: object) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.lower().split())


def _loose_key(name: object) -> str:
    """First and last name, without punctuation or a generational suffix."""
    text = name_key(name).replace(".", "").replace("-", " ")
    text = " ".join(text.split())
    for suffix in _SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    parts = text.split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1]}"
    return text


def predict_games(history: pd.DataFrame) -> pd.DataFrame:
    """Return one row per player with yearly games and a rounded prediction.

    ``history`` columns: ``player_name``, ``season``, ``gp``. Seasons in which
    the player does not appear are left blank and are not treated as zero.
    """
    required = {"player_name", "season", "gp"}
    missing = required - set(history.columns)
    if missing:
        raise ValueError(f"Games history is missing columns: {sorted(missing)}")

    frame = history.copy()
    frame["player_name"] = frame["player_name"].astype(str)
    frame["name_key"] = frame["player_name"].map(name_key)
    frame["gp"] = pd.to_numeric(frame["gp"], errors="coerce")
    frame = frame.dropna(subset=["gp"])
    frame = frame[frame["season"].isin(HISTORY_SEASONS)]

    names = (
        frame.sort_values("season")
        .groupby("name_key", as_index=False)
        .tail(1)[["name_key", "player_name"]]
    )
    yearly = (
        frame.pivot_table(index="name_key", columns="season", values="gp", aggfunc="sum")
        .reindex(columns=list(HISTORY_SEASONS))
    )

    weighted_gp = []
    weight_sums = []
    for _, row in yearly.iterrows():
        total = 0.0
        weight = 0.0
        for season in HISTORY_SEASONS:
            games = row[season]
            if pd.isna(games):
                continue
            season_weight = SEASON_WEIGHTS[season]
            total += season_weight * float(games)
            weight += season_weight
        weighted_gp.append(total / weight if weight else float("nan"))
        weight_sums.append(weight)

    yearly = yearly.copy()
    yearly["weighted_games"] = weighted_gp
    yearly["predicted_games"] = (
        pd.Series(weighted_gp, index=yearly.index).clip(upper=MAX_GAMES).round().astype("Int64")
    )
    yearly = yearly.reset_index().merge(names, on="name_key", how="left")
    yearly = yearly.rename(columns={season: f"gp_{season[:4]}" for season in HISTORY_SEASONS})
    columns = [
        "player_name",
        "name_key",
        "gp_2021",
        "gp_2022",
        "gp_2023",
        "gp_2024",
        "gp_2025",
        "predicted_games",
    ]
    return yearly[columns]


def _same_player(left: str, right: str) -> bool:
    if left == right:
        return True
    left_first, _, left_last = left.partition(" ")
    right_first, _, right_last = right.partition(" ")
    if not left_last or left_last != right_last:
        return False
    shorter, longer = sorted((left_first, right_first), key=len)
    return len(shorter) >= 3 and longer.startswith(shorter)


def attach_games_forecast(ranked: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    """Add the games forecast beside a value ranking. Sort order stays put."""
    order = ranked.copy()
    order["_row"] = range(len(order))
    order["name_key"] = order["player_name"].map(name_key)
    value_columns = ["gp_2021", "gp_2022", "gp_2023", "gp_2024", "gp_2025", "predicted_games"]
    history = forecast[["name_key", "player_name", *value_columns]].drop_duplicates("name_key")
    merged = order.merge(history.drop(columns=["player_name"]), on="name_key", how="left")

    missing = merged["predicted_games"].isna()
    if missing.any():
        history = history.copy()
        history["loose"] = history["player_name"].map(_loose_key)
        unique_loose = history.groupby("loose")["name_key"].transform("count").eq(1)
        by_loose = history.loc[unique_loose].set_index("loose")
        for idx in merged.index[missing]:
            loose = _loose_key(merged.at[idx, "player_name"])
            chosen = None
            if loose in by_loose.index:
                chosen = by_loose.loc[loose]
            else:
                candidates = history[history["loose"].map(lambda other: _same_player(loose, other))]
                if len(candidates) == 1:
                    chosen = candidates.iloc[0]
            if chosen is None:
                continue
            for column in value_columns:
                merged.at[idx, column] = chosen[column]

    merged = merged.sort_values("_row", kind="mergesort").drop(columns=["_row", "name_key"])
    return merged.reset_index(drop=True)


class GamesForecast:
    """Load regular-season games from the NBA stats API and forecast next year."""

    def __init__(self, seasons: tuple[str, ...] = HISTORY_SEASONS, timeout: int = 60) -> None:
        self.seasons = seasons
        self.timeout = timeout

    def fetch_history(self) -> pd.DataFrame:
        from nba_api.stats.endpoints import leaguedashplayerstats

        frames: list[pd.DataFrame] = []
        for season in self.seasons:
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star="Regular Season",
                per_mode_detailed="PerGame",
                timeout=self.timeout,
            )
            frame = stats.get_data_frames()[0]
            frames.append(
                pd.DataFrame(
                    {
                        "player_name": frame["PLAYER_NAME"],
                        "season": season,
                        "gp": frame["GP"],
                        "age": frame["AGE"],
                    }
                )
            )
        return pd.concat(frames, ignore_index=True)

    def build(self) -> pd.DataFrame:
        return predict_games(self.fetch_history())
