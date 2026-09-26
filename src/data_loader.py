"""Projection ingestion and NBA schedule fetching."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

STANDARD_COLUMNS: tuple[str, ...] = (
    "player_name",
    "positions",
    "pts",
    "reb",
    "ast",
    "stl",
    "blk",
    "fg3m",
    "fg_pct",
    "fga",
    "ft_pct",
    "fta",
    "to",
)

NUMERIC_COLUMNS: tuple[str, ...] = tuple(
    column for column in STANDARD_COLUMNS if column not in {"player_name", "positions"}
)

PERCENTAGE_COLUMNS = frozenset({"fg_pct", "ft_pct"})

# Floors used when an export leaves a stat blank. Counting stats use 0.
# Shooting percentages use a replacement-level rate rather than 0%.
REPLACEMENT_MINIMUMS: dict[str, float] = {
    "pts": 0.0,
    "reb": 0.0,
    "ast": 0.0,
    "stl": 0.0,
    "blk": 0.0,
    "fg3m": 0.0,
    "fg_pct": 0.40,
    "fga": 0.0,
    "ft_pct": 0.70,
    "fta": 0.0,
    "to": 0.0,
}

COLUMN_ALIASES: dict[str, set[str]] = {
    "player_name": {"player_name", "player", "name", "playername"},
    "positions": {"positions", "position", "pos", "eligible_positions", "elig_pos"},
    "pts": {"pts", "points", "ppg", "pts_per_g"},
    "reb": {"reb", "rebounds", "trb", "treb", "reb_per_g", "trb_per_g"},
    "ast": {"ast", "assists", "ast_per_g"},
    "stl": {"stl", "steals", "stl_per_g"},
    "blk": {"blk", "blocks", "blk_per_g"},
    "fg3m": {"fg3m", "3pm", "3p", "threes", "3ptm", "fg3_per_g"},
    "fg_pct": {"fg_pct", "fgp", "fg_percentage"},
    "fga": {"fga", "fga_per_g"},
    "ft_pct": {"ft_pct", "ftp", "ft_percentage"},
    "fta": {"fta", "fta_per_g"},
    "to": {"to", "tov", "turnovers", "to_per_g", "tov_per_g"},
}

WEEKDAYS: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _canonical_header(name: str) -> str:
    text = str(name).strip().lower().replace("%", " pct")
    text = text.replace("-", " ").replace("/", " ")
    return "_".join(text.split())


def _normalize_positions(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    parts = [part.strip().upper() for part in re.split(r"[,/;|-]+", text) if part.strip()]
    return "/".join(parts)


class ProjectionLoader:
    """Read a projection export and return the standard player schema.

    Accepts local CSVs from Hashtag Basketball, Yahoo, Basketball Monster,
    or this project's own projections file. Extra columns such as team and
    games are preserved.
    """

    def __init__(
        self,
        filepath: str | Path,
        replacement_minimums: dict[str, float] | None = None,
    ) -> None:
        self.filepath = Path(filepath)
        self.replacement_minimums = dict(REPLACEMENT_MINIMUMS)
        if replacement_minimums:
            self.replacement_minimums.update(replacement_minimums)

    def load(self) -> pd.DataFrame:
        raw = pd.read_csv(self.filepath)
        normalized = self.normalize_columns(raw)
        return self.fill_missing(normalized)

    def normalize_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        renamed = self._rename_columns(frame)
        missing = [column for column in STANDARD_COLUMNS if column not in renamed.columns]
        if missing:
            raise ValueError(f"Projection file is missing required columns: {missing}")

        normalized = renamed.copy()
        normalized["player_name"] = normalized["player_name"].astype(str).str.strip()
        normalized["positions"] = normalized["positions"].map(_normalize_positions)
        for column in NUMERIC_COLUMNS:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
            if column in PERCENTAGE_COLUMNS:
                as_percent = normalized[column] > 1
                normalized.loc[as_percent, column] = normalized.loc[as_percent, column] / 100
        return normalized

    def fill_missing(self, frame: pd.DataFrame) -> pd.DataFrame:
        filled = frame.copy()
        filled = filled[filled["player_name"].ne("") & filled["player_name"].ne("nan")]
        for column in NUMERIC_COLUMNS:
            minimum = self.replacement_minimums[column]
            filled[column] = filled[column].fillna(minimum)
        still_missing = [
            column for column in NUMERIC_COLUMNS if filled[column].isna().any()
        ]
        if still_missing:
            raise ValueError(f"Numerical fields still contain missing values: {still_missing}")
        return filled.reset_index(drop=True)

    def _rename_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        alias_to_standard = {
            alias: standard
            for standard, aliases in COLUMN_ALIASES.items()
            for alias in aliases
        }
        rename: dict[str, str] = {}
        used: set[str] = set()
        for original in frame.columns:
            canonical = _canonical_header(original)
            standard = alias_to_standard.get(canonical, canonical)
            if standard in STANDARD_COLUMNS and standard not in used:
                rename[original] = standard
                used.add(standard)
        return frame.rename(columns=rename)


class NBAScheduleFetcher:
    """Season schedule from the official NBA stats API."""

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout

    def get_weekly_schedule_matrix(self, season: str = "2025-26") -> pd.DataFrame:
        """Games each team plays, Monday through Sunday, for every fantasy week.

        Uses ``scheduleleaguev2`` so one request returns the season slate.
        Regular-season games (game id prefix ``002``) are counted. Each row
        is one team in one Monday-Sunday matchup week.
        """
        from nba_api.stats.endpoints import scheduleleaguev2

        schedule = scheduleleaguev2.ScheduleLeagueV2(season=season, timeout=self.timeout)
        games = schedule.get_data_frames()[0]
        appearances = self._regular_season_appearances(games)
        return self._weekly_matrix(appearances, season)

    def _regular_season_appearances(self, games: pd.DataFrame) -> pd.DataFrame:
        game_ids = games["gameId"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
        regular = games.loc[game_ids.str.startswith("002")].copy()
        if "postponedStatus" in regular.columns:
            status = regular["postponedStatus"].astype(str).str.upper()
            regular = regular.loc[~status.isin({"Y", "YES", "POSTPONED"})]

        dates = pd.to_datetime(regular["gameDate"].astype(str).str.slice(0, 10), format="%m/%d/%Y")
        home = pd.DataFrame(
            {
                "game_date": dates.to_numpy(),
                "team": regular["homeTeam_teamTricode"].astype(str).to_numpy(),
            }
        )
        away = pd.DataFrame(
            {
                "game_date": dates.to_numpy(),
                "team": regular["awayTeam_teamTricode"].astype(str).to_numpy(),
            }
        )
        appearances = pd.concat([home, away], ignore_index=True)
        appearances = appearances[appearances["team"].ne("") & appearances["team"].ne("nan")]
        return appearances

    def _weekly_matrix(self, appearances: pd.DataFrame, season: str) -> pd.DataFrame:
        if appearances.empty:
            return pd.DataFrame(
                columns=["season", "week_start", "team", *WEEKDAYS, "games"]
            )

        dated = appearances.copy()
        dated["week_start"] = dated["game_date"] - pd.to_timedelta(dated["game_date"].dt.weekday, unit="D")
        dated["weekday"] = dated["game_date"].dt.day_name().str.slice(0, 3)

        counts = (
            dated.groupby(["week_start", "team", "weekday"], observed=True)
            .size()
            .unstack(fill_value=0)
            .reindex(columns=list(WEEKDAYS), fill_value=0)
        )
        teams = sorted(dated["team"].unique())
        weeks = sorted(dated["week_start"].unique())
        full_index = pd.MultiIndex.from_product([weeks, teams], names=["week_start", "team"])
        counts = counts.reindex(full_index, fill_value=0).reset_index()
        counts.insert(0, "season", season)
        counts["games"] = counts.loc[:, WEEKDAYS].sum(axis=1).astype(int)
        for day in WEEKDAYS:
            counts[day] = counts[day].astype(int)
        return counts.sort_values(["week_start", "team"], kind="mergesort").reset_index(drop=True)
