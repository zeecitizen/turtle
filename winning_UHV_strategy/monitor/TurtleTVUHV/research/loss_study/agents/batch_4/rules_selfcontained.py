"""rules_selfcontained.py - every batch-4 rule as a standalone `def rule(t, A)` source string (exactly as submitted), checked against rules.py."""
SRC = {
"r_close_2030_2200": "def rule(t, A):\n    s = t['t_in'] % 86400  # UTC seconds of day\n    return 73800 <= s < 79200  # 20:30-22:00 UTC: NY close + daily rollover\n",
"r_close_2045_2130": "def rule(t, A):\n    s = t['t_in'] % 86400\n    return 74700 <= s < 77400  # 20:45-21:30 UTC\n",
"r_thin_market": "def rule(t, A):\n    s = t['t_in'] % 86400\n    spread = (t['fill'] - t['brk_hi_so_far']) / 1e-4  # buy: ask filled 0.3 s after the break minus the bid that broke the level\n    return (73800 <= s < 79200) or (t['side'] > 0 and spread >= 1.0)\n",
"r_spread_buy_1p5": "def rule(t, A):\n    return t['side'] > 0 and (t['fill'] - t['brk_hi_so_far']) / 1e-4 >= 1.5\n",
"r_spread_buy_1p0": "def rule(t, A):\n    return t['side'] > 0 and (t['fill'] - t['brk_hi_so_far']) / 1e-4 >= 1.0\n",
"r_friday_pm_16": "def rule(t, A):\n    dow = int(((t['t_in'] // 86400) + 4) % 7)  # 0 Sun .. 5 Fri (1970-01-01 was a Thursday)\n    return dow == 5 and (t['t_in'] % 86400) >= 57600  # Friday from 16:00 UTC\n",
"r_thin_market_plus_friday": "def rule(t, A):\n    s = t['t_in'] % 86400\n    dow = int(((t['t_in'] // 86400) + 4) % 7)\n    return ((73800 <= s < 79200) or (dow == 5 and s >= 57600)\n            or (t['side'] > 0 and (t['fill'] - t['brk_hi_so_far']) / 1e-4 >= 1.0))\n",
"r_jump_1p0": "def rule(t, A):\n    return (t['fill'] - t['level']) * t['side'] / 1e-4 >= 1.0\n",
"r_spread_buy_0p8": "def rule(t, A):\n    return t['side'] > 0 and (t['fill'] - t['brk_hi_so_far']) / 1e-4 >= 0.8\n",
"r_spread_buy_1p0_outside_close": "def rule(t, A):\n    s = t['t_in'] % 86400\n    return t['side'] > 0 and (t['fill'] - t['brk_hi_so_far']) / 1e-4 >= 1.0 and not (73800 <= s < 79200)\n",
"r_spread_buy_1p5_outside_close": "def rule(t, A):\n    s = t['t_in'] % 86400\n    return t['side'] > 0 and (t['fill'] - t['brk_hi_so_far']) / 1e-4 >= 1.5 and not (73800 <= s < 79200)\n",
"r_friday_pm_16_outside_close": "def rule(t, A):\n    s = t['t_in'] % 86400\n    dow = int(((t['t_in'] // 86400) + 4) % 7)\n    return dow == 5 and s >= 57600 and not (73800 <= s < 79200)\n",
"r_brk_nearly_as_loud": "def rule(t, A):\n    return t['brk_ticks_so_far'] >= 0.9 * t['uhv_v']\n",
"r_round_figure_ahead": "def rule(t, A):\n    lev, s, q = t['level'], t['side'], 0.0050\n    if s > 0:\n        rn = np.ceil(lev / q - 1e-9) * q\n        return 0 <= (rn - lev) / 1e-4 <= 1.5\n    rn = np.floor(lev / q + 1e-9) * q\n    return 0 <= (lev - rn) / 1e-4 <= 1.5\n",
"r_brk_projected_louder": "def rule(t, A):\n    secs = max(t['t_in'] % 60 - 0.3, 0.5)  # seconds into the entry minute\n    return t['brk_ticks_so_far'] * 60.0 / secs >= 1.2 * t['uhv_v']\n",
"r_volume_burst_2x": "def rule(t, A):\n    k, v = t['k'], A.v\n    return np.median(v[k - 9:k + 1]) >= 2.0 * max(np.median(v[k - 120:k - 9]), 1)\n",
"r_camstk_ge4": "def rule(t, A):\n    return abs(t['camStk']) >= 4\n",
"r_counter_volume_dominates": "def rule(t, A):\n    k, s = t['k'], t['side']\n    o, c, v = A.o[k - 9:k + 1], A.c[k - 9:k + 1], A.v[k - 9:k + 1]\n    return v[(c - o) * s < 0].sum() >= 1.5 * max(v[(c - o) * s > 0].sum(), 1)\n",
"r_second_attempt": "def rule(t, A):\n    ku, lev = t['ku'], t['level']\n    c = A.c[ku - 10:ku]\n    return bool(np.any(c > lev)) if t['side'] > 0 else bool(np.any(c < lev))\n",
"r_hump_no_hh": "def rule(t, A):\n    H = A.humps_known(t['k'])  # rows b0, v0, bh, vh, b1, v1, tr, known_at_bar\n    if len(H) < 2:\n        return False\n    return H[-1][3] < H[-2][3] if t['side'] > 0 else H[-1][3] > H[-2][3]\n",
"r_prior_swing_within_1pip": "def rule(t, A):\n    hs, ls = A.pivots(t['k'], 1, 30)\n    lev = t['level']\n    if t['side'] < 0:\n        return any(b < t['ku'] and 0 <= (lev - p) / 1e-4 <= 1.0 for b, p in ls)\n    return any(b < t['ku'] and 0 <= (p - lev) / 1e-4 <= 1.0 for b, p in hs)\n",
"r_counter_trend_90": "def rule(t, A):\n    k = t['k']\n    return (A.c[k] - A.c[k - 90]) * t['side'] < -6.0 * A.atr[k]\n",
}

if __name__ == "__main__":
    import math
    import os
    import sys

    import numpy as np
    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
    sys.path.insert(0, HERE)
    import api
    import rules
    bad = 0
    for n, src in SRC.items():
        g = {"np": np, "math": math}
        exec(src, g)
        a, b = api.score(g["rule"]), api.score(getattr(rules, n))
        same = all(a[p][q] == b[p][q] for p in ("all", "train", "test") for q in ("removed", "losers_removed", "lift"))
        bad += not same
        print(f"{n:32s} {'OK ' if same else 'MISMATCH'}  removed {a['all']['removed']} losers {a['all']['losers_removed']}  lift {a['all']['lift']} train {a['train']['lift']} test {a['test']['lift']}")
    print("mismatches:", bad)
