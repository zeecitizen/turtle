"""slip_calibrator.py — sample slippage in pips from calibrated distribution.

Two sampling modes available:
  - empirical_cdf:  random.choice from observed sorted distribution. Bounded by max observed.
  - lognormal:      zero-inflated lognormal fit. Naturally extrapolates the tail
                    (predicts realistic outliers beyond observed max).

Lognormal is theoretically sounder per quantitative best practices: slippage is
strictly non-negative with a long right tail, which lognormal models naturally.
The empirical CDF can never produce a value larger than the observed max — so it
underestimates true tail risk. The lognormal fit (built by fit_lognormal_slip.py)
predicts p99.9 = 22pips and p99.99 = 45pips for our distribution.

Default mode is `lognormal` (set via SLIP_MODE env var or set_mode() function).

Usage:
    from slip_calibrator import sample_slip_pips, set_mode
    set_mode('lognormal')   # or 'empirical_cdf'
    slip_pips = sample_slip_pips()
"""
from __future__ import annotations
import json, math, random, os
from pathlib import Path

CAL_PATH = Path(__file__).parent / "slip_calibration.json"

_CALIBRATION = None
_MODE = os.environ.get("SLIP_MODE", "lognormal")  # default: lognormal


def _load():
    global _CALIBRATION
    if _CALIBRATION is None:
        if not CAL_PATH.exists():
            raise FileNotFoundError(f"{CAL_PATH} missing — run build_slip_calibration.py first.")
        _CALIBRATION = json.loads(CAL_PATH.read_text(encoding="utf-8"))
    return _CALIBRATION


def set_mode(mode):
    """Set sampling mode: 'lognormal' or 'empirical_cdf'."""
    global _MODE
    if mode not in ("lognormal", "empirical_cdf"):
        raise ValueError(f"mode must be 'lognormal' or 'empirical_cdf', got {mode!r}")
    _MODE = mode


def get_mode():
    return _MODE


def sample_slip_pips():
    """Sample one slippage value (in pips). Always >= 0."""
    cal = _load()
    if _MODE == "empirical_cdf":
        dist = cal.get("sorted_distribution_pips", [])
        if not dist: return 0.0
        return random.choice(dist)
    # Default: lognormal (zero-inflated)
    fit = cal.get("lognormal_fit")
    if fit is None:
        # Fall back to empirical_cdf if lognormal_fit missing (e.g., haven't run fit_lognormal_slip.py yet)
        dist = cal.get("sorted_distribution_pips", [])
        if not dist: return 0.0
        return random.choice(dist)
    if random.random() < fit["zero_prob"]:
        return 0.0
    return math.exp(random.gauss(fit["log_mean"], fit["log_stdev"]))


def empirical_mean_pips():
    cal = _load()
    dist = cal.get("sorted_distribution_pips", [])
    return sum(dist) / max(len(dist), 1)


def empirical_max_pips():
    cal = _load()
    return max(cal.get("sorted_distribution_pips", [0.0]))


def lognormal_p999_pips():
    cal = _load()
    fit = cal.get("lognormal_fit")
    return fit.get("p999_extrapolated", 0.0) if fit else 0.0
