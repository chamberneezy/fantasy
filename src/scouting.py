"""Matchup detail for one player-game, read off the NBA game logs on disk.

What the opponent gives up to his position group, how fast and how well it
defends, what he has done against that team before, his home/away split, and
his role (usage, true shooting). Information only: none of it moves the
simulated week. ``context.py`` already folds a clamped opponent/home factor into
the line, and that measured to ~0.1% of error.

The free logs carry no offensive rebounds, so possessions are estimated as
FGA + 0.44·FTA + TO. Pace and defensive rating are therefore a little high in
absolute terms; the ranks are what to read.
"""

from __future__ import annotations

import pandas as pd

import context
from nba_feed import LOG_COLUMNS

# Team games each side must have this season before its numbers replace last season's.
CURRENT_TEAM_GAMES = 10
# His own games this season before his role and split come from this season alone.
CURRENT_PLAYER_GAMES = 10
LAST_MEETINGS = 3

# (label, stat, higher allowed is good for you). FG% / FT% are made over attempted.
OPPONENT_CATS = (
    ("PTS", "pts", True),
    ("REB", "reb", True),
    ("AST", "ast", True),
    ("3PM", "fg3m", True),
    ("STL", "stl", True),
    ("BLK", "blk", True),
    ("TO", "to", False),
    ("PF", "pf", False),
    ("FG%", ("fgm", "fga"), True),
    ("FT%", ("ftm", "fta"), True),
)
LINE_STATS = ("min", "pts", "reb", "ast", "fg3m", "stl", "blk", "to", "pf", "fgm", "fga", "ftm", "fta", "dd")
_SUMS = ["min", "fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "to", "pf"]


def _possessions(frame: pd.DataFrame) -> pd.Series:
    return frame["fga"] + 0.44 * frame["fta"] + frame["to"]


def _per_game(games: pd.DataFrame) -> dict | None:
    if games.empty:
        return None
    line = {stat: round(float(games[stat].mean()), 1) for stat in LINE_STATS if stat != "dd"}
    line["dd"] = round(float(games["dd"].mean()), 2)
    line["fg_pct"] = round(float(games["fgm"].sum() / games["fga"].sum()), 3) if games["fga"].sum() else None
    line["ft_pct"] = round(float(games["ftm"].sum() / games["fta"].sum()), 3) if games["fta"].sum() else None
    line["games"] = int(len(games))
    return line


def team_games(logs: pd.DataFrame) -> pd.DataFrame:
    """One row per team per game: summed box score, with the opponent's beside it."""
    if logs.empty:
        return pd.DataFrame(columns=["team", "game_id", "opp", *_SUMS, "poss"])
    sums = logs.groupby(["team", "game_id", "opp"], as_index=False)[_SUMS].sum()
    sums["poss"] = _possessions(sums)
    other = sums.rename(columns={column: f"opp_{column}" for column in [*_SUMS, "poss"]}).drop(columns="opp")
    other = other.rename(columns={"team": "opp"})
    return sums.merge(other, on=["opp", "game_id"], how="inner")


class Scout:
    """Matchup detail built from this season's logs, last season's, and older seasons."""

    def __init__(
        self,
        current: pd.DataFrame,
        last: pd.DataFrame,
        older: pd.DataFrame,
        groups: dict[int, str],
        season: str,
        last_season: str,
    ) -> None:
        self.groups = groups
        self.season = season
        self.last_season = last_season
        self.current = current
        self.last = last
        frames = [
            frame.assign(season=label)[[*LOG_COLUMNS, "season"]]
            for frame, label in ((current, season), (last, last_season))
            if len(frame)
        ]
        if len(older):
            frames.insert(0, older[[*LOG_COLUMNS, "season"]])
        self.everything = (
            pd.concat(frames, ignore_index=True).drop_duplicates(["player_id", "game_id"], keep="last")
            if frames
            else pd.DataFrame(columns=[*LOG_COLUMNS, "season"])
        )
        self.team_logs, self.team_basis = self._team_sample()
        self._allowed = self._allowed_by_group(self.team_logs)
        self._teams = self._team_table(self.team_logs)

    def _team_sample(self) -> tuple[pd.DataFrame, str]:
        """This season once every team has played enough, else last season."""
        if len(self.current):
            per_team = self.current.groupby("team")["game_id"].nunique()
            if len(per_team) >= 30 and int(per_team.min()) >= CURRENT_TEAM_GAMES:
                return self.current, self.season
        return self.last, self.last_season

    def _allowed_by_group(self, logs: pd.DataFrame) -> dict:
        """Per opponent and position group: rate given up, its ratio to league, and its rank of 30."""
        if logs.empty:
            return {}
        frame = logs.assign(group=[self.groups.get(int(pid), "F") for pid in logs["player_id"]])
        against = frame.groupby(["opp", "group"])[_SUMS].sum()
        league = frame.groupby("group")[_SUMS].sum()
        table: dict = {}
        for group in context.GROUPS:
            if group not in league.index:
                continue
            rows = against.xs(group, level="group")
            for label, stat, good_high in OPPONENT_CATS:
                if isinstance(stat, tuple):
                    made, tried = stat
                    rates = rows[made] / rows[tried].where(rows[tried] > 0)
                    base = league.loc[group, made] / league.loc[group, tried]
                else:
                    rates = rows[stat] / rows["min"].where(rows["min"] > 0)
                    base = league.loc[group, stat] / league.loc[group, "min"]
                # Rank 1 = the kindest matchup for you in this category.
                ranks = rates.rank(ascending=not good_high, method="min")
                for opp in rates.index:
                    rate = rates.loc[opp]
                    if pd.isna(rate) or not base:
                        continue
                    table[(str(opp), group, label)] = {
                        "ratio": round(float(rate / base) - 1.0, 3),
                        "rank": int(ranks.loc[opp]),
                    }
        return table

    def _team_table(self, logs: pd.DataFrame) -> dict:
        """Pace and defensive rating per team, with ranks (1 = fastest, 1 = softest defence)."""
        games = team_games(logs)
        if games.empty:
            return {}
        games["pace"] = (games["poss"] + games["opp_poss"]) / 2 * 48 / (games["min"] / 5)
        totals = games.groupby("team").agg(
            pace=("pace", "mean"), allowed=("opp_pts", "sum"), faced=("opp_poss", "sum"), games=("game_id", "nunique")
        )
        totals["drtg"] = 100 * totals["allowed"] / totals["faced"]
        pace_rank = totals["pace"].rank(ascending=False, method="min")
        drtg_rank = totals["drtg"].rank(ascending=False, method="min")
        return {
            str(team): {
                "pace": round(float(row.pace), 1),
                "pace_rank": int(pace_rank.loc[team]),
                "drtg": round(float(row.drtg), 1),
                "drtg_rank": int(drtg_rank.loc[team]),
                "games": int(row.games),
            }
            for team, row in totals.iterrows()
        }

    def _player_sample(self, player_id: int) -> tuple[pd.DataFrame, str]:
        mine = self.current.loc[self.current["player_id"] == player_id] if len(self.current) else self.current
        if len(mine) >= CURRENT_PLAYER_GAMES:
            return mine, self.season
        last = self.last.loc[self.last["player_id"] == player_id] if len(self.last) else self.last
        if len(mine):
            return pd.concat([last, mine], ignore_index=True), f"{self.last_season} + {len(mine)} g this season"
        return last, self.last_season

    def _role(self, games: pd.DataFrame, logs: pd.DataFrame) -> dict | None:
        """Usage rate and true shooting over his games, team totals from the same games."""
        if games.empty or not games["min"].sum():
            return None
        teams = logs.loc[logs["game_id"].isin(set(games["game_id"]))]
        totals = teams.groupby(["team", "game_id"], as_index=False)[["min", "fga", "fta", "to"]].sum()
        totals["used"] = _possessions(totals)
        joined = games[["team", "game_id"]].merge(totals, on=["team", "game_id"])
        team_minutes = float(joined["min"].sum())
        team_used = float(joined["used"].sum())
        used = float(_possessions(games).sum())
        shots = 2 * (float(games["fga"].sum()) + 0.44 * float(games["fta"].sum()))
        return {
            # Share of team possessions used while he was on the floor.
            "usage": round(100 * used * (team_minutes / 5) / (float(games["min"].sum()) * team_used), 1) if team_used else None,
            "ts": round(float(games["pts"].sum()) / shots, 3) if shots else None,
        }

    def detail(self, player_id: int | None, opp: str, home: bool) -> dict:
        """Everything the panel shows for one player against one opponent."""
        group = self.groups.get(int(player_id), "F") if player_id is not None else "F"
        allowed = [
            {"cat": label, **self._allowed[(opp, group, label)]}
            for label, _, _ in OPPONENT_CATS
            if (opp, group, label) in self._allowed
        ]
        result: dict = {
            "opp": opp,
            "group": group,
            "team_basis": self.team_basis,
            "early": self.team_basis != self.season,
            "allowed": allowed,
            "team": self._teams.get(opp),
            "history": None,
            "meetings": [],
            "splits": None,
            "role": None,
        }
        if player_id is None:
            return result
        mine = self.everything.loc[self.everything["player_id"] == player_id].sort_values("date")
        versus = mine.loc[mine["opp"] == opp]
        if len(versus):
            seasons = set(versus["season"])
            same = mine.loc[mine["season"].isin(seasons)]
            result["history"] = {
                "versus": _per_game(versus),
                "overall": _per_game(same),
                "seasons": sorted(str(season) for season in seasons),
            }
            result["meetings"] = [
                {
                    "date": str(row["date"]),
                    "home": bool(row["home"]),
                    "min": round(float(row["min"])),
                    "pts": int(row["pts"]),
                    "reb": int(row["reb"]),
                    "ast": int(row["ast"]),
                    "fg3m": int(row["fg3m"]),
                    "stl": int(row["stl"]),
                    "blk": int(row["blk"]),
                    "to": int(row["to"]),
                    "fg": f"{int(row['fgm'])}/{int(row['fga'])}",
                }
                for _, row in versus.tail(LAST_MEETINGS).iloc[::-1].iterrows()
            ]
        sample, basis = self._player_sample(int(player_id))
        if len(sample):
            result["splits"] = {
                "basis": basis,
                "home": _per_game(sample.loc[sample["home"] == 1]),
                "away": _per_game(sample.loc[sample["home"] == 0]),
                "tonight": "home" if home else "away",
            }
            role_logs = self.current if basis == self.season else pd.concat([self.last, self.current], ignore_index=True)
            role = self._role(sample, role_logs)
            if role:
                result["role"] = {**role, "basis": basis}
        return result
