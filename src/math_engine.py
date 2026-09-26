"""9-category head-to-head fantasy basketball math."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COUNTING_CATEGORIES: dict[str, str] = {
    "PTS": "pts",
    "REB": "reb",
    "AST": "ast",
    "STL": "stl",
    "BLK": "blk",
    "3PM": "fg3m",
    "TO": "to",
}

NEGATIVE_CATEGORIES = frozenset({"TO"})

PERCENTAGE_CATEGORIES: dict[str, tuple[str, str]] = {
    "FG%": ("fg_pct", "fga"),
    "FT%": ("ft_pct", "fta"),
}

ALL_CATEGORIES: tuple[str, ...] = (
    "PTS",
    "REB",
    "AST",
    "STL",
    "BLK",
    "3PM",
    "FG%",
    "FT%",
    "TO",
)

DUAL_POSITION_MULTIPLIER = 1.12


def _population_zscore(values: pd.Series) -> pd.Series:
    """Return (value - mean) / population std, or zeros when std is 0."""
    std = values.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=values.index, dtype="float64")
    return (values - values.mean()) / std


def _volume_weighted_mean(rates: pd.Series, volume: pd.Series) -> float:
    total_volume = float(volume.sum())
    if total_volume == 0:
        return float(rates.mean())
    return float((rates * volume).sum() / total_volume)


class FantasyMathEngine:
    """Load projections and rank players with 9-cat z-scores and punts."""

    def __init__(self) -> None:
        self.df: pd.DataFrame | None = None

    def load_data(self, source: str | Path | pd.DataFrame) -> pd.DataFrame:
        """Load the available player pool from a CSV path, frame, or loader.

        A ``ProjectionLoader`` is accepted directly: anything with a ``load()``
        method that returns a DataFrame is used as the pool.
        """
        if isinstance(source, pd.DataFrame):
            frame = source.copy()
        elif callable(getattr(source, "load", None)):
            frame = source.load()
            if not isinstance(frame, pd.DataFrame):
                raise TypeError("Projection source load() must return a DataFrame.")
        else:
            frame = pd.read_csv(source)
        self.df = frame
        return self.df

    def calculate_z_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add per-category z-scores and volume-weighted shooting impacts."""
        scored = df.copy()

        for category, column in COUNTING_CATEGORIES.items():
            z_score = _population_zscore(scored[column])
            if category in NEGATIVE_CATEGORIES:
                z_score = -1 * z_score
            scored[f"z_{category}"] = z_score

        for category, (rate_column, volume_column) in PERCENTAGE_CATEGORIES.items():
            rates = scored[rate_column]
            volume = scored[volume_column]
            mean_rate = _volume_weighted_mean(rates, volume)
            impact = (rates - mean_rate) * volume
            scored[f"impact_{category}"] = impact
            scored[f"z_{category}"] = _population_zscore(impact)

        return scored

    def category_baselines(self, df: pd.DataFrame | None = None) -> dict:
        """Mean and spread of the current pool, used to score players outside it."""
        pool = self.df if df is None else df
        if pool is None:
            raise ValueError("No projections loaded. Call load_data() first.")
        baselines: dict = {}
        for category, column in COUNTING_CATEGORIES.items():
            values = pool[column]
            baselines[category] = {
                "mean": float(values.mean()),
                "std": float(values.std(ddof=0)),
            }
        for category, (rate_column, volume_column) in PERCENTAGE_CATEGORIES.items():
            impact = (pool[rate_column] - _volume_weighted_mean(pool[rate_column], pool[volume_column])) * pool[volume_column]
            baselines[category] = {
                "mean_rate": _volume_weighted_mean(pool[rate_column], pool[volume_column]),
                "impact_mean": float(impact.mean()),
                "impact_std": float(impact.std(ddof=0)),
            }
        return baselines

    def score_with_baselines(self, df: pd.DataFrame, baselines: dict) -> pd.DataFrame:
        """Score rows with a frozen pool baseline so newcomers do not move veteran ranks."""
        scored = df.copy()
        for category, column in COUNTING_CATEGORIES.items():
            mean = baselines[category]["mean"]
            std = baselines[category]["std"]
            z_score = (scored[column] - mean) / std if std else 0.0
            if category in NEGATIVE_CATEGORIES:
                z_score = -1 * z_score
            scored[f"z_{category}"] = z_score
        for category, (rate_column, volume_column) in PERCENTAGE_CATEGORIES.items():
            reference = baselines[category]
            impact = (scored[rate_column] - reference["mean_rate"]) * scored[volume_column]
            std = reference["impact_std"]
            z_score = (impact - reference["impact_mean"]) / std if std else 0.0
            scored[f"impact_{category}"] = impact
            scored[f"z_{category}"] = z_score
        base_value = sum(scored[f"z_{category}"] for category in ALL_CATEGORIES)
        multi_position = scored["positions"].astype(str).str.contains("/", regex=False)
        scored["total_value"] = base_value.where(
            ~multi_position,
            base_value * DUAL_POSITION_MULTIPLIER,
        )
        return scored

    def get_ranked_players(self, active_punts: list[str] | None = None) -> pd.DataFrame:
        """Rank the loaded pool by z-score value, dropping any punted categories.

        Multi-position players (a ``/`` in ``positions``) receive a 1.12x
        multiplier on the summed value. Stored z-scores are left unchanged.
        """
        if self.df is None:
            raise ValueError("No projections loaded. Call load_data() first.")

        punts = list(active_punts or [])
        unknown = [category for category in punts if category not in ALL_CATEGORIES]
        if unknown:
            raise ValueError(f"Unknown punt categories: {unknown}")

        scored = self.calculate_z_scores(self.df)
        kept = [f"z_{category}" for category in ALL_CATEGORIES if category not in punts]
        base_value = scored[kept].sum(axis=1)
        multi_position = scored["positions"].astype(str).str.contains("/", regex=False)
        scored["total_value"] = base_value.where(
            ~multi_position,
            base_value * DUAL_POSITION_MULTIPLIER,
        )
        ranked = scored.sort_values("total_value", ascending=False, kind="mergesort")
        return ranked.reset_index(drop=True)
