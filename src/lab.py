"""Headless auctions: mixed bots, a report, and sale scenarios."""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from statistics import median

from auction import cap_bid
from coach import leftover_max, match_player, stay_price, stretch_price
from draft_room import DEFAULT_BUDGET, LAB_PATH, ROSTER_SIZE, SLOTS, TEAM_COUNT, first_open_slot

ELITE = 40
WATCH_LISTED = 24
DEFAULT_RUNS = 2000
MAX_RUNS = 10000
BOARD_SIZE = 220
TIGHT, ROOM, HEAT = "tight", "room", "heat"


def _piece(player: dict) -> dict:
    listed = int(player.get("yahoo_listed") or player.get("auction_value") or 1)
    stay = stay_price(listed, DEFAULT_BUDGET, ROSTER_SIZE, False, player)
    stretch = stretch_price(listed, DEFAULT_BUDGET, ROSTER_SIZE, False, player)
    return {
        "name": player["player_name"],
        "listed": listed,
        "stay": stay,
        "stretch": stretch,
        "value": float(player.get("total_value") or 0),
        "positions": player.get("positions") or "",
        "player": player,
    }


def _kinds(rng: random.Random, team_count: int, you: int) -> list[str]:
    pack = [TIGHT] * 7 + [ROOM] * 7 + [HEAT] * 1
    rng.shuffle(pack)
    kinds = [ROOM] * team_count
    slot = 0
    for index in range(team_count):
        if index == you:
            continue
        kinds[index] = pack[slot]
        slot += 1
    return kinds


def _bot_max(rng: random.Random, piece: dict, kind: str, budget: int, spots: int, owns_elite: bool) -> int:
    listed = piece["listed"]
    if spots <= 0:
        return 0
    if owns_elite and listed >= ELITE:
        steal = max(1, int(round(listed * 0.50)))
        return cap_bid(rng.randint(1, steal), budget, spots)
    if kind == TIGHT:
        lo, hi = listed, max(listed, piece["stay"])
    elif kind == ROOM:
        lo, hi = piece["stay"], max(piece["stay"], piece["stretch"])
    else:
        extra = max(3, int(round(piece["stretch"] * 0.14)))
        lo, hi = piece["stretch"], piece["stretch"] + extra
    if hi < lo:
        hi = lo
    return cap_bid(rng.randint(lo, hi), budget, spots)


def _wants(rng: random.Random, kind: str, listed: int, team: int, nominator: int) -> bool:
    if team == nominator:
        return True
    if listed >= ELITE:
        chance = {TIGHT: 0.28, ROOM: 0.48, HEAT: 0.82}[kind]
    elif listed >= 20:
        chance = {TIGHT: 0.42, ROOM: 0.52, HEAT: 0.40}[kind]
    else:
        chance = 0.32
    return rng.random() < chance


def _you_max(piece: dict, budget: int, spots: int, owns_elite: bool, policy: str) -> int:
    stay = stay_price(piece["listed"], budget, spots, owns_elite, piece["player"])
    stretch = stretch_price(piece["listed"], budget, spots, owns_elite, piece["player"])
    want = stretch if policy == "stretch" and not (owns_elite and piece["listed"] >= ELITE) else stay
    return cap_bid(want, budget, spots)


def _sell(ceilings: list[int], nominator: int, rng: random.Random) -> tuple[int, int]:
    high = max(ceilings)
    winners = [index for index, price in enumerate(ceilings) if price == high and price > 0]
    if not winners:
        return nominator, 1
    winner = nominator if nominator in winners else rng.choice(winners)
    second = 0
    for index, price in enumerate(ceilings):
        if index == winner:
            continue
        if price > second:
            second = price
    price = min(high, max(1, second + 1 if second else 1))
    return winner, price


def simulate_draft(
    pieces: list[dict],
    draft_slot: int = 5,
    policy: str = "stay",
    seed: int = 0,
    team_count: int = TEAM_COUNT,
    budget: int = DEFAULT_BUDGET,
) -> dict:
    rng = random.Random(seed)
    you = draft_slot - 1
    kinds = _kinds(rng, team_count, you)
    alive = list(range(min(len(pieces), BOARD_SIZE)))
    budgets = [budget] * team_count
    spots = [ROSTER_SIZE] * team_count
    elite = [False] * team_count
    yours: list[dict] = []
    watch: dict[str, dict] = {}
    filled: set[str] = set()
    labels = dict(SLOTS)
    for pick_number in range(team_count * ROSTER_SIZE):
        if not alive:
            break
        nominator = pick_number % team_count
        chosen = None
        for index in alive[:40]:
            piece = pieces[index]
            if spots[nominator] <= 0:
                break
            if nominator == you:
                if elite[you] and piece["listed"] >= ELITE:
                    continue
                if _you_max(piece, budgets[you], spots[you], elite[you], policy) <= 0:
                    continue
            elif leftover_max(budgets[nominator], spots[nominator]) < max(1, int(piece["listed"] * 0.70)):
                continue
            chosen = index
            break
        if chosen is None:
            chosen = alive[0]
        piece = pieces[chosen]
        ceilings = []
        for team in range(team_count):
            if spots[team] <= 0:
                ceilings.append(0)
            elif team == you:
                ceilings.append(_you_max(piece, budgets[you], spots[you], elite[you], policy))
            elif not _wants(rng, kinds[team], piece["listed"], team, nominator):
                ceilings.append(0)
            else:
                ceilings.append(_bot_max(rng, piece, kinds[team], budgets[team], spots[team], elite[team]))
        winner, price = _sell(ceilings, nominator, rng)
        if spots[winner] <= 0 or price > leftover_max(budgets[winner], spots[winner]):
            hopefuls = [
                team
                for team in range(team_count)
                if spots[team] > 0 and ceilings[team] >= 1 and ceilings[team] <= leftover_max(budgets[team], spots[team])
            ]
            if not hopefuls:
                alive.remove(chosen)
                continue
            winner = max(hopefuls, key=lambda team: ceilings[team])
            price = min(ceilings[winner], leftover_max(budgets[winner], spots[winner]))
        budgets[winner] -= price
        spots[winner] -= 1
        if piece["listed"] >= ELITE:
            elite[winner] = True
        alive.remove(chosen)
        sale = {
            "name": piece["name"],
            "price": price,
            "you": winner == you,
            "listed": piece["listed"],
            "positions": piece["positions"],
        }
        if winner == you:
            try:
                slot_id = first_open_slot(piece["positions"], filled)
            except ValueError:
                slot_id = next(slot for slot, _label in SLOTS if slot not in filled)
            filled.add(slot_id)
            sale["slot_id"] = slot_id
            sale["slot_label"] = labels[slot_id]
            yours.append(sale)
        if piece["listed"] >= WATCH_LISTED:
            watch[piece["name"]] = sale
    values = {piece["name"]: piece["value"] for piece in pieces}
    return {
        "yours": yours,
        "watch": watch,
        "leftover": budgets[you],
        "value": round(sum(values.get(item["name"], 0.0) for item in yours), 3),
        "stars": sum(1 for item in yours if item["listed"] >= ELITE),
    }


def _quantiles(values: list[int]) -> dict:
    if not values:
        return {"n": 0, "median": 0, "p25": 0, "p75": 0}
    ordered = sorted(values)
    n = len(ordered)

    def at(fraction: float) -> int:
        return ordered[min(n - 1, max(0, int(round((n - 1) * fraction))))]

    return {"n": n, "median": int(median(ordered)), "p25": at(0.25), "p75": at(0.75)}


def _iter_yours(draft: dict):
    for item in draft.get("yours") or []:
        if isinstance(item, dict):
            yield item
            continue
        name, price, *rest = item
        yield {"name": name, "price": price, "slot_id": rest[0] if rest else ""}


def _squad(drafts: list[dict]) -> list[dict]:
    rooms = max(1, len(drafts))
    counts = {slot_id: Counter() for slot_id, _label in SLOTS}
    paid = {slot_id: {} for slot_id, _label in SLOTS}
    for draft in drafts:
        for item in _iter_yours(draft):
            slot_id = item.get("slot_id")
            if slot_id not in counts:
                continue
            counts[slot_id][item["name"]] += 1
            paid[slot_id].setdefault(item["name"], []).append(int(item["price"]))
    rows = []
    for slot_id, label in SLOTS:
        top = counts[slot_id].most_common(4)
        if not top:
            rows.append({"id": slot_id, "label": label, "name": "", "p": 0, "price": 0, "alts": []})
            continue
        name, count = top[0]
        prices = paid[slot_id].get(name) or [0]
        rows.append(
            {
                "id": slot_id,
                "label": label,
                "name": name,
                "p": round(count / rooms, 3),
                "price": int(median(prices)),
                "alts": [
                    {"name": other, "p": round(other_count / rooms, 3)}
                    for other, other_count in top[1:]
                ],
            }
        )
    return rows


def _plays(stars: list[dict], you: dict) -> list[str]:
    lines = []
    if you.get("p_two_stars", 0) <= 0.08:
        lines.append("Two $40+ names almost never land if you listen to Stay. Take one star, then fill.")
    hot = [row for row in stars if row["listed"] >= 50 and row["p_over_stretch"] >= 0.18]
    if hot:
        names = ", ".join(row["name"].split()[-1] for row in hot[:3])
        verb = "run" if len(hot) > 1 else "runs"
        lines.append(f"{names} {verb} hot. If the offer is over Stretch, pass. The next star is still alive in most rooms.")
    first = next((row for row in stars if row["p_you"] >= 0.12), None)
    if first:
        lines.append(
            f"Your best shot at a first star is {first['name']} near ${first['median']}. "
            f"Stay ${first['stay']}. You get him in {round(first['p_you'] * 100)}% of rooms."
        )
    if you.get("median_leftover", 0) >= 20:
        lines.append(f"Median leftover is ${you['median_leftover']}. Spend it on the next Stay name, not a second star.")
    starters = [row for row in you.get("squad") or [] if row.get("name") and not str(row.get("id", "")).startswith("BN")]
    if len(starters) == 5:
        five = " / ".join(row["name"].split()[-1] for row in starters)
        lines.append(f"Most probable five: {five}. Those are the modal names at each slot, not one single room.")
    return lines


def build_report(drafts: list[dict], pieces: list[dict], meta: dict) -> dict:
    watch_names = [piece["name"] for piece in pieces if piece["listed"] >= WATCH_LISTED]
    stars = []
    for piece in pieces:
        if piece["listed"] < WATCH_LISTED:
            continue
        prices = []
        yours = []
        field = []
        for draft in drafts:
            sale = draft["watch"].get(piece["name"])
            if not sale:
                continue
            prices.append(sale["price"])
            (yours if sale["you"] else field).append(sale["price"])
        if not prices:
            continue
        over = sum(1 for price in prices if price > piece["stretch"])
        under = sum(1 for price in prices if price < piece["stay"])
        stars.append(
            {
                "name": piece["name"],
                "listed": piece["listed"],
                "stay": piece["stay"],
                "stretch": piece["stretch"],
                "p_you": round(len(yours) / len(drafts), 3),
                "p_under_stay": round(under / len(prices), 3),
                "p_over_stretch": round(over / len(prices), 3),
                **_quantiles(prices),
                "median_you": int(median(yours)) if yours else 0,
                "median_field": int(median(field)) if field else 0,
                "positions": piece["positions"],
            }
        )
    names = Counter(item["name"] for draft in drafts for item in draft["yours"])
    you = {
        "median_leftover": int(median([draft["leftover"] for draft in drafts])) if drafts else 0,
        "median_value": round(median([draft["value"] for draft in drafts]), 2) if drafts else 0,
        "p_one_star": round(sum(1 for draft in drafts if draft["stars"] >= 1) / max(1, len(drafts)), 3),
        "p_two_stars": round(sum(1 for draft in drafts if draft["stars"] >= 2) / max(1, len(drafts)), 3),
        "common": [{"name": name, "p": round(count / max(1, len(drafts)), 3)} for name, count in names.most_common(12)],
        "squad": _squad(drafts),
    }
    compact = []
    for draft in drafts:
        compact.append(
            {
                "left": draft["leftover"],
                "stars": draft["stars"],
                "yours": [[item["name"], item["price"], item.get("slot_id") or ""] for item in draft["yours"]],
                "watch": {name: [sale["price"], int(sale["you"])] for name, sale in draft["watch"].items()},
            }
        )
    return {
        "n": len(drafts),
        "draft_slot": meta.get("draft_slot", 5),
        "policy": meta.get("policy", "stay"),
        "budget": meta.get("budget", DEFAULT_BUDGET),
        "team_count": meta.get("team_count", TEAM_COUNT),
        "stars": stars,
        "you": you,
        "plays": _plays(stars, you),
        "watch_names": watch_names,
        "drafts": compact,
    }


def run_lab(
    players: list[dict],
    n: int = DEFAULT_RUNS,
    draft_slot: int = 5,
    policy: str = "stay",
    seed: int = 1,
) -> dict:
    count = max(20, min(MAX_RUNS, int(n)))
    if policy not in {"stay", "stretch"}:
        raise ValueError("Policy is stay or stretch.")
    if not 1 <= draft_slot <= TEAM_COUNT:
        raise ValueError(f"Nomination seat must be 1–{TEAM_COUNT}.")
    pieces = [_piece(player) for player in players]
    drafts = [
        simulate_draft(pieces, draft_slot=draft_slot, policy=policy, seed=seed + index)
        for index in range(count)
    ]
    return build_report(drafts, pieces, {"draft_slot": draft_slot, "policy": policy, "budget": DEFAULT_BUDGET, "team_count": TEAM_COUNT})


def scenario(report: dict, player_name: str, buyer: str = "room", price: int | None = None) -> dict:
    if not report or not report.get("drafts"):
        raise ValueError("Run the lab first.")
    names = [row["name"] for row in report.get("stars") or []]
    if not names:
        raise ValueError("The report has no stars yet.")
    dummy = [{"player_name": name, "auction_value": 1} for name in names]
    target = match_player(player_name, dummy)["player_name"]
    row = next((item for item in report["stars"] if item["name"] == target), None)
    if row is None:
        raise ValueError(f"No lab tape on {player_name}.")
    band = 6
    hits = []
    for draft in report["drafts"]:
        sale = draft["watch"].get(target)
        if not sale:
            continue
        paid, yours = sale
        if buyer == "me" and not yours:
            continue
        if buyer != "me" and yours:
            continue
        if price is not None and abs(int(paid) - int(price)) > band:
            continue
        hits.append(draft)
    if not hits:
        raise ValueError(f"No rooms matched {target} {buyer} {'' if price is None else f'near ${price}'}.".strip())
    next_names = Counter()
    leftovers = []
    for draft in hits:
        leftovers.append(draft["left"])
        after = False
        for item in _iter_yours(draft):
            if item["name"] == target:
                after = True
                continue
            if buyer != "me" or after:
                next_names[item["name"]] += 1
                break
    follow = [{"name": name, "p": round(count / len(hits), 3)} for name, count in next_names.most_common(6)]
    p_star = round(sum(1 for draft in hits if draft["stars"] >= (2 if buyer == "me" else 1)) / len(hits), 3)
    paid = price if price is not None else row["median_field"] if buyer != "me" else row["median_you"]
    if buyer == "me":
        tax = max(0, int(paid or 0) - row["stay"])
        why = (
            f"You took {target} at ${paid}. Stay was ${row['stay']}. "
            + (f"Tax ${tax}. The next $40+ name is a pass. " if tax else "That is Stay. ")
            + f"Median leftover in these rooms: ${int(median(leftovers))}."
        )
    else:
        over = int(paid or 0) > row["stretch"]
        why = (
            f"{target} went to the room at ${paid}. "
            + ("Over Stretch. You were right to pass. " if over else "Inside the room range. ")
            + f"You still land a $40+ name in {round(p_star * 100)}% of these rooms. "
            + (f"Next most often: {follow[0]['name']}." if follow else "Fill Stay names with the leftover.")
        )
    return {
        "player_name": target,
        "buyer": "You" if buyer == "me" else "Room",
        "price": paid,
        "listed": row["listed"],
        "stay": row["stay"],
        "stretch": row["stretch"],
        "matched": len(hits),
        "median_leftover": int(median(leftovers)) if leftovers else 0,
        "p_star": p_star,
        "next": follow,
        "squad": _squad(hits),
        "why": why,
    }


def save_report(report: dict | None, path: Path = LAB_PATH) -> None:
    if report is None:
        if path.exists():
            path.unlink()
        return
    path.write_text(json.dumps(report))


def load_report(path: Path = LAB_PATH) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())
