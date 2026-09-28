"""Learn Stay / Stretch from hammers you log. One sale does not reprice the board."""

from __future__ import annotations

from statistics import median

from coach import leftover_max, stay_price, stretch_price
from draft_room import DEFAULT_BUDGET, ROSTER_SIZE, TEAM_COUNT

STAR = 40
MID = 20
MIN_SAMPLES = 2
HEAT_FLOOR = 0.85
HEAT_CEILING = 1.22


def bucket(listed: int) -> str:
    price = max(1, int(listed))
    if price >= STAR:
        return "star"
    if price >= MID:
        return "mid"
    return "end"


def fair_marks(player: dict | None, listed: int, budget: int = DEFAULT_BUDGET) -> tuple[int, int]:
    stay = stay_price(listed, budget, ROSTER_SIZE, False, player)
    stretch = stretch_price(listed, budget, ROSTER_SIZE, False, player)
    return stay, stretch


def _sale_marks(item: dict, budget: int) -> tuple[int, int, int]:
    player = item.get("player") or {}
    listed = int(item.get("listed") or player.get("yahoo_listed") or item.get("auction_value") or 1)
    stay = int(item.get("fair_stay") or 0)
    stretch = int(item.get("fair_stretch") or 0)
    if stay <= 0 or stretch <= 0:
        stay, stretch = fair_marks(player or None, listed, budget)
    return listed, stay, stretch


def read_room(
    taken: list[dict],
    team_count: int = TEAM_COUNT,
    budget: int = DEFAULT_BUDGET,
    roster_size: int = ROSTER_SIZE,
) -> dict:
    samples: dict[str, list[float]] = {"star": [], "mid": [], "end": []}
    over_stretch_stars = 0
    spent = 0
    for item in taken:
        listed, stay, stretch = _sale_marks(item, budget)
        price = max(1, int(item.get("price") or 1))
        spent += price
        samples[bucket(listed)].append(price / max(1, stay))
        if listed >= STAR and price > stretch:
            over_stretch_stars += 1
    counts = {key: len(values) for key, values in samples.items()}
    factors = {key: 1.0 for key in samples}
    for key, values in samples.items():
        if len(values) < MIN_SAMPLES:
            continue
        heat = float(median(values))
        factors[key] = round(min(HEAT_CEILING, max(HEAT_FLOOR, heat)), 3)
    if over_stretch_stars >= 3 and factors["star"] > 1.0:
        lift = 1.0 + 0.45 * (factors["star"] - 1.0)
        factors["mid"] = round(min(HEAT_CEILING, max(factors["mid"], lift)), 3)
    seats_left = max(0, team_count * roster_size - len(taken))
    cash = team_count * budget - spent
    per_seat = round(cash / seats_left, 1) if seats_left else 0.0
    listening = any(count >= MIN_SAMPLES for count in counts.values())
    if seats_left and per_seat < 8 and len(taken) >= 8:
        note = f"League leftover is ${per_seat} a seat. The $1 endgame is close."
    elif listening and factors["star"] >= 1.08:
        note = f"Stars are going {factors['star']:.2f}× Stay. This room's Stay is marked up."
    elif listening and factors["star"] <= 0.92 and counts["star"] >= MIN_SAMPLES:
        note = f"Stars are going {factors['star']:.2f}× Stay. This room is cheaper than the tape."
    elif counts["star"] == 1:
        note = "One star sale is noise. A second $40+ hammer teaches the tier."
    else:
        note = "Stay is the published tape until two sales land in the same tier."
    return {
        "factors": factors,
        "counts": counts,
        "over_stretch_stars": over_stretch_stars,
        "cash": cash,
        "seats_left": seats_left,
        "per_seat": per_seat,
        "endgame": bool(seats_left and per_seat < 8 and len(taken) >= 8),
        "listening": listening,
        "note": note,
    }


def factor_for(listed: int, room: dict | None) -> float:
    if not room:
        return 1.0
    return float((room.get("factors") or {}).get(bucket(listed), 1.0))


def apply_room(
    stay: int,
    stretch: int,
    listed: int,
    budget_left: int,
    spots_left: int,
    owns_elite: bool,
    room: dict | None,
) -> tuple[int, int]:
    ceiling = leftover_max(budget_left, spots_left)
    if ceiling <= 0:
        return 0, 0
    if owns_elite and listed >= STAR:
        return stay, stretch
    factor = factor_for(listed, room)
    if abs(factor - 1.0) < 0.03:
        return stay, stretch
    room_stay = min(ceiling, max(1, int(round(stay * factor))))
    room_stretch = min(ceiling, max(room_stay, int(round(stretch * factor))))
    return room_stay, room_stretch
