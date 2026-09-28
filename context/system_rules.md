# Pilsner 12-category salary-cap draft

Head-to-head matchups use twelve categories:

| Category | Key | Direction |
| --- | --- | --- |
| Minutes | MIN | Higher is better |
| Field goal percentage | FG% | Higher is better, volume-weighted |
| Free throw percentage | FT% | Higher is better, volume-weighted |
| Three-pointers made | 3PM | Higher is better |
| Points | PTS | Higher is better |
| Rebounds | REB | Higher is better |
| Assists | AST | Higher is better |
| Steals | STL | Higher is better |
| Blocks | BLK | Higher is better |
| Turnovers | TO | Lower is better |
| Personal fouls | PF | Lower is better |
| Double-doubles | DD | Higher is better |

Counting-stat value is a z-score: `(stat - mean) / std_dev`.

Turnovers and personal fouls are inverted: `-1 * (stat - mean) / std_dev`.

Shooting percentages are volume-weighted before they are standardized.

## Draft

16 teams. Salary-cap auction. Default mock budget $200. Ten players each. A player costs at least $1.

## Roster

| Slot | Count |
| --- | --- |
| PG | 1 |
| SG | 1 |
| SF | 1 |
| PF | 1 |
| C | 1 |
| Bench | 5 |
| **Drafted** | **10** |

Injured list slots are in-season only and are not filled in the draft.

## Auction price

Listed dollars follow Yahoo's 2025-26 salary-cap board, then Hashtag Yahoo/ESPN sale averages and FantraxHQ recommended $. Stay is the median of those sources, never below Yahoo list. Stretch is the high sale average. Names Yahoo does not list stay on surplus. The live helper is `/helper` and does not share a session with the `/draft` mock. On `/helper`, pick a name, then Sold or Me. The dollar starts at Stay if you do not type one. Logged hammers update Stay by tier: one sale is noise, two in the same bucket move this room's Stay. Yahoo list and fair Stay stay on the card. `/lab` runs headless rooms with mixed bots (Stay–Stretch, plus a heat tail over Stretch) and answers sale scenarios.
