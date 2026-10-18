"""Game context for a daily line: opponent, home court, back-to-backs.

Every factor is measured from NBA game logs and pulled toward 1, because one
season of one opponent is a small sample. On last season's games the opponent
and home factors moved a line by a few percent at most. The second night of a
back-to-back does not cut the minutes of those who play; it changes who plays,
so it is a chance of sitting, per player. Blowouts are not modelled: that
needs betting lines, which this pad does not pull.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from daily import STAT_COLUMNS

GROUPS = ("G", "F", "C")
# How much of a measured gap from league average is believed.
OPPONENT_TRUST = 0.75
# Minutes against one opponent by one position group before the sample counts half.
OPPONENT_HALF_SAMPLE = 2000.0
HOME_TRUST = 0.5
# Second nights a player's team must have had before his own rest habit counts half.
REST_HALF_SAMPLE = 8.0
FACTOR_FLOOR = 0.85
FACTOR_CEILING = 1.15


def position_group(positions: object) -> str:
    """Guard, forward or centre from the first listed position."""
    text = "" if positions is None else str(positions).strip().upper()
    for part in text.replace("/", "-").replace(",", "-").split("-"):
        if part in ("PG", "SG", "G"):
            return "G"
        if part in ("SF", "PF", "F"):
            return "F"
        if part == "C":
            return "C"
    return "F"


def _clamp(value: float) -> float:
    return min(FACTOR_CEILING, max(FACTOR_FLOOR, value))


class Context:
    """Opponent, home and rest factors read off a set of game logs."""

    def __init__(self, logs: pd.DataFrame, groups: dict[int, str] | None = None) -> None:
        self.opponent: dict[tuple[str, str, str], float] = {}
        self.home: dict[str, float] = {}
        self.away: dict[str, float] = {}
        self.rest: dict[int, float] = {}
        if logs.empty:
            return
        frame = logs.copy()
        lookup = groups or {}
        frame["group"] = [lookup.get(int(player_id), "F") for player_id in frame["player_id"]]
        self._opponents(frame)
        self._home(frame)
        self._back_to_backs(frame)

    def _opponents(self, frame: pd.DataFrame) -> None:
        columns = ["min", *STAT_COLUMNS]
        league = frame.groupby("group")[columns].sum()
        against = frame.groupby(["opp", "group"])[columns].sum()
        for (opp, group), row in against.iterrows():
            minutes = float(row["min"])
            base = league.loc[group]
            weight = OPPONENT_TRUST * minutes / (minutes + OPPONENT_HALF_SAMPLE)
            for stat in STAT_COLUMNS:
                league_rate = float(base[stat]) / float(base["min"]) if base["min"] else 0.0
                if not minutes or not league_rate:
                    continue
                ratio = (float(row[stat]) / minutes) / league_rate
                self.opponent[(str(opp), group, stat)] = _clamp(1.0 + weight * (ratio - 1.0))

    def _home(self, frame: pd.DataFrame) -> None:
        columns = ["min", *STAT_COLUMNS]
        sides = frame.groupby("home")[columns].sum()
        if 0 not in sides.index or 1 not in sides.index:
            return
        total = sides.sum()
        for stat in STAT_COLUMNS:
            league_rate = float(total[stat]) / float(total["min"]) if total["min"] else 0.0
            if not league_rate:
                continue
            for flag, table in ((1, self.home), (0, self.away)):
                ratio = (float(sides.loc[flag, stat]) / float(sides.loc[flag, "min"])) / league_rate
                table[stat] = _clamp(1.0 + HOME_TRUST * (ratio - 1.0))

    def _back_to_backs(self, frame: pd.DataFrame) -> None:
        """How often each player suits up for the second night, against his other games."""
        team_days = {
            team: {date.fromisoformat(day) for day in days}
            for team, days in frame.groupby("team")["date"].unique().items()
        }
        second_nights = {
            team: {day for day in days if day - timedelta(days=1) in days} for team, days in team_days.items()
        }
        days = [date.fromisoformat(value) for value in frame["date"]]
        frame = frame.assign(
            day=days,
            second=[day in second_nights[team] for day, team in zip(days, frame["team"])],
        )
        for (player_id, team), games in frame.groupby(["player_id", "team"]):
            first, last = games["day"].min(), games["day"].max()
            span = [day for day in team_days[team] if first <= day <= last]
            seconds = [day for day in span if day in second_nights[team]]
            others = len(span) - len(seconds)
            if not seconds or not others:
                continue
            played_seconds = int(games["second"].sum())
            played_others = len(games) - played_seconds
            other_rate = played_others / others
            if not other_rate:
                continue
            ratio = min(1.0, (played_seconds / len(seconds)) / other_rate)
            weight = len(seconds) / (len(seconds) + REST_HALF_SAMPLE)
            previous = self.rest.get(int(player_id), 1.0)
            self.rest[int(player_id)] = min(previous, 1.0 + weight * (ratio - 1.0))

    def rest_chance(self, player_id: int | None) -> float:
        """Chance a healthy player suits up for the second night of a back-to-back."""
        return self.rest.get(int(player_id), 1.0) if player_id is not None else 1.0

    def adjust(self, line: dict, opp: str, home: bool, group: str) -> dict:
        """The line against this opponent at this venue. Minutes stay put."""
        adjusted = dict(line)
        side = self.home if home else self.away
        for stat in STAT_COLUMNS:
            factor = self.opponent.get((opp, group, stat), 1.0) * side.get(stat, 1.0)
            adjusted[stat] = line[stat] * factor
        adjusted["fg_pct"] = adjusted["fgm"] / adjusted["fga"] if adjusted["fga"] else 0.0
        adjusted["ft_pct"] = adjusted["ftm"] / adjusted["fta"] if adjusted["fta"] else 0.0
        return adjusted
