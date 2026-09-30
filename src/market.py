"""Yahoo listed prices and published sale averages for a $200 room.

Yahoo salary-cap listed values: basketball.fantasysports.yahoo.com prerank, 2025-26
(checked 29 Sep 2026). $0 on that board is stored as $1 — the live minimum bid.
Humans can bid leftover-$1; Yahoo's computer stops at 120% of listed.
Yahoo / ESPN averages: Hashtag Basketball category auction table (28 Sep 2026).
Fantrax column: FantraxHQ 2025-26 recommended $200 values.
Mocks: NBC / Yahoo salary mock Jokić $69, SGA $62, Luka $62, Wemby $61.
"""

from __future__ import annotations

from statistics import median

from availability import name_key

# Yahoo official salary-cap listed $. That is what their computer maxes at 120%.
YAHOO_LISTED = {
    "victor wembanyama": 61,
    "nikola jokic": 60,
    "luka doncic": 59,
    "shai gilgeous-alexander": 57,
    "cade cunningham": 57,
    "tyrese maxey": 55,
    "anthony edwards": 54,
    "jayson tatum": 52,
    "giannis antetokounmpo": 50,
    "jalen johnson": 49,
    "donovan mitchell": 47,
    "tyrese haliburton": 46,
    "cooper flagg": 44,
    "scottie barnes": 42,
    "kevin durant": 42,
    "karl-anthony towns": 41,
    "jamal murray": 40,
    "josh giddey": 38,
    "trae young": 37,
    "austin reaves": 35,
    "amen thompson": 33,
    "domantas sabonis": 32,
    "lamelo ball": 32,
    "devin booker": 31,
    "alperen sengun": 31,
    "stephen curry": 31,
    "chet holmgren": 30,
    "evan mobley": 30,
    "jalen brunson": 30,
    "james harden": 29,
    "jaylen brown": 29,
    "bam adebayo": 28,
    "kawhi leonard": 27,
    "lauri markkanen": 26,
    "trey murphy": 26,
    "jalen duren": 26,
    "walker kessler": 25,
    "jalen williams": 25,
    "donovan clingan": 25,
    "brandon miller": 25,
    "derrick white": 24,
    "lebron james": 24,
    "jaren jackson": 24,
    "anthony davis": 23,
    "kon knueppel": 23,
    "desmond bane": 23,
    "deni avdija": 23,
    "kyrie irving": 22,
    "franz wagner": 22,
    "onyeka okongwu": 21,
    "keyonte george": 20,
    "paolo banchero": 19,
    "michael porter": 19,
    "nickeil alexander-walker": 18,
    "brandon ingram": 18,
    "naz reid": 18,
    "cameron boozer": 18,
    "damian lillard": 17,
    "joel embiid": 17,
    "dyson daniels": 17,
    "darius garland": 17,
    "pascal siakam": 17,
    "ivica zubac": 17,
    "dejounte murray": 16,
    "jarrett allen": 16,
    "zach edey": 16,
    "tyler herro": 16,
    "alex sarr": 16,
    "og anunoby": 15,
    "rudy gobert": 14,
    "de'aaron fox": 14,
    "payton pritchard": 13,
    "julius randle": 13,
    "paul george": 13,
    "stephon castle": 12,
    "mikal bridges": 12,
    "coby white": 11,
    "zion williamson": 10,
    "norman powell": 10,
    "nic claxton": 9,
    "immanuel quickley": 8,
    "jaden mcdaniels": 7,
    "ausar thompson": 6,
    "jabari smith": 5,
    "zach lavine": 5,
    "toumani camara": 5,
    "ja morant": 5,
    "kristaps porzingis": 4,
    "miles bridges": 4,
    "myles turner": 4,
    "josh hart": 4,
    "andrew nembhard": 4,
    "cj mccollum": 4,
    "john collins": 3,
    "kevin porter": 3,
    "kel'el ware": 16,
    "ryan rollins": 15,
    "vj edgecombe": 12,
    "matas buzelis": 12,
    "cedric coward": 12,
    "caleb wilson": 11,
    "day'ron sharpe": 9,
    "ty jerome": 9,
    "dylan harper": 6,
    "derik queen": 6,
    "andrew wiggins": 5,
    "aj dybantsa": 5,
    "isaiah hartenstein": 5,
    "jalen suggs": 5,
    "wendell carter": 5,
    "mark williams": 5,
    "jusuf nurkic": 4,
    "peyton watson": 4,
    "davion mitchell": 3,
    "ayo dosunmu": 3,
    "collin murray-boyles": 3,
    "sandro mamukelashvili": 3,
    "darryn peterson": 2,
    "jakob poeltl": 2,
    "khaman maluach": 2,
    "brandin podziemski": 2,
    "darius acuff": 2,
    "reed sheppard": 1,
    "neemias queta": 1,
    "aaron gordon": 1,
    "kyshawn george": 1,
    "jaime jaquez": 1,
    "keegan murray": 1,
    "fred vanvleet": 1,
    "jimmy butler": 1,
    "nikola vucevic": 1,
    "devin vassell": 1,
    "yaxel lendeborg": 1,
    "jalen green": 1,
    "cason wallace": 1,
    "tre jones": 1,
    "ajay mitchell": 1,
    "rj barrett": 1,
    "jrue holiday": 1,
    "maxime raynaud": 1,
    "collin gillespie": 1,
    "paul reed": 1,
    "tari eason": 1,
    "bobby portis": 1,
    "draymond green": 1,
    "christian braun": 1,
    "moussa diabate": 1,
    "saddiq bey": 1,
    "aaron nesmith": 1,
    "tobias harris": 1,
    "herbert jones": 1,
    "dillon brooks": 1,
    "pj washington": 1,
    "ace bailey": 1,
    "anthony black": 1,
    "daniss jenkins": 1,
    "jeremiah fears": 1,
    "kelly oubre": 1,
    "quentin grimes": 1,
    "morez johnson": 1,
    "grayson allen": 1,
    "collin sexton": 1,
    "bennedict mathurin": 1,
    "jerami grant": 1,
    "egor demin": 1,
    "brook lopez": 1,
    "yves missi": 1,
    "sam hauser": 1,
    "isaiah stewart": 1,
    "scoot henderson": 1,
    "daniel gafford": 1,
    "oso ighodaro": 1,
    "cameron johnson": 1,
    "santi aldama": 1,
    "jordan poole": 1,
    "dereck lively": 1,
    "kyle filipowski": 1,
    "de'andre hunter": 1,
    "mitchell robinson": 1,
    "julian champagnie": 1,
    "kyle kuzma": 1,
    "anfernee simons": 1,
    "andre drummond": 1,
    "deandre ayton": 1,
    "max strus": 1,
    "jaylen wells": 1,
    "rui hachimura": 1,
    "aaron wiggins": 1,
    "brayden burries": 1,
    "de'anthony melton": 1,
    "bilal coulibaly": 1,
    "scotty pippen": 1,
    "klay thompson": 1,
    "cam whitmore": 1,
    "obi toppin": 1,
    "miles mcbride": 1,
    "luguentz dort": 1,
    "tj mcconnell": 1,
    "keldon johnson": 1,
    "jalen smith": 1,
}

# Published sale averages / expert $200 values. Missing means we only have Yahoo list.
YAHOO_AAV = {
    "nikola jokic": 70,  # Hashtag category Y! avg, 28 Sep 2026
    "victor wembanyama": 70,
    "luka doncic": 72,
    "shai gilgeous-alexander": 68,
    "giannis antetokounmpo": 55,
    "pascal siakam": 30,
    "cooper flagg": 25,
    "jalen johnson": 49,
}
ESPN_AAV = {
    "nikola jokic": 83,
    "victor wembanyama": 80,
    "luka doncic": 68,
    "shai gilgeous-alexander": 66,
    "cooper flagg": 25,
    "pascal siakam": 30,
}
FANTRAX = {
    "nikola jokic": 74,
    "shai gilgeous-alexander": 72,
    "victor wembanyama": 67,
    "anthony edwards": 67,
    "luka doncic": 67,
    "trae young": 61,
    "devin booker": 61,
    "kevin durant": 60,
    "stephen curry": 60,
    "jalen williams": 59,
    "giannis antetokounmpo": 59,
    "donovan mitchell": 58,
    "jalen brunson": 58,
    "domantas sabonis": 52,
    "karl-anthony towns": 51,
    "james harden": 50,
    "jaylen brown": 49,
    "derrick white": 48,
    "mikal bridges": 47,
    "paolo banchero": 46,
    "franz wagner": 45,
    "cade cunningham": 44,
    "lauri markkanen": 43,
    "tyrese maxey": 37,
    "jaren jackson": 37,
    "de'aaron fox": 36,
    "ja morant": 36,
    "jamal murray": 34,
    "bam adebayo": 33,
    "anthony davis": 33,
    "austin reaves": 30,
    "alperen sengun": 29,
    "scottie barnes": 28,
    "cooper flagg": 28,
    "lamelo ball": 27,
    "desmond bane": 27,
    "lebron james": 25,
    "josh giddey": 25,
    "amen thompson": 24,
    "dyson daniels": 24,
    "kawhi leonard": 14,
}


def _samples(key: str) -> list[int]:
    values = []
    for table in (YAHOO_LISTED, YAHOO_AAV, ESPN_AAV, FANTRAX):
        if key in table and table[key] > 0:
            values.append(int(table[key]))
    return values


def _in_tables(key: str) -> bool:
    return any(key in table for table in (YAHOO_LISTED, FANTRAX, YAHOO_AAV, ESPN_AAV))


def _player_key(name: str) -> str:
    key = name_key(name)
    if _in_tables(key):
        return key
    loose = " ".join(key.replace(".", "").split())
    if _in_tables(loose):
        return loose
    stripped = loose
    for suffix in (" jr", " sr", " ii", " iii", " iv"):
        if stripped.endswith(suffix):
            stripped = stripped[: -len(suffix)].strip()
            break
    if _in_tables(stripped):
        return stripped
    parts = stripped.split()
    if len(parts) == 1:
        hits = [item for item in YAHOO_LISTED if item.split()[-1] == parts[0]]
        if len(hits) == 1:
            return hits[0]
    return key


def quote(player_name: str) -> dict | None:
    key = _player_key(player_name)
    samples = _samples(key)
    if not samples:
        return None
    listed = YAHOO_LISTED.get(key, min(samples))
    low, high = min(samples), max(samples)
    stay = max(listed, int(round(median(samples))))
    stretch = max(stay, high)
    return {
        "yahoo_listed": listed,
        "room_low": low,
        "room_high": high,
        "stay_market": stay,
        "stretch_market": stretch,
        "auction_value": listed,
    }


def apply_market_prices(players: list[dict]) -> list[dict]:
    """Stamp Yahoo / sale-average numbers.

    On a Yahoo-backed board, unlisted names are $1 endgame flyers. Surplus is
    only a starting guess; it must not turn a four-game two-way into a $30 mid.
    A synthetic pool with no Yahoo names keeps surplus so tests still spend the cap.
    """
    found_by_name = {player["player_name"]: quote(player["player_name"]) for player in players}
    stamped = sum(1 for found in found_by_name.values() if found)
    for player in players:
        found = found_by_name[player["player_name"]]
        if found:
            player.update(found)
            continue
        if not stamped:
            continue
        player["auction_value"] = 1
        player.pop("yahoo_listed", None)
        player.pop("stay_market", None)
        player.pop("stretch_market", None)
        player.pop("room_low", None)
        player.pop("room_high", None)
    return players
