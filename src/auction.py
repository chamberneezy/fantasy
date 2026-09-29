"""Turn 12-category value into a salary-cap price."""

from __future__ import annotations

from market import apply_market_prices

# Surplus only fills names Yahoo does not list. Market names keep Yahoo's $.
SURPLUS_POWER = 0.74
LISTED_STAR_CAP = 76


def assign_auction_values(
    players: list[dict],
    team_count: int,
    roster_size: int,
    budget: int,
) -> list[dict]:
    """Give each player a dollar price so the league spends every dollar.

    The top ``team_count * roster_size`` players share the budget. Everyone
    starts at $1. Leftover money is split by surplus above replacement, flattened
    so the top of the board looks like a Yahoo / Fantrax $200 room instead of
    two names eating a third of a roster budget.
    """
    ordered = sorted(
        players,
        key=lambda player: (-(player.get("total_value") or -999), player["player_name"]),
    )
    rostered = min(len(ordered), team_count * roster_size)
    if rostered == 0:
        return players

    replacement = 0.0
    if len(ordered) > rostered:
        replacement = float(ordered[rostered].get("total_value") or 0)
    surplus = [
        max(0.0, float(player.get("total_value") or 0) - replacement) ** SURPLUS_POWER
        for player in ordered[:rostered]
    ]
    total_surplus = sum(surplus) or 1.0
    leftover = team_count * max(0, budget - roster_size)
    raw = [1 + leftover * value / total_surplus for value in surplus]
    dollars = [max(1, int(round(value))) for value in raw]
    target = team_count * budget
    _balance(dollars, target, LISTED_STAR_CAP)

    prices = {player["player_name"]: 1 for player in ordered}
    for player, price in zip(ordered[:rostered], dollars):
        prices[player["player_name"]] = price
    for player in players:
        listed = prices[player["player_name"]]
        low, high = typical_sale(listed)
        player["auction_value"] = listed
        player["typical_low"] = low
        player["typical_high"] = high
    apply_market_prices(players)
    for player in players:
        listed = int(player.get("auction_value") or 1)
        if player.get("room_low") is None:
            low, high = typical_sale(listed)
            player["typical_low"] = low
            player["typical_high"] = high
        else:
            player["typical_low"] = int(player["room_low"])
            player["typical_high"] = int(player["room_high"])
    return players


def typical_sale(listed: int) -> tuple[int, int]:
    """What a name usually goes for in a $200 room, not the desperation max."""
    price = max(1, int(listed))
    return max(1, int(round(price * 0.88))), max(price, int(round(price * 1.10)))


def recommended_stay(listed: int, leftover_max: int) -> int:
    """Pay market, not every leftover dollar."""
    if leftover_max <= 0:
        return 0
    return max(1, min(leftover_max, int(round(max(1, listed) * 1.05))))


def _balance(dollars: list[int], target: int, cap: int) -> None:
    if not dollars:
        return
    while sum(dollars) > target:
        index = max(range(len(dollars)), key=lambda i: (dollars[i], i))
        if dollars[index] <= 1:
            break
        dollars[index] -= 1
    while sum(dollars) < target:
        index = max(
            (i for i in range(len(dollars)) if dollars[i] < cap),
            key=lambda i: (dollars[i], -i),
            default=None,
        )
        if index is None:
            index = max(range(len(dollars)), key=lambda i: (dollars[i], -i))
        dollars[index] += 1
    for index, value in enumerate(dollars):
        if value > cap:
            dollars[index] = cap
    while sum(dollars) < target:
        index = max(
            (i for i in range(len(dollars)) if dollars[i] < cap),
            key=lambda i: (-dollars[i], i),
            default=None,
        )
        if index is None:
            break
        dollars[index] += 1


def cap_bid(auction_value: int, budget_left: int, spots_left: int) -> int:
    """Most you can pay and still fill the roster at $1 a seat."""
    if spots_left <= 0:
        return 0
    reserve = max(0, spots_left - 1)
    return max(1, min(int(auction_value), budget_left - reserve))


def estimate_dd(pts: float, reb: float, ast: float) -> float:
    """Rough double-doubles a night from the three counting stats that make them."""
    top, second, _ = sorted((pts, reb, ast), reverse=True)
    if second < 5:
        return 0.02
    return round(min(0.85, max(0.0, (top - 8) * (second - 5) / 90)), 3)
