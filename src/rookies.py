"""2026 draft class: college lines translated onto the veteran 9-cat scale.

College games played are not used as the NBA games prediction. Expected games
come from how many games recent rookies at that draft slot actually played.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ROOKIE_PATH = ROOT / "data" / "rookies_2026.csv"

COUNTING_STATS = ("pts", "reb", "ast", "stl", "blk", "fg3m", "fga", "fta", "to")
RATE_STATS = ("fg_pct", "ft_pct")
PICK_BANDS = ((1, 5), (6, 14), (15, 30), (31, 45), (46, 60))
COLLEGE_STAT_FIELDS = {
    "games": "gamesPlayed",
    "minutes": "avgMinutes",
    "pts": "avgPoints",
    "reb": "avgRebounds",
    "ast": "avgAssists",
    "stl": "avgSteals",
    "blk": "avgBlocks",
    "fg3m": "avgThreePointFieldGoalsMade",
    "fga": "avgFieldGoalsAttempted",
    "fg_pct": "fieldGoalPct",
    "fta": "avgFreeThrowsAttempted",
    "ft_pct": "freeThrowPct",
    "to": "avgTurnovers",
}
POSITION_MAP = {"G": "PG", "F": "SF", "C": "C"}


def name_key(name: object) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = "".join(char if char.isalnum() or char.isspace() else " " for char in text)
    return " ".join(text.lower().split())


def pick_band(overall_pick: int) -> str:
    for start, end in PICK_BANDS:
        if start <= int(overall_pick) <= end:
            return f"{start}-{end}"
    return "46-60"


def predict_rookie_games(overall_pick: int, games_by_band: dict[str, float]) -> int:
    band = pick_band(overall_pick)
    games = games_by_band.get(band, games_by_band.get("15-30", 55))
    return int(round(min(82, max(0, games))))


def translate_college_line(college: dict, counting_ratios: dict[str, float], rate_deltas: dict[str, float]) -> dict:
    """Scale a college per-game line by the prior draft class's NBA/college gap."""
    translated = {}
    for stat in COUNTING_STATS:
        translated[stat] = round(float(college[stat]) * counting_ratios[stat], 3)
    for stat in RATE_STATS:
        translated[stat] = round(min(0.95, max(0.30, float(college[stat]) + rate_deltas[stat])), 3)
    return translated


def fit_translation(pairs: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    """Median NBA-to-college ratio from rookies who played both levels.

    ``pairs`` has ``college_<stat>`` and ``nba_<stat>`` columns. Counting stats
    use a ratio. Shooting percentages use the median NBA minus college gap.
    """
    counting: dict[str, float] = {}
    for stat in COUNTING_STATS:
        college = pairs[f"college_{stat}"]
        nba = pairs[f"nba_{stat}"]
        usable = college > 0.4
        if int(usable.sum()) < 5:
            counting[stat] = 0.75
            continue
        counting[stat] = float((nba[usable] / college[usable]).median())
    rates: dict[str, float] = {}
    for stat in RATE_STATS:
        gap = pairs[f"nba_{stat}"] - pairs[f"college_{stat}"]
        rates[stat] = float(gap.median()) if len(gap) else -0.03
    return counting, rates


def _espn_page(season: int, page: int, limit: int = 400, qualified: bool = True) -> dict:
    qualified_flag = "true" if qualified else "false"
    url = (
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/"
        "mens-college-basketball/statistics/byathlete"
        f"?region=us&lang=en&contentorigin=espn&isqualified={qualified_flag}&season={season}"
        f"&seasontype=2&limit={limit}&page={page}"
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _athlete_row(payload: dict, glossary: dict[str, dict[str, int]]) -> dict:
    athlete = payload["athlete"]
    values: dict[str, float] = {}
    for category in payload.get("categories", []):
        index = glossary.get(category["name"], {})
        numbers = category.get("values") or []
        for field, position in index.items():
            if position < len(numbers) and numbers[position] is not None:
                number = float(numbers[position])
                if field in {"fieldGoalPct", "freeThrowPct", "threePointFieldGoalPct"} and number > 1:
                    number = number / 100
                values[field] = number
    position = (athlete.get("position") or {}).get("abbreviation", "")
    return {
        "player_name": athlete.get("displayName", ""),
        "college_position": POSITION_MAP.get(position, position),
        "college_team": athlete.get("teamShortName") or athlete.get("teamName") or "",
        **{column: values.get(field) for column, field in COLLEGE_STAT_FIELDS.items()},
    }


def fetch_college_season(season: int, qualified: bool = True) -> pd.DataFrame:
    label = "qualified" if qualified else "all"
    cache = ROOT / "data" / "cache" / f"cbb_{season}_{label}.csv"
    if cache.exists():
        frame = pd.read_csv(cache)
        frame["name_key"] = frame["player_name"].map(name_key)
        return frame
    first = _espn_page(season, 1, qualified=qualified)
    glossary = {
        category["name"]: {name: index for index, name in enumerate(category["names"])}
        for category in first["categories"]
    }
    pages = int(first["pagination"]["pages"])
    rows = [_athlete_row(payload, glossary) for payload in first["athletes"]]
    for page in range(2, pages + 1):
        payload = _espn_page(season, page, qualified=qualified)
        rows.extend(_athlete_row(athlete, glossary) for athlete in payload["athletes"])
    frame = pd.DataFrame(rows)
    frame["name_key"] = frame["player_name"].map(name_key)
    cache.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache, index=False)
    return frame


def fetch_draft(season_year: int) -> pd.DataFrame:
    from nba_api.stats.endpoints import drafthistory

    draft = drafthistory.DraftHistory(season_year_nullable=str(season_year), timeout=60).get_data_frames()[0]
    frame = pd.DataFrame(
        {
            "player_name": draft["PLAYER_NAME"],
            "overall_pick": draft["OVERALL_PICK"].astype(int),
            "team": draft["TEAM_ABBREVIATION"],
            "college": draft["ORGANIZATION"],
            "organization_type": draft["ORGANIZATION_TYPE"],
        }
    )
    frame["name_key"] = frame["player_name"].map(name_key)
    return frame


def rookie_games_by_band(drafts: pd.DataFrame, nba_games: pd.DataFrame) -> dict[str, float]:
    """Median first-year games for each pick band.

    ``nba_games`` columns: ``name_key``, ``gp``.
    """
    merged = drafts.merge(nba_games, on="name_key", how="inner")
    merged["band"] = merged["overall_pick"].map(pick_band)
    medians = merged.groupby("band")["gp"].median()
    return {band: float(medians[band]) for band in medians.index}


def _last_name(name: object) -> str:
    parts = [part for part in name_key(name).split() if part not in {"jr", "sr", "ii", "iii", "iv"}]
    return parts[-1] if parts else ""


def _match_college_players(draft: pd.DataFrame, college: pd.DataFrame) -> pd.DataFrame:
    """Match a draft list to college lines, including a unique last-name fallback."""
    pool = college.drop_duplicates("name_key").copy()
    pool["last_name"] = pool["player_name"].map(_last_name)
    rows = []
    for _, prospect in draft.iterrows():
        hit = pool[pool["name_key"] == prospect["name_key"]]
        if hit.empty:
            candidates = pool[(pool["last_name"] == _last_name(prospect["player_name"])) & (pool["minutes"].fillna(0) >= 15)]
            if len(candidates) == 1:
                hit = candidates
        record: dict[str, object] = {"player_name": prospect["player_name"]}
        if hit.empty:
            record["college_position"] = ""
            for column in COLLEGE_STAT_FIELDS:
                record[column] = pd.NA
        else:
            source = hit.iloc[0]
            record["college_position"] = source["college_position"]
            for column in COLLEGE_STAT_FIELDS:
                record[column] = source[column]
        rows.append(record)
    return pd.DataFrame(rows)


class RookieBoard:
    """Build translated 2026 rookie lines and score them on the veteran scale."""

    def __init__(self, path: Path = ROOKIE_PATH) -> None:
        self.path = path

    def load(self) -> pd.DataFrame:
        frame = pd.read_csv(self.path)
        return frame

    def build(self, nba_pool: pd.DataFrame) -> pd.DataFrame:
        draft = fetch_draft(2026)
        college = fetch_college_season(2026, qualified=False)
        ratios, deltas = self._prior_class_translation(nba_pool)
        games_by_band = self._historical_rookie_games()
        board = self._assemble(draft, college, ratios, deltas, games_by_band)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        board.to_csv(self.path, index=False)
        return board

    def _prior_class_translation(self, nba_pool: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
        draft = fetch_draft(2025)
        college = fetch_college_season(2025)
        college_stats = college[["name_key", "games", "minutes", *COUNTING_STATS, *RATE_STATS]].rename(
            columns={stat: f"{stat}_cbb" for stat in ("games", "minutes", *COUNTING_STATS, *RATE_STATS)}
        )
        nba = nba_pool.copy()
        nba["name_key"] = nba["player_name"].map(name_key)
        nba_stats = nba[["name_key", "games", "mp", *COUNTING_STATS, *RATE_STATS]].rename(
            columns={stat: f"{stat}_nba" for stat in ("games", "mp", *COUNTING_STATS, *RATE_STATS)}
        )
        merged = draft.merge(college_stats, on="name_key", how="inner").merge(nba_stats, on="name_key", how="inner")
        merged = merged[
            (merged["overall_pick"] <= 30)
            & (merged["games_cbb"] >= 20)
            & (merged["minutes_cbb"] >= 20)
            & (merged["games_nba"] >= 40)
            & (merged["mp_nba"] >= 20)
        ]
        pairs = pd.DataFrame()
        for stat in (*COUNTING_STATS, *RATE_STATS):
            pairs[f"college_{stat}"] = pd.to_numeric(merged[f"{stat}_cbb"], errors="coerce")
            pairs[f"nba_{stat}"] = pd.to_numeric(merged[f"{stat}_nba"], errors="coerce")
        fitted = pairs.dropna()
        if len(fitted) < 8:
            raise ValueError(f"Only {len(fitted)} prior-class rookies matched college and NBA lines.")
        return fit_translation(fitted)

    def _historical_rookie_games(self) -> dict[str, float]:
        from nba_api.stats.endpoints import leaguedashplayerstats

        frames = []
        season_for_draft = {2023: "2023-24", 2024: "2024-25", 2025: "2025-26"}
        for draft_year, season in season_for_draft.items():
            draft = fetch_draft(draft_year)
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star="Regular Season",
                per_mode_detailed="PerGame",
                timeout=60,
            ).get_data_frames()[0]
            games = pd.DataFrame({"name_key": stats["PLAYER_NAME"].map(name_key), "gp": stats["GP"]})
            frames.append(draft.merge(games, on="name_key", how="inner"))
        history = pd.concat(frames, ignore_index=True)
        history["band"] = history["overall_pick"].map(pick_band)
        medians = history.groupby("band")["gp"].median()
        return {str(band): float(medians[band]) for band in medians.index}

    def _assemble(self, draft, college, ratios, deltas, games_by_band) -> pd.DataFrame:
        college_keep = _match_college_players(draft, college)
        merged = draft.drop(columns=["name_key"]).merge(college_keep, on="player_name", how="left")
        rows = []
        for _, player in merged.iterrows():
            predicted = predict_rookie_games(int(player["overall_pick"]), games_by_band)
            record = {
                "player_name": player["player_name"],
                "positions": player["college_position"] if isinstance(player["college_position"], str) else "",
                "team": player["team"],
                "overall_pick": int(player["overall_pick"]),
                "college": player["college"],
                "predicted_games": predicted,
                "college_games": player.get("games"),
            }
            has_college = pd.notna(player.get("pts"))
            record["translation"] = "college_to_nba" if has_college else "no_college_stats"
            if has_college:
                record.update(translate_college_line(player, ratios, deltas))
            else:
                for stat in (*COUNTING_STATS, *RATE_STATS):
                    record[stat] = pd.NA
            rows.append(record)
        return pd.DataFrame(rows).sort_values("overall_pick").reset_index(drop=True)
