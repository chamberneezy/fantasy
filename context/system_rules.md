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

Confirmed Yahoo snapshot for **3. Pilsner Fantasy Liga** (id 51867): 16 teams, H2H categories, roster PG/SG/SF/PF/C + 5 BN, cats MIN, FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO, PF, DD. Daily lineup deadline. 4 adds per week. No waivers. No Yahoo trades (commissioner review). 4 divisions. Playoffs 8 teams, weeks 18–20. Not a Yahoo cash/prize league. 3rd league has no dynasty keepers this draft. Default draft dollars $200 unless the team row on the Pilsner DD table says otherwise.

## Auction price

Listed dollars follow Yahoo's 2025-26 salary-cap board, then Hashtag Yahoo/ESPN sale averages and FantraxHQ recommended $. Stay is the median of those sources, never below Yahoo list. Stretch is the high sale average. Names Yahoo does not list stay on surplus. Draft dollars are the salary-cap budget (default $200, floor $160, ceiling $240). They are not a payment. The live helper is `/helper` and does not share a session with the `/draft` mock. On `/helper`, pick a name, then Sold or Me. Keep is your dynasty at Yahoo list. Locked is another team's dynasty. Dynasty logs do not teach room heat. The dollar starts at Stay if you do not type one. Logged hammers update Stay by tier: one sale is noise, two in the same bucket move this room's Stay. Yahoo list and fair Stay stay on the card. `/lab` runs headless rooms with mixed bots (Stay–Stretch, plus a heat tail over Stretch) and answers sale scenarios.
