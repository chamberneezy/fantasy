import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import backtest  # noqa: E402


def test_shrink_and_its_fitted_slope():
    chance = np.array([0.9, 0.1, 0.5])
    assert backtest.shrink(chance, 1.0) == pytest.approx(chance, abs=1e-6)
    pulled = backtest.shrink(chance, 0.5)
    assert 0.5 < pulled[0] < 0.9 and 0.1 < pulled[1] < 0.5 and pulled[2] == pytest.approx(0.5)
    rng = np.random.default_rng(0)
    truth = rng.uniform(0.05, 0.95, 20000)
    result = (rng.random(20000) < truth).astype(float)
    # A forecaster twice as sure as the truth on the log-odds scale needs a slope near 0.5.
    odds = np.log(truth / (1 - truth))
    overconfident = 1 / (1 + np.exp(-2 * odds))
    assert backtest.fit_slope(overconfident, result) == pytest.approx(0.5, abs=0.06)


def test_calibration_bins_report_what_happened():
    table = backtest.calibration(np.array([0.05, 0.05, 0.95, 0.95]), np.array([0.0, 1.0, 1.0, 1.0]))
    assert list(table["happened"]) == [0.5, 1.0]
    assert list(table["n"]) == [2, 2]


def test_double_doubles_are_recounted_from_the_stats():
    games = np.zeros((2, len(backtest.matchup.STATS)))
    at = backtest.matchup.AT
    games[0, at["pts"]], games[0, at["reb"]] = 12, 10
    games[1, at["pts"]], games[1, at["ast"]] = 30, 9
    assert list(backtest._dd(games)) == [1.0, 0.0]
