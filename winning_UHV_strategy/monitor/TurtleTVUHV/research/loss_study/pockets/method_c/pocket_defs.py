"""pocket_defs.py - METHOD C pocket families: one small set per loss-cause cluster, each 1-2 conditions on decision-time features with a
market reason. Grids are coarse and in natural units (NY clock in 15-min steps anchored on the 17:00 NY daily break / Friday close /
08:30 + 10:00 NY US-data slots; whole ATRs; integer humps; 0.1-pip ATR). Shared by tune_pockets.py (train only) and evaluate_pockets.py."""
import numpy as np


def hm(m):
    m = int(m)
    return f"{m // 60:02d}:{m % 60:02d}"


def H(h, m=0):
    return h * 60 + m


CLUSTERS = ["weekly_close", "rollover_dead_book", "news_spike", "no_separator_chop", "exhausted_move", "counter_structure",
            "support_resistance"]
_A = [H(15, 30), H(15, 45), H(16), H(16, 15), H(16, 30), H(16, 45)]
_B = [H(17, 15), H(17, 30), H(17, 45), H(18), H(18, 15), H(18, 30), H(18, 45), H(19), H(19, 15), H(19, 30)]
_ATR = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
FAMILIES = {
    # Friday afternoon into the 17:00 NY weekly close: weekend drain, the engine flattens open trades at 16:58 NY
    "weekly_close": [
        {"name": "fri_from", "nconds": 2, "grid": {"T": list(range(H(12), H(16, 46), 15))}},
    ],
    # the 17:00 NY daily break (rollover): empty book, spread blow-out; a clock window on any day, optionally OR a blow-out spread at the
    # breakout tick (>= 1.0 pip only: below that the train/test feeds differ, 0.5/0.6 vs <= 0.5) or OR a dead book (10-bar mean ticks)
    "rollover_dead_book": [
        {"name": "clock_window", "nconds": 1, "grid": {"A": _A, "B": _B}},
        {"name": "clock_or_spread", "nconds": 2, "grid": {"A": _A, "B": _B, "S": [1.0, 1.2, 1.4, 1.6, 2.0]}},
        {"name": "clock_or_deadbook", "nconds": 2, "grid": {"A": _A, "B": _B, "V": [10, 15, 20, 25, 30, 40]}},
    ],
    # scheduled US data (08:30 NY, 10:00 NY), Mon-Fri: a fixed window around the slot, optionally with volume already picking up
    "news_spike": [
        {"name": "data_slots", "nconds": 1, "grid": {"slots": ["0830", "0830+1000"], "w": [5, 10, 15, 20, 30]}},
        {"name": "data_slots_volup", "nconds": 2, "grid": {"slots": ["0830", "0830+1000"], "w": [5, 10, 15, 20, 30],
                                                           "r": [0.8, 1.0, 1.2, 1.4]}},
    ],
    # dead / chop tape with no separator: tiny ATR, optionally in the NY-night (Asian) hours or with a low 30-bar efficiency
    "no_separator_chop": [
        {"name": "low_atr", "nconds": 1, "grid": {"a": _ATR}},
        {"name": "low_atr_night", "nconds": 2, "grid": {"a": _ATR, "E": [H(0), H(1), H(2), H(3)]}},
        {"name": "low_atr_chop", "nconds": 2, "grid": {"a": _ATR, "e": [0.05, 0.10, 0.15, 0.20]}},
    ],
    # exhausted / climax: a long run already behind the breakout (30-bar move in ATRs) plus maturity (camel humps) or straightness
    "exhausted_move": [
        {"name": "humps_trend", "nconds": 2, "grid": {"h": list(range(1, 10)), "t": list(range(1, 10))}},
        {"name": "er_trend", "nconds": 2, "grid": {"e": [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5], "t": list(range(1, 10))}},
        {"name": "extreme_trend", "nconds": 2, "grid": {"p": [0.8, 0.85, 0.9, 0.95, 1.0], "t": list(range(1, 10))}},
    ],
    # counter-structure: trading against the prevailing move (90/30-bar move against the trade, level low in its 60-bar range)
    "counter_structure": [
        {"name": "downtrend_low", "nconds": 2, "grid": {"t": [0, 2, 4, 6, 8, 10, 12, 15], "p": [0.1, 0.2, 0.3, 0.4, 0.5]}},
        {"name": "against_structure", "nconds": 2, "grid": {"t": [0, 2, 4, 6, 8, 10, 12, 15], "p": [1.0]}},   # p fixed: 2 conditions max
        {"name": "against_impulse", "nconds": 2, "grid": {"t": [1, 2, 3, 4, 5, 6], "p": [0.1, 0.2, 0.3, 0.4, 0.5]}},
    ],
    # into support / resistance: an older 60/240-bar extreme or a round figure just beyond the level, in the trade's way
    "support_resistance": [
        {"name": "wall_ahead60", "nconds": 1, "grid": {"r": [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]}},
        {"name": "wall_ahead240", "nconds": 1, "grid": {"r": [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]}},
        {"name": "figure_ahead", "nconds": 1, "grid": {"f": [1, 2, 3, 4, 5, 6, 8, 10]}},
        {"name": "half_figure_ahead", "nconds": 1, "grid": {"f": [1, 2, 3, 4, 5, 6]}},
        {"name": "near_top_wall", "nconds": 2, "grid": {"p": [0.7, 0.8, 0.85, 0.9, 0.95], "r": [1.0, 2.0, 3.0, 5.0]}},
    ],
}


def mask_of(name, p, A):
    mod, wd = A["ny_min_of_day"], A["weekday"]
    if name == "fri_from":
        return (wd == 4) & (mod >= p["T"])
    if name in ("clock_window", "clock_or_spread", "clock_or_deadbook"):
        m = (mod >= p["A"]) & (mod < p["B"])
        if name == "clock_or_spread":
            m = m | (A["spread_pips"] >= p["S"] - 1e-9)
        if name == "clock_or_deadbook":
            m = m | (A["vol10"] <= p["V"])
        return m
    if name in ("data_slots", "data_slots_volup"):
        slots = [H(8, 30)] + ([H(10)] if p["slots"] == "0830+1000" else [])
        m = np.zeros(len(mod), bool)
        for s in slots:
            m |= np.abs(mod - s) <= p["w"]
        m &= wd <= 4
        if name == "data_slots_volup":
            m &= A["vol_ratio10_60"] >= p["r"]
        return m
    if name == "low_atr":
        return A["atr_pips"] <= p["a"] + 1e-9
    if name == "low_atr_night":
        return (A["atr_pips"] <= p["a"] + 1e-9) & ((mod >= H(19)) | (mod < p["E"]))
    if name == "low_atr_chop":
        return (A["atr_pips"] <= p["a"] + 1e-9) & (A["er30"] <= p["e"] + 1e-9)
    if name == "humps_trend":
        return (A["humps"] >= p["h"]) & (A["trend30_atr"] >= p["t"])
    if name == "er_trend":
        return (A["er30"] >= p["e"] - 1e-9) & (A["trend30_atr"] >= p["t"])
    if name == "extreme_trend":
        return (A["pos60"] >= p["p"] - 1e-9) & (A["trend30_atr"] >= p["t"])
    if name == "downtrend_low":
        return (A["trend90_atr"] <= -p["t"]) & (A["pos60"] <= p["p"] + 1e-9)
    if name == "against_structure":
        return (A["struct_with"] == 0) & (A["trend90_atr"] <= -p["t"]) & (A["pos60"] <= p["p"] + 1e-9)
    if name == "against_impulse":
        return (A["trend30_atr"] <= -p["t"]) & (A["pos60"] <= p["p"] + 1e-9)
    if name == "wall_ahead60":
        return (A["room60_pips"] > 0) & (A["room60_pips"] <= p["r"] + 1e-9)
    if name == "wall_ahead240":
        return (A["room240_pips"] > 0) & (A["room240_pips"] <= p["r"] + 1e-9)
    if name == "figure_ahead":
        return A["fig_ahead_pips"] <= p["f"] + 1e-9
    if name == "half_figure_ahead":
        return np.mod(A["fig_ahead_pips"], 50.0) <= p["f"] + 1e-9
    if name == "near_top_wall":
        return (A["pos60"] >= p["p"] - 1e-9) & (A["room60_pips"] > 0) & (A["room60_pips"] <= p["r"] + 1e-9)
    raise KeyError(name)


def describe(name, p):
    if name == "fri_from":
        return f"Friday from {hm(p['T'])} NY (to the 17:00 NY weekly close)"
    if name == "clock_window":
        return f"NY clock {hm(p['A'])}-{hm(p['B'])}, any day (the 17:00 NY daily break)"
    if name == "clock_or_spread":
        return f"NY clock {hm(p['A'])}-{hm(p['B'])} any day, OR breakout-tick spread >= {p['S']:.1f} pip"
    if name == "clock_or_deadbook":
        return f"NY clock {hm(p['A'])}-{hm(p['B'])} any day, OR last-10-candle mean ticks <= {p['V']}"
    if name == "data_slots":
        s = "08:30" if p["slots"] == "0830" else "08:30 / 10:00"
        return f"Mon-Fri within +-{p['w']} min of the {s} NY US-data slot"
    if name == "data_slots_volup":
        s = "08:30" if p["slots"] == "0830" else "08:30 / 10:00"
        return f"Mon-Fri within +-{p['w']} min of the {s} NY US-data slot AND vol10/vol60 >= {p['r']}"
    if name == "low_atr":
        return f"ATR <= {p['a']:.1f} pip"
    if name == "low_atr_night":
        return f"ATR <= {p['a']:.1f} pip AND NY 19:00-{hm(p['E'])} (night / Asian tape)"
    if name == "low_atr_chop":
        return f"ATR <= {p['a']:.1f} pip AND er30 <= {p['e']:.2f}"
    if name == "humps_trend":
        return f"camel humps >= {p['h']} AND 30-bar move with the trade >= {p['t']} ATR"
    if name == "er_trend":
        return f"er30 >= {p['e']:.2f} AND 30-bar move with the trade >= {p['t']} ATR"
    if name == "extreme_trend":
        return f"level at >= {p['p']:.2f} of its 60-bar range AND 30-bar move with the trade >= {p['t']} ATR"
    if name == "downtrend_low":
        return f"90-bar move AGAINST the trade >= {p['t']} ATR AND level in the bottom {p['p']:.1f} of its 60-bar range"
    if name == "against_structure":
        return f"no HH+HL structure with the trade AND 90-bar move against >= {p['t']} ATR AND pos60 <= {p['p']:.1f}"
    if name == "against_impulse":
        return f"30-bar move AGAINST the trade >= {p['t']} ATR AND level in the bottom {p['p']:.1f} of its 60-bar range"
    if name == "wall_ahead60":
        return f"an older 60-bar extreme 0-{p['r']:.1f} pip beyond the level (wall ahead)"
    if name == "wall_ahead240":
        return f"an older 240-bar extreme 0-{p['r']:.1f} pip beyond the level (wall ahead)"
    if name == "figure_ahead":
        return f"a 100-pip figure within {p['f']} pip ahead"
    if name == "half_figure_ahead":
        return f"a 00/50 figure within {p['f']} pip ahead"
    if name == "near_top_wall":
        return f"level at >= {p['p']:.2f} of its 60-bar range AND the 60-bar extreme 0-{p['r']:.1f} pip beyond it"
    return f"{name} {p}"
