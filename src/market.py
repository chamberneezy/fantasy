"""Yahoo listed prices and published sale averages for a $200 room.

Yahoo salary-cap listed values: basketball.fantasysports.yahoo.com prerank, 2025-26.
Yahoo / ESPN averages: Hashtag Basketball (Jokić Y! $85 / ESPN $70; 2024-25 Y! Wemby $70, Jokić $72).
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
}

# Published sale averages / expert $200 values. Missing means we only have Yahoo list.
YAHOO_AAV = {
    "nikola jokic": 85,  # Hashtag 2025-26 Y!
    "victor wembanyama": 70,  # Hashtag 2024-25 Y!; 2025-26 mocks $61
    "luka doncic": 72,
    "shai gilgeous-alexander": 68,
    "giannis antetokounmpo": 55,
    "pascal siakam": 30,
    "cooper flagg": 25,
    "jalen johnson": 49,
}
ESPN_AAV = {
    "nikola jokic": 70,
    "victor wembanyama": 74,
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


def _player_key(name: str) -> str:
    key = name_key(name)
    if key in YAHOO_LISTED or key in FANTRAX or key in YAHOO_AAV:
        return key
    loose = key
    for suffix in (" jr", " sr", " ii", " iii", " iv"):
        if loose.endswith(suffix):
            loose = loose[: -len(suffix)].strip()
    if loose in YAHOO_LISTED or loose in FANTRAX or loose in YAHOO_AAV:
        return loose
    parts = loose.split()
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
    """Stamp Yahoo / sale-average numbers. Unlisted names keep surplus dollars."""
    for player in players:
        found = quote(player["player_name"])
        if not found:
            continue
        player.update(found)
    return players
