"""News that changes a roster call: who is out, who gets his minutes, and what that does to their lines.

Info only. Nothing here ranks Mario's lineup or makes a move; it says what the
injury report means for his ten, his opponent's, and the players he could add.

How a bump is worked out, per teammate of the absent player:

1. Games on this team with him and without him, this season counted
   ``THIS_SEASON_WEIGHT`` times last season (a season counts only if he was
   on the team, so "without him" is the same roster).
2. Minutes: the difference without vs with him. Per-minute production: the
   ratio without vs with, per stat (more shots per minute, more assists...).
3. Both are shrunk toward "no change" by ``n / (n + SHRINK_GAMES)`` games
   without him, then applied to the teammate's current pad line.
4. The bumped line is scored on the 12 cats like any other line, so its value
   compares with Mario's own players.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd

import daily

# An absence matters when the player was in the rotation.
ROTATION_MINUTES = 20.0
# A teammate is listed when he played this many more minutes without him.
MINUTE_GAIN = 1.5
# Fewer games without him than this is noise.
MIN_GAMES_WITHOUT = 3
# This season's games count this many times last season's.
THIS_SEASON_WEIGHT = 3.0
# Report news this many days old.
FRESH_DAYS = 3
# An Out with no return date counts as this many days; longer absences stop adding weight.
UNDATED_DAYS = 14
DAYS_CAP = 21
# Games without him that count as much as the prior "no change". Replaying 2025-26
# (top named teammate per absence, earlier games only): 15 predicts +4.5 min on high
# calls against +3.7 real; 5 predicted +6.6. Per-minute production is untested, so it
# moves even more slowly.
SHRINK_GAMES = 15.0
RATE_SHRINK_GAMES = 30.0
# Per-minute ratios are kept inside this band.
RATE_FLOOR, RATE_CEILING = 0.85, 1.25
MAX_MINUTES = 40.0
# Certainty: the minutes jump measured against its own noise (Welch t), and the sample.
HIGH_T, HIGH_GAMES = 3.0, 8
MEDIUM_T, MEDIUM_GAMES = 2.0, 4
# How the top named teammate did in that replay, by certainty: share who gained minutes,
# share who gained 3+, average gain. Shown next to each call.
TRACK_RECORD = {
    "high": {"gained": 0.69, "gained_3": 0.52, "minutes": 3.7, "calls": 132},
    "medium": {"gained": 0.64, "gained_3": 0.46, "minutes": 2.2, "calls": 171},
    "low": {"gained": 0.57, "gained_3": 0.37, "minutes": 1.2, "calls": 172},
}
# A bumped free agent is "worth a look" when he beats Mario's weakest player by this much value.
ADD_MARGIN = 0.5
SHOWN_STATS = ("pts", "reb", "ast", "fg3m", "stl", "blk", "to")
COUNT_STATS = (*daily.STAT_COLUMNS, "dd")


def _group(rows: pd.DataFrame, weight: float) -> dict:
    """Weighted sums of one teammate's games, plus the raw minutes for the noise."""
    return {
        "w": len(rows) * weight,
        "n": len(rows),
        "min": float(rows["min"].sum()) * weight,
        "minutes": [float(value) for value in rows["min"]],
        **{stat: float(rows[stat].sum()) * weight for stat in COUNT_STATS},
    }


def _add(total: dict, part: dict) -> None:
    for key, value in part.items():
        if key == "minutes":
            total.setdefault(key, []).extend(value)
        else:
            total[key] = total.get(key, 0.0) + value


def minute_shift(seasons: list[tuple[pd.DataFrame, float]], team: str, out_id: int) -> dict[int, dict]:
    """Teammates' games with and without ``out_id`` on ``team``: weighted sums per side.

    ``seasons`` is ``[(logs, weight), ...]``. A season counts only if the absent
    player played for ``team`` in it. Each value has ``with`` and ``without``
    (sums, ``w`` the weighted game count, ``n`` the games), ``min_with``,
    ``min_without`` and ``games_without``.
    """
    totals: dict[int, dict] = {}
    for logs, weight in seasons:
        games = logs.loc[logs["team"] == team] if len(logs) else logs
        if games.empty or out_id not in set(games["player_id"]):
            continue
        with_him = set(games.loc[games["player_id"] == out_id, "game_id"])
        for player_id, rows in games.loc[games["player_id"] != out_id].groupby("player_id"):
            side = totals.setdefault(int(player_id), {"with": {}, "without": {}})
            _add(side["with"], _group(rows.loc[rows["game_id"].isin(with_him)], weight))
            _add(side["without"], _group(rows.loc[~rows["game_id"].isin(with_him)], weight))
    shift = {}
    for player_id, side in totals.items():
        together, apart = side["with"], side["without"]
        if together.get("w") and apart.get("w"):
            shift[player_id] = {
                **side,
                "min_with": together["min"] / together["w"],
                "min_without": apart["min"] / apart["w"],
                "games_without": int(apart["n"]),
            }
    return shift


def certainty(shift: dict) -> dict:
    """How sure the minutes jump is: Welch t on raw minutes, the sample, and a range for the jump."""
    together, apart = shift["with"]["minutes"], shift["without"]["minutes"]
    gain = shift["min_without"] - shift["min_with"]

    def spread(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((value - mean) ** 2 for value in values) / (len(values) - 1)

    error = math.sqrt(spread(together) / max(len(together), 1) + spread(apart) / max(len(apart), 1))
    t = gain / error if error else 0.0
    games = len(apart)
    if t >= HIGH_T and games >= HIGH_GAMES:
        level = "high"
    elif t >= MEDIUM_T and games >= MEDIUM_GAMES:
        level = "medium"
    else:
        level = "low"
    return {"level": level, "t": round(t, 1), "gain_low": round(gain - 1.96 * error, 1), "gain_high": round(gain + 1.96 * error, 1)}


def bumped_line(line: dict | None, shift: dict, baselines: dict, still_with: float = 1.0, minute_scale: float = 1.0) -> dict | None:
    """The teammate's current line with the shrunk minutes jump and per-minute ratios applied, scored.

    ``still_with``: the share of his current line that came from games with the absent
    player. If he has already been out all season, the bump is in the line already (0).
    """
    if not line or not line.get("mp"):
        return None
    together, apart = shift["with"], shift["without"]
    keep = still_with * apart["n"] / (apart["n"] + SHRINK_GAMES)
    rate_keep = still_with * apart["n"] / (apart["n"] + RATE_SHRINK_GAMES)
    minutes = min(line["mp"] + keep * minute_scale * (shift["min_without"] - shift["min_with"]), MAX_MINUTES)
    bumped = {"mp": minutes}
    for stat in daily.STAT_COLUMNS:
        rate_with = together[stat] / together["min"] if together["min"] else 0.0
        rate_without = apart[stat] / apart["min"] if apart["min"] else 0.0
        ratio = rate_without / rate_with if rate_with > 0 else 1.0
        ratio = 1.0 + rate_keep * (min(max(ratio, RATE_FLOOR), RATE_CEILING) - 1.0)
        bumped[stat] = float(line.get(stat, 0.0)) / float(line["mp"]) * minutes * ratio
    dd_gain = apart["dd"] / apart["w"] - together["dd"] / together["w"]
    bumped["dd"] = min(max(float(line.get("dd", 0.0)) + keep * dd_gain, 0.0), 1.0)
    bumped["fg_pct"] = bumped["fgm"] / bumped["fga"] if bumped["fga"] else 0.0
    bumped["ft_pct"] = bumped["ftm"] / bumped["fta"] if bumped["fta"] else 0.0
    bumped.update(daily.score_lines([bumped], baselines)[0])
    return bumped


def shown(line: dict | None) -> dict | None:
    """A line as the app shows it: minutes, the counting stats, the percentages and the 12-cat value."""
    if not line:
        return None
    row = {"min": round(float(line.get("mp", 0.0)), 1), **{stat: round(float(line.get(stat, 0.0)), 1) for stat in SHOWN_STATS}}
    row["fg_pct"] = round(float(line.get("fg_pct", 0.0)), 3)
    row["ft_pct"] = round(float(line.get("ft_pct", 0.0)), 3)
    row["value"] = round(float(line.get("value", 0.0)), 2)
    return row


def _absent(injury: dict, today: date) -> bool:
    """Out, or day-to-day with a return date at least two days off."""
    status = str(injury.get("status") or "")
    if status == "Out":
        return True
    back = str(injury.get("return_date") or "")
    return status == "Day-To-Day" and bool(back) and back >= (today + timedelta(days=2)).isoformat()


def _fresh(injury: dict, today: date) -> bool:
    reported = str(injury.get("reported") or "")
    return bool(reported) and reported >= (today - timedelta(days=FRESH_DAYS)).isoformat()


def _injury_row(name: str, injury: dict) -> dict:
    return {
        "player_name": name,
        "status": str(injury.get("status") or ""),
        "return_date": str(injury.get("return_date") or ""),
        "reported": str(injury.get("reported") or ""),
        "part": str(injury.get("part") or ""),
        "note": str(injury.get("note") or ""),
    }


def still_with(logs: pd.DataFrame, team: str, out_id: int, mate_id: int, anchor_games: float) -> float:
    """Share of the teammate's current line built on games with the absent player.

    The pad's line is this season's games on top of an anchor worth ``anchor_games``
    (last season's or the outlook's, nearly all with him). This season's games
    without him already carry the bump.
    """
    if not len(logs):
        return 1.0
    games = logs.loc[logs["team"] == team]
    with_him = set(games.loc[games["player_id"] == out_id, "game_id"])
    played = games.loc[games["player_id"] == mate_id, "game_id"]
    apart = sum(1 for game in played if game not in with_him)
    return 1.0 - apart / (len(played) + anchor_games)


def _season_minutes(logs: pd.DataFrame, player_id: int) -> float:
    rows = logs.loc[logs["player_id"] == player_id] if len(logs) else logs
    return float(rows["min"].mean()) if len(rows) else 0.0


def _owner(data, name: str, mine: set[str], free: dict | None) -> str:
    """mine / a fantasy team / free. All 16 rosters are on file (25 Oct 2026), so no roster means free."""
    if name.casefold() in mine:
        return "mine"
    return data.rostered_by(name) or "free"


def _days_out(injury: dict, today: date) -> int:
    """Days until the listed return; an undated Out counts as two weeks."""
    back = str(injury.get("return_date") or "")
    if not back:
        return UNDATED_DAYS
    return max((date.fromisoformat(back) - today).days, 1)


def _priority(chance: dict) -> tuple:
    """Gains Mario can use first (his own players, then pickups), weighted by minutes gained x days out."""
    usable = [gain for gain in chance["gains"] if gain["owner"] in ("mine", "free", "unlisted")]
    jump = max((gain["min_without"] - gain["min_with"] for gain in usable), default=0.0)
    return (not usable, -jump * min(chance["days_out"], DAYS_CAP))


def weakest(data, mine: list[str], protected: set[str]) -> dict | None:
    """Mario's lowest-value player who is not protected: the bar a pickup must clear."""
    rows = []
    for name in mine:
        if name.casefold() in protected:
            continue
        line = data.line_for(name)
        if line:
            rows.append({"player_name": name, "value": round(float(line.get("value", 0.0)), 2)})
    return min(rows, key=lambda row: row["value"]) if rows else None


def news(data, mine: list[str], opponent: str | None, today: date, protected: set[str] | None = None) -> dict:
    """Injury news sorted into what Mario can act on.

    ``mine``: his roster names. ``opponent``: this week's fantasy team, if known.
    ``protected``: names never offered as a drop (casefolded).
    """
    their = set(data.active_names(opponent)) if opponent else set()
    # Names are matched without case: the pad has "Tristan Da Silva", the feed "Tristan da Silva".
    mine_set = {name.casefold() for name in mine}
    bar = weakest(data, mine, protected or set())
    names_by_id = {int(row.player_id): str(row.player_name) for row in data.players.itertuples()}
    seasons = [(data.logs, THIS_SEASON_WEIGHT), (data.last_logs, 1.0)]
    my_out, their_out, chances = [], [], []
    seen = set()
    for key, injury in data.injuries.items():
        name = str(injury.get("player_name") or key)
        if name in seen or not _absent(injury, today):
            continue
        seen.add(name)
        if name.casefold() in mine_set:
            my_out.append(_injury_row(name, injury))
        elif name in their:
            their_out.append(_injury_row(name, injury))
        player_id = data.player_id(name)
        if player_id is None or not _fresh(injury, today):
            continue
        team = data.team_of(name)
        minutes = max(_season_minutes(data.logs, player_id), _season_minutes(data.last_logs, player_id))
        if not team or minutes < ROTATION_MINUTES:
            continue
        listed = []
        for mate_id, shift in minute_shift(seasons, team, player_id).items():
            mate = names_by_id.get(mate_id)
            if not mate or data.team_of(mate) != team:
                continue
            if shift["min_without"] - shift["min_with"] < MINUTE_GAIN or shift["games_without"] < MIN_GAMES_WITHOUT:
                continue
            listed.append((mate_id, mate, shift))
        # A game has 240 minutes: what the listed teammates gain cannot exceed what he leaves.
        jumps = sum(shift["min_without"] - shift["min_with"] for _, _, shift in listed)
        scale = min(1.0, minutes / jumps) if jumps else 1.0
        gains = []
        for mate_id, mate, shift in listed:
            free = data.free_agent(mate)
            owner = _owner(data, mate, mine_set, free)
            now = data.line_for(mate)
            share = still_with(data.logs, team, player_id, mate_id, daily.MINUTES_ANCHOR_GAMES)
            bumped = bumped_line(now, shift, data.baselines, share, scale)
            gain = {
                "player_name": mate,
                "owner": owner,
                "yahoo_status": str((free or {}).get("yahoo_status") or ""),
                "min_with": round(shift["min_with"], 1),
                "min_without": round(shift["min_without"], 1),
                "games_without": shift["games_without"],
                "certainty": certainty(shift),
                "already_in_line": round(1.0 - share, 2),
                "now": shown(now),
                "bumped": shown(bumped),
            }
            if bumped and bar and owner in ("free", "unlisted"):
                gain["beats_weakest"] = bool(bumped["value"] >= bar["value"] + ADD_MARGIN)
            gains.append(gain)
        if gains:
            gains.sort(key=lambda row: -(row["min_without"] - row["min_with"]))
            chances.append(
                {**_injury_row(name, injury), "team": team, "minutes": round(minutes, 1), "days_out": _days_out(injury, today), "gains": gains}
            )
    chances.sort(key=_priority)
    return {"mine_out": my_out, "opponent_out": their_out, "opportunities": chances, "weakest": bar, "track_record": TRACK_RECORD}
