"""What the season pad reads from disk: the NBA feed plus the season lines."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import context
import daily
import injuries
import matchup
import nba_feed
import schedule as slate
import scouting
from availability import _loose_key, name_key
from data_loader import ProjectionLoader
from draft_room import PROJECTIONS, _attach_double_doubles, _prepare_rookies
from math_engine import FantasyMathEngine
from rookies import ROOKIE_PATH

# Fewer games than this last season is not a season line worth anchoring on.
MIN_ANCHOR_GAMES = 5
# Past games a simulated night is drawn from, latest first.
HISTORY_GAMES = 60
ROSTERS_NAME = "league_rosters.csv"
MATCHUPS_NAME = "matchups.csv"
# Yahoo's matchup page, typed in from a screenshot: both teams' week totals through a day.
YAHOO_SCORES_NAME = "yahoo_scores.csv"
YAHOO_COLUMNS = ("week", "through", "side", "min", "fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf", "dd")
# Yahoo's free-agent list, pasted by hand. When present, only these names are offered as adds.
FREE_AGENTS_NAME = "free_agents.csv"
# NBA feed positions are G / F / C. Yahoo's are finer; this is the nearest guess
# for a free agent whose Yahoo eligibility was never pasted.
FEED_POSITIONS = {"G": "PG/SG", "F": "SF/PF", "C": "C", "G-F": "SG/SF", "F-G": "SG/SF", "F-C": "PF/C", "C-F": "PF/C"}

_CACHE: dict[tuple, "SeasonData"] = {}


def _stack(*frames: pd.DataFrame) -> pd.DataFrame:
    """Rows of the non-empty frames, in order."""
    filled = [frame for frame in frames if len(frame)]
    return pd.concat(filled, ignore_index=True) if filled else frames[0]


def _read_logs(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=list(nba_feed.LOG_COLUMNS))
    return pd.read_csv(path, dtype={"game_id": str})


def season_lines() -> tuple[pd.DataFrame, dict]:
    """Season line per player (veterans, then rookies) and the veteran-pool baselines."""
    veterans = _attach_double_doubles(ProjectionLoader(PROJECTIONS).load())
    engine = FantasyMathEngine()
    engine.load_data(veterans)
    baselines = engine.category_baselines()
    lines = veterans
    if ROOKIE_PATH.exists():
        rookies = _prepare_rookies(pd.read_csv(ROOKIE_PATH).query("translation == 'college_to_nba'"))
        rookies = rookies.loc[~rookies["player_name"].isin(set(veterans["player_name"]))]
        lines = pd.concat([veterans, rookies], ignore_index=True)
    return lines, baselines


def _keyed(pairs) -> dict:
    """Name → value under the exact name and, where unambiguous, first-and-last only.

    Yahoo prints "Jimmy Butler III"; the projections say "Jimmy Butler".
    """
    exact: dict = {}
    loose: dict[str, list] = {}
    for name, value in pairs:
        exact[name_key(name)] = value
        loose.setdefault(_loose_key(name), []).append(value)
    for key, values in loose.items():
        if len(values) == 1:
            exact.setdefault(f"~{key}", values[0])
    return exact


def _find(table: dict, name: str):
    value = table.get(name_key(name))
    return value if value is not None else table.get(f"~{_loose_key(name)}")


class SeasonData:
    def __init__(self, feed_dir: Path | None = None, lines: pd.DataFrame | None = None, baselines: dict | None = None) -> None:
        self.feed_dir = feed_dir or nba_feed.FEED_DIR
        self.schedule = slate.load_schedule(self.feed_dir / nba_feed.SCHEDULE_PATH.name)
        self.weeks = slate.load_weeks(self.schedule, self.feed_dir / slate.WEEKS_PATH.name)
        self.logs = _read_logs(self.feed_dir / f"gamelogs_{nba_feed.SEASON}.csv")
        self.last_logs = _read_logs(self.feed_dir / f"gamelogs_{nba_feed.LAST_SEASON}.csv")
        self.older_logs = _read_logs(self.feed_dir / nba_feed.OLDER_LOGS_PATH.name)
        outlook_path = self.feed_dir / nba_feed.OUTLOOK_PATH.name
        self._outlook = (
            {int(row["player_id"]): row for row in pd.read_csv(outlook_path).to_dict("records")}
            if outlook_path.exists()
            else {}
        )
        players_path = self.feed_dir / nba_feed.PLAYERS_PATH.name
        self.players = (
            pd.read_csv(players_path) if players_path.exists() else pd.DataFrame(columns=list(nba_feed.PLAYER_COLUMNS))
        )
        if lines is None or baselines is None:
            lines, baselines = season_lines()
        self.baselines = baselines
        self._anchors = _keyed((row["player_name"], row) for row in lines.to_dict("records"))
        self._ids = self._index_players()
        self._teams = {int(row.player_id): slate.nba_team(row.team) for row in self.players.itertuples()}
        self._lines: dict[str, dict | None] = {}
        meta_path = self.feed_dir / nba_feed.META_PATH.name
        self.meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        self._feed_positions = {int(row.player_id): str(row.nba_position) for row in self.players.itertuples()}
        groups = {player_id: context.position_group(text) for player_id, text in self._feed_positions.items()}
        self.context = context.Context(_stack(self.last_logs, self.logs), groups)
        self._groups = groups
        self._history: dict[str, np.ndarray | None] = {}
        self._scout: scouting.Scout | None = None
        self._load_league()

    def _load_league(self) -> None:
        """Rosters and matchups Mario pasted from Yahoo, and the injury report."""
        rosters_path = self.feed_dir / ROSTERS_NAME
        self.rosters = (
            pd.read_csv(rosters_path)
            if rosters_path.exists()
            else pd.DataFrame(columns=["fantasy_team", "manager", "slot", "player_name", "nba_team", "positions"])
        )
        agents_path = self.feed_dir / FREE_AGENTS_NAME
        agents = pd.read_csv(agents_path).fillna("") if agents_path.exists() else pd.DataFrame(columns=["player_name", "positions", "yahoo_status"])
        self.free_agents = _keyed((row["player_name"], row) for row in agents.to_dict("records"))
        self._yahoo = _keyed(
            [(row["player_name"], str(row["positions"])) for row in agents.to_dict("records")]
            + [(row.player_name, str(row.positions)) for row in self.rosters.itertuples()]
        )
        self._rostered = _keyed((row.player_name, str(row.fantasy_team)) for row in self.rosters.itertuples())
        matchups_path = self.feed_dir / MATCHUPS_NAME
        self.matchups = (
            {int(row.week): str(row.opponent) for row in pd.read_csv(matchups_path).itertuples()}
            if matchups_path.exists()
            else {}
        )
        scores_path = self.feed_dir / YAHOO_SCORES_NAME
        self.yahoo_scores = pd.read_csv(scores_path) if scores_path.exists() else pd.DataFrame(columns=list(YAHOO_COLUMNS))
        injuries_path = self.feed_dir / nba_feed.INJURIES_PATH.name
        report = pd.read_csv(injuries_path).fillna("") if injuries_path.exists() else pd.DataFrame()
        self.injuries = _keyed((row["player_name"], row) for row in report.to_dict("records"))

    def yahoo_banked(self, week: int) -> dict | None:
        """The latest Yahoo score for ``week``: ``through`` a day, both sides as ``matchup.STATS`` vectors."""
        rows = self.yahoo_scores.loc[self.yahoo_scores["week"] == week] if len(self.yahoo_scores) else self.yahoo_scores
        if rows.empty:
            return None
        through = str(rows["through"].max())
        latest = rows.loc[rows["through"].astype(str) == through]
        sides = {}
        for side in ("mine", "theirs"):
            row = latest.loc[latest["side"] == side]
            if row.empty:
                return None
            values = row.iloc[0]
            sides[side] = np.array([float(values["min" if stat == "mp" else stat]) for stat in matchup.STATS])
        return {"through": through, **sides}

    def team_names(self, fantasy_team: str) -> list[str]:
        return [str(name) for name in self.rosters.loc[self.rosters["fantasy_team"] == fantasy_team, "player_name"]]

    def active_names(self, fantasy_team: str) -> list[str]:
        """Names that can score: an IL row stays rostered but out of the week's starts."""
        team = self.rosters[self.rosters["fantasy_team"] == fantasy_team]
        return [str(name) for name in team.loc[team["slot"].astype(str).str.upper() != "IL", "player_name"]]

    def positions_for(self, name: str, fallback: object = "") -> tuple[str, bool]:
        """Yahoo eligibility if pasted, else a guess from the NBA feed. Second value: is it Yahoo's."""
        yahoo = _find(self._yahoo, name)
        if yahoo:
            return yahoo, True
        guess = FEED_POSITIONS.get(self._feed_positions.get(self.player_id(name) or -1, ""), "")
        return guess or str(fallback or ""), False

    def injury(self, name: str) -> dict | None:
        return _find(self.injuries, name)

    def free_agent(self, name: str) -> dict | None:
        """His row on the pasted Yahoo free-agent list, if there is one."""
        return _find(self.free_agents, name)

    def rostered_by(self, name: str) -> str | None:
        """The fantasy team that owns him on the pasted rosters, if any."""
        return _find(self._rostered, name)

    def history(self, name: str) -> np.ndarray | None:
        """His latest games as rows of ``matchup.STATS``, for drawing a night from."""
        key = name_key(name)
        if key not in self._history:
            player_id = self.player_id(name)
            games = _stack(
                self._games(self.older_logs, player_id),
                self._games(self.last_logs, player_id),
                self._games(self.logs, player_id),
            )
            games = games.tail(HISTORY_GAMES).rename(columns={"min": "mp"})
            self._history[key] = games[list(matchup.STATS)].to_numpy(dtype=float) if len(games) else None
        return self._history[key]

    def season_games(self, name: str) -> pd.DataFrame:
        """His games this season, oldest first."""
        return self._games(self.logs, self.player_id(name))

    def games_on_file(self, name: str) -> int:
        player_id = self.player_id(name)
        return len(self._games(self.last_logs, player_id)) + len(self._games(self.logs, player_id))

    def actual(self, name: str, day: str) -> np.ndarray | None:
        """What he really did on ``day``, or ``None`` if no game is on file."""
        games = self._games(self.logs, self.player_id(name))
        played = games.loc[games["date"] == day].rename(columns={"min": "mp"})
        return played[list(matchup.STATS)].iloc[0].to_numpy(dtype=float) if len(played) else None

    def play_chance(self, name: str, game: dict, override: str | None = None) -> tuple[float, str]:
        """Chance he plays this game, and the reason if it is not certain."""
        if override == "out":
            return 0.0, "you marked him out"
        if override == "in":
            return 1.0, "you marked him in"
        chance = 1.0
        reasons = []
        listed = self.injury(name)
        if listed:
            chance = injuries.play_chance(
                listed["status"], listed["return_date"], listed["reported"], date.fromisoformat(game["date"])
            )
            if chance < 1.0:
                reasons.append(f"{listed['status']}{' · ' + listed['part'] if listed['part'] else ''}")
        if game.get("b2b"):
            rest = self.context.rest_chance(self.player_id(name))
            if rest < 0.97:
                reasons.append(f"sat {round((1 - rest) * 100)}% of second nights")
            chance *= rest
        return chance, " · ".join(reasons)

    def game_line(self, name: str, game: dict, score: bool = True) -> dict | None:
        """Tonight's line: his next-game line moved for this opponent and venue."""
        base = self.line_for(name)
        if base is None:
            return None
        group = self._groups.get(self.player_id(name) or -1, "F")
        line = self.context.adjust(base, game["opp"], bool(game["home"]), group)
        if score:
            line.update(daily.score_lines([line], self.baselines)[0])
        return line

    def _index_players(self) -> dict[str, int]:
        """Exact name first. First-and-last only where that pair is one player."""
        ids: dict[str, int] = {}
        loose: dict[str, list[int]] = {}
        for row in self.players.itertuples():
            ids[name_key(row.player_name)] = int(row.player_id)
            loose.setdefault(_loose_key(row.player_name), []).append(int(row.player_id))
        for key, matches in loose.items():
            if len(matches) == 1:
                ids.setdefault(f"~{key}", matches[0])
        return ids

    def player_id(self, name: str) -> int | None:
        exact = self._ids.get(name_key(name))
        return exact if exact is not None else self._ids.get(f"~{_loose_key(name)}")

    def team_of(self, name: str, fallback: object = "") -> str:
        """Current NBA team from the roster feed, else the team on the season line."""
        team = self._teams.get(self.player_id(name) or -1, "")
        return team or slate.nba_team(fallback)

    def _games(self, logs: pd.DataFrame, player_id: int | None) -> pd.DataFrame:
        if player_id is None or logs.empty:
            return logs.iloc[0:0]
        return logs.loc[logs["player_id"] == player_id].sort_values(["date", "game_id"], kind="mergesort")

    def line_for(self, name: str) -> dict | None:
        """Expected next-game line with its 12-cat z, or ``None`` with no NBA sample."""
        key = name_key(name)
        if key in self._lines:
            return self._lines[key]
        player_id = self.player_id(name)
        last = self._games(self.last_logs, player_id)
        row = _find(self._anchors, name)
        anchor = daily.anchor_from_row(row) if row is not None else None
        basis = "season line"
        # The three-season outlook beat last season's line on a season it had not seen.
        seen = self._outlook.get(player_id) if player_id is not None else None
        if seen is not None:
            anchor = {stat: float(seen[stat]) for stat in ("mp", "dd", *daily.STAT_COLUMNS)}
            basis = "3-season outlook"
        if anchor is None and len(last) >= MIN_ANCHOR_GAMES:
            anchor = daily.anchor_from_games(last)
            basis = "last season"
        older = self._games(self.older_logs, player_id)
        if anchor is None and len(older) >= MIN_ANCHOR_GAMES:
            anchor = daily.anchor_from_games(older)
            basis = f"{older['season'].iloc[-1]} season, missed last year"
        line = daily.project_line(anchor, self._games(self.logs, player_id))
        if line is not None:
            line.update(daily.score_lines([line], self.baselines)[0])
            if line["games"]:
                basis = f"{line['games']} g this season"
            line["basis"] = basis
            current = self.team_of(name)
            line["new_team"] = bool(len(last) and current and slate.nba_team(last["team"].iloc[-1]) != current)
        self._lines[key] = line
        return line

    @property
    def scout(self) -> scouting.Scout:
        """Matchup detail. Reads the past seasons in ``history/`` on first use only."""
        if self._scout is None:
            history = self.feed_dir / nba_feed.HISTORY_DIR.name
            older = [pd.read_csv(path, dtype={"game_id": str}) for path in sorted(history.glob("gamelogs_*.csv"))]
            self._scout = scouting.Scout(
                self.logs,
                self.last_logs,
                _stack(*older) if older else pd.DataFrame(),
                self._groups,
                nba_feed.SEASON,
                nba_feed.LAST_SEASON,
            )
        return self._scout

    def scout_detail(self, name: str, opp: str, home: bool) -> dict:
        return self.scout.detail(self.player_id(name), slate.nba_team(opp), home)

    def logs_through(self) -> str | None:
        for logs in (self.logs, self.last_logs):
            if not logs.empty:
                return str(logs["date"].max())
        return None


def load(feed_dir: Path | None = None) -> SeasonData:
    """Read the feed once and again only when a file on disk changes."""
    target = feed_dir or nba_feed.FEED_DIR
    stamp = tuple(
        sorted((path.name, path.stat().st_mtime_ns) for path in target.glob("*") if path.is_file())
    ) if target.exists() else ()
    key = (str(target), stamp)
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = SeasonData(target)
    return _CACHE[key]
