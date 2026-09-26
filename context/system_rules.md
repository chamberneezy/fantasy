# 9-Category H2H NBA Fantasy Rules

## Categories

Head-to-head matchups are scored across nine categories:

| Category | Key | Direction |
| --- | --- | --- |
| Points | PTS | Higher is better |
| Rebounds | REB | Higher is better |
| Assists | AST | Higher is better |
| Steals | STL | Higher is better |
| Blocks | BLK | Higher is better |
| Three-pointers made | 3PM | Higher is better |
| Field goal percentage | FG% | Higher is better, volume-weighted |
| Free throw percentage | FT% | Higher is better, volume-weighted |
| Turnovers | TO | Lower is better |

Counting-stat value is a z-score: `(stat - mean) / std_dev`.

Turnovers are inverted: `-1 * (stat - mean) / std_dev`.

Shooting percentages are volume-weighted before they are standardized:

```
FG_Impact = (FG% - Mean_FG%) * FGA
FT_Impact = (FT% - Mean_FT%) * FTA
```

`Mean_FG%` is the attempt-weighted pool mean, `sum(FG% * FGA) / sum(FGA)`. `Mean_FT%` uses FTA the same way.

## Roster composition

Each roster has 10 slots:

| Slot | Count |
| --- | --- |
| PG | 1 |
| SG | 1 |
| SF | 1 |
| PF | 1 |
| C | 1 |
| Util | 2 |
| Bench | 3 |
| **Total** | **10** |

## Dual-position boost

A player eligible at more than one position receives a **1.12x** multiplier on total weighted value. Single-position players stay at 1.0x. The boost is applied after z-scores are summed, and after any active punt categories have been dropped from that sum.

## Punt strategies

An active punt drops that category's z-score from the final value. The remaining categories are summed, then the dual-position multiplier is applied. Rankings are sorted by that custom weighted value, highest first.
