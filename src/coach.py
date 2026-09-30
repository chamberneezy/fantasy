"""Stay / Stretch / Pass numbers for a $200 room you type into."""

from __future__ import annotations

import re

from auction import typical_sale
from availability import name_key

ELITE_LISTED = 40
STAY_FACTOR = 1.05
STRETCH_FACTOR = 1.12
SECOND_STAR_FACTOR = 0.50

ALIASES = {
    "ad": "anthony davis",
    "ant": "anthony edwards",
    "bambi": "victor wembanyama",
    "bron": "lebron james",
    "cade": "cade cunningham",
    "curry": "stephen curry",
    "doncic": "luka doncic",
    "durant": "kevin durant",
    "embiid": "joel embiid",
    "flagg": "cooper flagg",
    "giannis": "giannis antetokounmpo",
    "haliburton": "tyrese haliburton",
    "halliburton": "tyrese haliburton",
    "joker": "nikola jokic",
    "jokic": "nikola jokic",
    "kat": "karl-anthony towns",
    "kawhi": "kawhi leonard",
    "kd": "kevin durant",
    "lebron": "lebron james",
    "luka": "luka doncic",
    "maxey": "tyrese maxey",
    "sga": "shai gilgeous-alexander",
    "shai": "shai gilgeous-alexander",
    "steph": "stephen curry",
    "tatum": "jayson tatum",
    "wemby": "victor wembanyama",
    "wembanyama": "victor wembanyama",
}


def leftover_max(budget_left: int, spots_left: int) -> int:
    if spots_left <= 0:
        return 0
    return max(0, int(budget_left) - (int(spots_left) - 1))


def stay_price(listed: int, budget_left: int, spots_left: int, owns_elite: bool, player: dict | None = None) -> int:
    ceiling = leftover_max(budget_left, spots_left)
    if ceiling <= 0:
        return 0
    price = max(1, int(listed))
    if owns_elite and price >= ELITE_LISTED:
        return max(1, min(ceiling, int(round(price * SECOND_STAR_FACTOR))))
    if player and player.get("stay_market"):
        return max(1, min(ceiling, int(player["stay_market"])))
    return max(1, min(ceiling, int(round(price * STAY_FACTOR))))


def stretch_price(listed: int, budget_left: int, spots_left: int, owns_elite: bool, player: dict | None = None) -> int:
    stay = stay_price(listed, budget_left, spots_left, owns_elite, player)
    ceiling = leftover_max(budget_left, spots_left)
    if ceiling <= 0:
        return 0
    price = max(1, int(listed))
    if owns_elite and price >= ELITE_LISTED:
        return stay
    if player and player.get("stretch_market"):
        return max(stay, min(ceiling, int(player["stretch_market"])))
    return max(stay, min(ceiling, int(round(price * STRETCH_FACTOR))))


def call_for(bid: int | None, stay: int, stretch: int) -> str:
    if bid is None:
        return "ready"
    if bid <= stay:
        return "stay"
    if bid <= stretch:
        return "stretch"
    return "pass"


def parse_feed(line: str) -> dict:
    """Turn `wemby 52` / `kd 40 me` / `wemby 72 sold` into a command."""
    tokens = [part for part in re.split(r"\s+", str(line).strip().lower()) if part]
    if not tokens:
        raise ValueError("Type a name. Example: wemby 52")
    action = "lookup"
    amount = None
    names: list[str] = []
    for token in tokens:
        cleaned = token.strip(",")
        if cleaned in {"sold", "gone", "taken"}:
            action = "sold"
            continue
        if cleaned in {"me", "mine", "got", "you"}:
            action = "me"
            continue
        if cleaned in {"keep", "dynasty"}:
            action = "keep"
            continue
        if cleaned == "locked":
            action = "locked"
            continue
        if cleaned.startswith("$") and cleaned[1:].isdigit():
            amount = int(cleaned[1:])
            continue
        if cleaned.isdigit():
            amount = int(cleaned)
            continue
        names.append(cleaned)
    if not names:
        raise ValueError("Type the player name first.")
    query = " ".join(names)
    return {"query": ALIASES.get(query, query), "amount": amount, "action": action}


def match_player(query: str, players: list[dict]) -> dict:
    needle = name_key(ALIASES.get(query, query))
    if not needle:
        raise ValueError("Type a player name.")
    scored: list[tuple[int, dict]] = []
    for player in players:
        key = name_key(player["player_name"])
        last = key.split()[-1] if key.split() else ""
        if key == needle or last == needle:
            return player
        if key.startswith(needle) or needle in key:
            scored.append((0 if key.startswith(needle) else 1, player))
        elif all(part in key for part in needle.split()):
            scored.append((2, player))
    if not scored:
        raise ValueError(f"No player matches {query}.")
    scored.sort(key=lambda item: (item[0], -(item[1].get("auction_value") or 0)))
    return scored[0][1]


def next_targets(
    available: list[dict],
    budget_left: int,
    spots_left: int,
    owns_elite: bool,
    skip: str = "",
    room: dict | None = None,
) -> list[dict]:
    from room import apply_room

    chosen = []
    for player in available:
        if player["player_name"] == skip:
            continue
        listed = int(player.get("yahoo_listed") or player.get("auction_value") or 1)
        if owns_elite and listed >= ELITE_LISTED:
            continue
        stay = stay_price(listed, budget_left, spots_left, owns_elite, player)
        stretch = stretch_price(listed, budget_left, spots_left, owns_elite, player)
        stay, stretch = apply_room(stay, stretch, listed, budget_left, spots_left, owns_elite, room)
        if stay <= 0:
            continue
        low, high = typical_sale(listed)
        chosen.append(
            {
                "player_name": player["player_name"],
                "listed": listed,
                "stay": stay,
                "typical_low": low,
                "typical_high": high,
            }
        )
        if len(chosen) == 3:
            break
    return chosen


def build_card(
    player: dict,
    bid: int | None,
    budget_left: int,
    spots_left: int,
    owns_elite: bool,
    available: list[dict],
    room: dict | None = None,
) -> dict:
    from room import apply_room, factor_for

    listed = int(player.get("yahoo_listed") or player.get("auction_value") or 1)
    fair_stay = stay_price(listed, budget_left, spots_left, owns_elite, player)
    fair_stretch = stretch_price(listed, budget_left, spots_left, owns_elite, player)
    stay, stretch = apply_room(fair_stay, fair_stretch, listed, budget_left, spots_left, owns_elite, room)
    factor = factor_for(listed, room)
    ceiling = leftover_max(budget_left, spots_left)
    if abs(factor - 1.0) >= 0.03 and not (owns_elite and listed >= ELITE_LISTED):
        room_uncapped = max(1, int(round(fair_stay * factor)))
        room_uncapped_stretch = max(room_uncapped, int(round(fair_stretch * factor)))
    else:
        room_uncapped = fair_stay
        room_uncapped_stretch = fair_stretch
    low = int(player.get("typical_low") or typical_sale(listed)[0])
    high = int(player.get("typical_high") or typical_sale(listed)[1])
    signal = call_for(bid, stay, stretch)
    price = stay if bid is None else int(bid)
    tax = max(0, price - stay)
    after = max(0, budget_left - price)
    seats = max(0, spots_left - 1)
    owns_after = owns_elite or listed >= ELITE_LISTED
    targets = next_targets(available, after, seats, owns_after, player["player_name"], room)
    second = owns_elite and listed >= ELITE_LISTED
    room_note = ""
    if room and abs(factor - 1.0) >= 0.03:
        room_note = f" Fair Stay ${fair_stay}. This room is at ${room_uncapped} ({factor:.2f}× on this tier)."
        if ceiling and ceiling < room_uncapped and not second:
            room_note += f" You can pay ${ceiling}."
    if spots_left <= 0:
        why = "Your roster is full. Log the sale if someone else got him."
    elif second:
        why = (
            f"You already have a ${ELITE_LISTED}+ player. Stay is ${stay} only if he is a steal. "
            f"Market on this name is ${low}–${high}. A second star wrecks the bench."
        )
    elif signal == "ready":
        if listed >= 50:
            computer = max(1, int(round(listed * 1.20)))
            why = (
                f"Yahoo lists ${listed}. Their computer stops at ${computer}. "
                f"In this 16-team, 10-seat room humans Stay ${stay}. Stretch ${stretch}. "
                f"$100 is still Stay.{room_note}"
            )
        else:
            why = (
                f"Yahoo lists ${listed}. Rooms pay ${low}–${high} (Hashtag / Fantrax / mocks). "
                f"Stay ${stay}. Stretch ${stretch}. Past that is a tax on the last seats.{room_note}"
            )
    elif signal == "stay":
        why = f"Pay this. After ${price} you have ${after} for {seats} seats.{room_note}"
    elif signal == "stretch":
        why = (
            f"${tax} over stay. You can, then ${after} for {seats} seats. "
            f"The next ${ELITE_LISTED}+ name is a pass.{room_note}"
        )
    else:
        why = (
            f"Pass. Tax ${tax} on a ${listed} name. "
            f"If you still pay ${price} you have ${after} for {seats} seats and you are in stars-and-scrubs.{room_note}"
        )
    if targets and signal != "pass":
        follow = ", ".join(f"{item['player_name']} stay ${item['stay']}" for item in targets[:2])
        why = f"{why} Next: {follow}."
    return {
        "player_name": player["player_name"],
        "positions": player.get("positions") or "",
        "listed": listed,
        "bid": bid,
        "stay": stay,
        "stretch": stretch,
        "fair_stay": fair_stay,
        "fair_stretch": fair_stretch,
        "room_stay": room_uncapped,
        "room_stretch": room_uncapped_stretch,
        "room_factor": round(factor, 3),
        "your_max": ceiling,
        "typical_low": low,
        "typical_high": high,
        "call": signal,
        "tax": tax,
        "after": after,
        "seats_after": seats,
        "second_star": second,
        "why": why,
        "next": targets,
    }
