# Category forecast backtest (2000 runs per team-week)

Missed games, regulars in 2023-24: after playing 0.056 (n 12088), after missing 0.618 (n 1771), plays after two misses 0.255.

Weeks: 2023-24 24, 2024-25 24, 2025-26 24; 16 teams, 120 pairs x 12 categories a week.

## Fitting the weekly form spread on 2023-24
- form spread 0.00: Brier 0.1771
- form spread 0.08: Brier 0.1769
- form spread 0.12: Brier 0.1768
- form spread 0.16: Brier 0.1768
- form spread 0.20: Brier 0.1770
- form spread 0.25: Brier 0.1774
Best: 0.16

## Out of sample
| Model | Season | Brier raw | 95% (weeks) | Log loss | Shrink fitted on 2023-24 | Brier shrunk | Pad's 0.6 shrink |
|---|---|---:|---|---:|---:|---:|---:|
| today's pad (healthy players always play) | 2024-25 | 0.1784 | 0.1716–0.1848 | 0.5725 | 0.68 | 0.1746 | 0.1747 |
| today's pad (healthy players always play) | 2025-26 | 0.1785 | 0.1708–0.1874 | 0.5648 | 0.68 | 0.1741 | 0.1742 |
| + double-doubles counted from the drawn stats | 2024-25 | 0.1786 | 0.1718–0.1849 | 0.5730 | 0.68 | 0.1748 | 0.1749 |
| + double-doubles counted from the drawn stats | 2025-26 | 0.1784 | 0.1710–0.1873 | 0.5646 | 0.68 | 0.1741 | 0.1742 |
| + missed games in runs | 2024-25 | 0.1769 | 0.1715–0.1825 | 0.5449 | 0.90 | 0.1763 | 0.1789 |
| + missed games in runs | 2025-26 | 0.1795 | 0.1739–0.1861 | 0.5498 | 0.90 | 0.1789 | 0.1817 |
| + shared weekly form (spread 0.16) | 2024-25 | 0.1761 | 0.1708–0.1814 | 0.5416 | 0.99 | 0.1761 | 0.1803 |
| + shared weekly form (spread 0.16) | 2025-26 | 0.1787 | 0.1735–0.1848 | 0.5477 | 0.99 | 0.1787 | 0.1832 |

A coin is Brier 0.2500. Lower is better.

## Calibration, today's pad (healthy players always play), 2024-25 + 2025-26
| Said | Raw: happened | n | Shrunk: said | happened |
|---:|---:|---:|---:|---:|
| 0.04 | 0.12 | 9482 | 0.04 | 0.08 |
| 0.15 | 0.25 | 5769 | 0.15 | 0.17 |
| 0.25 | 0.32 | 5634 | 0.25 | 0.27 |
| 0.35 | 0.40 | 5656 | 0.35 | 0.35 |
| 0.45 | 0.47 | 5760 | 0.45 | 0.46 |
| 0.55 | 0.54 | 5957 | 0.55 | 0.56 |
| 0.65 | 0.62 | 6113 | 0.65 | 0.66 |
| 0.75 | 0.69 | 6256 | 0.75 | 0.75 |
| 0.85 | 0.77 | 6512 | 0.85 | 0.85 |
| 0.97 | 0.90 | 11981 | 0.96 | 0.93 |

### By category, today's pad (healthy players always play)
| Cat | Brier raw | Brier shrunk |
|---|---:|---:|
| MIN | 0.1770 | 0.1665 |
| FG% | 0.2159 | 0.2126 |
| FT% | 0.2079 | 0.2072 |
| 3PM | 0.1598 | 0.1561 |
| PTS | 0.1848 | 0.1763 |
| REB | 0.1542 | 0.1482 |
| AST | 0.1672 | 0.1613 |
| STL | 0.1903 | 0.1905 |
| BLK | 0.1699 | 0.1671 |
| TO | 0.1897 | 0.1844 |
| PF | 0.1766 | 0.1738 |
| DD | 0.1478 | 0.1485 |

## Calibration, + shared weekly form (spread 0.16), 2024-25 + 2025-26
| Said | Raw: happened | n | Shrunk: said | happened |
|---:|---:|---:|---:|---:|
| 0.05 | 0.08 | 4302 | 0.06 | 0.08 |
| 0.15 | 0.17 | 5739 | 0.15 | 0.17 |
| 0.25 | 0.27 | 6847 | 0.25 | 0.27 |
| 0.35 | 0.36 | 7582 | 0.35 | 0.36 |
| 0.45 | 0.47 | 7907 | 0.45 | 0.47 |
| 0.55 | 0.55 | 8209 | 0.55 | 0.55 |
| 0.65 | 0.66 | 8002 | 0.65 | 0.66 |
| 0.75 | 0.74 | 7775 | 0.75 | 0.74 |
| 0.85 | 0.84 | 6853 | 0.85 | 0.84 |
| 0.95 | 0.94 | 5904 | 0.95 | 0.94 |

### By category, + shared weekly form (spread 0.16)
| Cat | Brier raw | Brier shrunk |
|---|---:|---:|
| MIN | 0.1642 | 0.1642 |
| FG% | 0.2160 | 0.2159 |
| FT% | 0.2071 | 0.2071 |
| 3PM | 0.1589 | 0.1588 |
| PTS | 0.1792 | 0.1791 |
| REB | 0.1546 | 0.1546 |
| AST | 0.1659 | 0.1659 |
| STL | 0.1931 | 0.1932 |
| BLK | 0.1710 | 0.1709 |
| TO | 0.1903 | 0.1902 |
| PF | 0.1798 | 0.1798 |
| DD | 0.1489 | 0.1490 |

Took 54 s.

## Mid-week (added 15 Nov 2026)

Same league and seasons. The days already played are fixed, the rest forecast. Slope fitted on 2023-24, Brier on 2024-25 + 2025-26:

| Forecast on | Fitted slope | Raw | Slope 0.6 (old rule) | Slope 0.68 | Fitted slope |
|---|---:|---:|---:|---:|---:|
| Monday | 0.68 | 0.1784 | 0.1745 | 0.1744 | 0.1744 |
| Thursday | 0.83 | 0.1187 | 0.1197 | 0.1185 | 0.1178 |
| Saturday | 0.91 | 0.0735 | 0.0760 | 0.0746 | 0.0733 |

The rule adopted, `matchup.fair_chance`: slope = 1 − 0.32 × (days left ÷ 7). That gives 0.68, 0.82 and 0.91.

The structural fixes (missed games in runs, a shared weekly form) give calibrated raw chances (fitted slope 0.99). Their Brier is no better than today's model with the slope (0.176–0.179 vs 0.174), so they were not adopted. The double-double recount changed nothing measurable.
