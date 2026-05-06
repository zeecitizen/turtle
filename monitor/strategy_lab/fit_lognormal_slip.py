"""fit_lognormal_slip.py — fit a zero-inflated lognormal to empirical slippage.

Per quantitative best practices: slippage is strictly non-negative with long right
tail, which lognormal models naturally. Empirical CDF works but can only sample
values that occurred — never extrapolates beyond the observed max (20 pips).
A fitted lognormal can produce realistic outliers BEYOND the observed range.

Zero inflation: ~10-15% of fills have exactly 0 slip (broker improvement / no slip).
Modeled as: Bernoulli(p_zero) + Lognormal(mu, sigma) on positive subset.

Output: appends `lognormal_fit` + `zero_inflation_prob` to slip_calibration.json.
"""
from __future__ import annotations
import json, math, statistics
from pathlib import Path

CAL_PATH = Path(__file__).parent / "slip_calibration.json"


def fit_zero_inflated_lognormal(slips):
    """Returns (zero_prob, log_mean, log_stdev, n_positive, n_zero).
    Use exp(N(log_mean, log_stdev)) with prob (1-zero_prob), else 0.
    """
    n = len(slips)
    zeros = [s for s in slips if s == 0.0]
    positives = [s for s in slips if s > 0.0]
    n_zero = len(zeros)
    n_pos  = len(positives)
    if n_pos < 2:
        return n_zero / n, 0.0, 0.0, n_pos, n_zero
    logs = [math.log(s) for s in positives]
    log_mean = statistics.mean(logs)
    log_stdev = statistics.stdev(logs)
    return n_zero / n, log_mean, log_stdev, n_pos, n_zero


def lognormal_quantiles(zero_prob, log_mean, log_stdev, qs=(0.5, 0.75, 0.9, 0.95, 0.99)):
    """Compute theoretical quantiles of the zero-inflated lognormal.
    For q above zero_prob: x = exp(mu + sigma * z(q'))  where q' = (q - zero_prob) / (1 - zero_prob)
    For q below zero_prob: x = 0
    """
    out = {}
    # inverse normal CDF approximation (Beasley-Springer-Moro)
    def inv_norm(p):
        if p <= 0 or p >= 1: return 0.0
        # Acklam's inverse normal CDF approximation
        a = [-39.6968302866538, 220.946098424521, -275.928510446969,
              138.357751867269, -30.6647980661472, 2.50662827745924]
        b = [-54.4760987982241, 161.585836858041, -155.698979859887,
              66.8013118877197, -13.2806815528857]
        c = [-0.00778489400243029, -0.322396458041136, -2.40075827716184,
             -2.54973253934373, 4.37466414146497, 2.93816398269878]
        d = [0.00778469570904146, 0.32246712907004, 2.445134137143,
             3.75440866190742]
        plow = 0.02425; phigh = 1 - plow
        if p < plow:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                   ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        if p <= phigh:
            q = p - 0.5; r = q*q
            return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
                   (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    for q in qs:
        if q <= zero_prob:
            out[f"p{int(q*100)}"] = 0.0
        else:
            q_adj = (q - zero_prob) / (1 - zero_prob)
            z = inv_norm(q_adj)
            out[f"p{int(q*100)}"] = round(math.exp(log_mean + log_stdev * z), 3)
    return out


def main():
    if not CAL_PATH.exists():
        print(f"{CAL_PATH} missing — run build_slip_calibration.py first")
        return
    cal = json.loads(CAL_PATH.read_text(encoding="utf-8"))
    slips = cal["sorted_distribution_pips"]

    print(f"Fitting zero-inflated lognormal to n={len(slips)} empirical slip values...")
    zero_prob, log_mean, log_stdev, n_pos, n_zero = fit_zero_inflated_lognormal(slips)

    fit_pcts = lognormal_quantiles(zero_prob, log_mean, log_stdev)
    emp_pcts = cal["percentiles_pips"]

    print()
    print(f"Zero-inflation: {n_zero}/{len(slips)} = {zero_prob:.1%}")
    print(f"On positives (n={n_pos}): log_mean={log_mean:.4f}, log_stdev={log_stdev:.4f}")
    print(f"  -> median positive slip = exp({log_mean:.3f}) = {math.exp(log_mean):.3f} pips")
    print(f"  -> mean positive slip   = exp({log_mean:.3f} + {log_stdev:.3f}^2/2) = {math.exp(log_mean + log_stdev**2/2):.3f} pips")
    print()

    print(f"{'Quantile':<10s}  {'Empirical':>10s}  {'Lognormal fit':>15s}  {'Delta':>8s}")
    for q in [50, 75, 90, 95, 99]:
        emp = emp_pcts.get(str(q), emp_pcts.get(q, 0.0))
        fit = fit_pcts[f"p{q}"]
        print(f"  p{q:<2d}      {emp:>10.3f}  {fit:>15.3f}  {fit - emp:>+8.3f}")
    print()

    # Tail extrapolation: the lognormal can produce values beyond observed max
    p999_fit = lognormal_quantiles(zero_prob, log_mean, log_stdev, qs=(0.999,))["p99"]  # actually 99.9
    p9999_fit = lognormal_quantiles(zero_prob, log_mean, log_stdev, qs=(0.9999,))["p99"]
    print(f"Tail extrapolation (lognormal can predict beyond observed max=20pips):")
    print(f"  p99.9  fit ~= {p999_fit:.2f} pips")
    print(f"  p99.99 fit ~= {p9999_fit:.2f} pips")
    print()

    cal["lognormal_fit"] = {
        "zero_prob": zero_prob,
        "log_mean": log_mean,
        "log_stdev": log_stdev,
        "median_positive_pips": math.exp(log_mean),
        "mean_positive_pips": math.exp(log_mean + log_stdev**2/2),
        "fit_quantiles": fit_pcts,
        "p999_extrapolated": p999_fit,
        "p9999_extrapolated": p9999_fit,
        "note": "Sample: if random < zero_prob -> 0; else -> exp(N(log_mean, log_stdev)). Lognormal naturally extrapolates the tail beyond observed max."
    }
    CAL_PATH.write_text(json.dumps(cal, indent=2), encoding="utf-8")
    print(f"Updated {CAL_PATH} with lognormal_fit")


if __name__ == "__main__":
    main()
