"""Grade the weekly category forecasts on past seasons (src/backtest.py). Prints a report.

Fits on one season (missed-game chain, weekly form spread, log-odds shrink), then grades
every variant on later seasons it never saw.

    .venv/bin/python scripts/backtest_categories.py [--runs 2000] [--out report.md]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import backtest  # noqa: E402

HISTORY = ROOT / "data" / "season" / "history"
SEASONS = {
    "2023-24": HISTORY / "gamelogs_2023-24.csv",
    "2024-25": HISTORY / "gamelogs_2024-25.csv",
    "2025-26": ROOT / "data" / "season" / "gamelogs_2025-26.csv",
}
PRIOR = {"2023-24": HISTORY / "gamelogs_2022-23.csv", "2024-25": HISTORY / "gamelogs_2023-24.csv", "2025-26": HISTORY / "gamelogs_2024-25.csv"}
FIT = "2023-24"
TESTS = ("2024-25", "2025-26")
FORM_GRID = (0.0, 0.08, 0.12, 0.16, 0.20, 0.25)


def season_weeks(season: str) -> list[list[backtest.TeamWeek]]:
    logs = backtest.load_logs(SEASONS[season])
    prior = backtest.load_logs(PRIOR[season])
    teams, baselines = backtest.draft(prior)
    return [backtest.week_inputs(teams, prior, logs, monday, baselines) for monday in backtest.mondays(logs)]


def run(weeks: list[list[backtest.TeamWeek]], variant: backtest.Variant, runs: int) -> pd.DataFrame:
    frames = []
    for number, week in enumerate(weeks):
        if len(week) < 2:
            continue
        frame = backtest.forecasts(week, variant, runs, seed=1000 + number)
        frame["week"] = number
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def week_ci(frame: pd.DataFrame, column: str = "chance", draws: int = 400, seed: int = 7) -> tuple[float, float]:
    """95% interval of the Brier score, resampling whole weeks (pairs in a week share teams)."""
    rng = np.random.default_rng(seed)
    by_week = [group for _, group in frame.groupby("week")]
    values = []
    for _ in range(draws):
        sample = pd.concat([by_week[index] for index in rng.integers(0, len(by_week), len(by_week))])
        values.append(float(((sample[column] - sample["result"]) ** 2).mean()))
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    started = time.time()
    lines: list[str] = []

    def say(text: str = "") -> None:
        print(text, flush=True)
        lines.append(text)

    rates = backtest.miss_rates(backtest.load_logs(SEASONS[FIT]))
    say(f"# Category forecast backtest ({args.runs} runs per team-week)\n")
    say(f"Missed games, regulars in {FIT}: after playing {rates['miss_after_play']:.3f} (n {rates['cases_after_play']}), "
        f"after missing {rates['miss_after_miss']:.3f} (n {rates['cases_after_miss']}), plays after two misses {rates['plays_after_two_missed']:.3f}.\n")
    listed = rates["plays_after_two_missed"]
    weeks = {season: season_weeks(season) for season in (FIT, *TESTS)}
    say(f"Weeks: {', '.join(f'{season} {len(value)}' for season, value in weeks.items())}; 16 teams, 120 pairs x 12 categories a week.\n")

    today = backtest.Variant("today's pad (healthy players always play)", listed_plays=listed)
    dd_fix = backtest.Variant("+ double-doubles counted from the drawn stats", listed_plays=listed, dd_from_stats=True)
    misses = backtest.Variant("+ missed games in runs", listed_plays=listed, dd_from_stats=True,
                              miss_after_play=rates["miss_after_play"], miss_after_miss=rates["miss_after_miss"])

    say(f"## Fitting the weekly form spread on {FIT}")
    best_sd, best = 0.0, 1.0
    for sd in FORM_GRID:
        variant = backtest.Variant(f"form {sd}", listed_plays=listed, dd_from_stats=True,
                                   miss_after_play=rates["miss_after_play"], miss_after_miss=rates["miss_after_miss"], form_sd=sd)
        frame = run(weeks[FIT], variant, args.runs)
        brier = backtest.scores(frame["chance"].to_numpy(), frame["result"].to_numpy())["brier"]
        say(f"- form spread {sd:.2f}: Brier {brier:.4f}")
        if brier < best:
            best_sd, best = sd, brier
    say(f"Best: {best_sd:.2f}\n")
    form = backtest.Variant(f"+ shared weekly form (spread {best_sd:.2f})", listed_plays=listed, dd_from_stats=True,
                            miss_after_play=rates["miss_after_play"], miss_after_miss=rates["miss_after_miss"], form_sd=best_sd)

    say("## Out of sample")
    say("| Model | Season | Brier raw | 95% (weeks) | Log loss | Shrink fitted on 2023-24 | Brier shrunk | Pad's 0.6 shrink |")
    say("|---|---|---:|---|---:|---:|---:|---:|")
    results = {}
    for variant in (today, dd_fix, misses, form):
        fit_frame = run(weeks[FIT], variant, args.runs)
        slope = backtest.fit_slope(fit_frame["chance"].to_numpy(), fit_frame["result"].to_numpy())
        for season in TESTS:
            frame = run(weeks[season], variant, args.runs)
            chance, result = frame["chance"].to_numpy(), frame["result"].to_numpy()
            raw = backtest.scores(chance, result)
            low, high = week_ci(frame)
            shrunk = float(((backtest.shrink(chance, slope) - result) ** 2).mean())
            pad = float(((backtest.shrink(chance, 0.6) - result) ** 2).mean())
            say(f"| {variant.name} | {season} | {raw['brier']:.4f} | {low:.4f}–{high:.4f} | {raw['log_loss']:.4f} | {slope:.2f} | {shrunk:.4f} | {pad:.4f} |")
            results[(variant.name, season)] = (frame, slope)
    say("\nA coin is Brier 0.2500. Lower is better.\n")

    for variant in (today, form):
        frame = pd.concat([results[(variant.name, season)][0] for season in TESTS])
        slope = results[(variant.name, TESTS[0])][1]
        say(f"## Calibration, {variant.name}, {' + '.join(TESTS)}")
        say("| Said | Raw: happened | n | Shrunk: said | happened |")
        say("|---:|---:|---:|---:|---:|")
        raw = backtest.calibration(frame["chance"].to_numpy(), frame["result"].to_numpy())
        adjusted = backtest.calibration(backtest.shrink(frame["chance"].to_numpy(), slope), frame["result"].to_numpy())
        for index in range(len(raw)):
            shrunk_row = adjusted.iloc[index] if index < len(adjusted) else None
            say(f"| {raw['said'][index]:.2f} | {raw['happened'][index]:.2f} | {raw['n'][index]} | "
                f"{(shrunk_row['said'] if shrunk_row is not None else float('nan')):.2f} | {(shrunk_row['happened'] if shrunk_row is not None else float('nan')):.2f} |")
        say()
        say(f"### By category, {variant.name}")
        say("| Cat | Brier raw | Brier shrunk |")
        say("|---|---:|---:|")
        for category, group in frame.groupby("cat", sort=False):
            chance, result = group["chance"].to_numpy(), group["result"].to_numpy()
            say(f"| {category} | {((chance - result) ** 2).mean():.4f} | {((backtest.shrink(chance, slope) - result) ** 2).mean():.4f} |")
        say()
    say(f"Took {time.time() - started:.0f} s.")
    if args.out:
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
