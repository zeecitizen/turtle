"""admin.py - symbol profiles for Golden Gravity (Zee 2026-11-04): "create an admin page for the game -> on that page we can select whether
its EURUSD or XAUUSD in the symbol -> and it can have settings for both and we can apply them at will -> the game picks up whatever setting is
saved on the admin interface".

state/admin.json = {"active": "XAUUSD", "profiles": {"XAUUSD": {...}, "EURUSD": {...}}}. Every profile key is a config.json key (it is laid
over config.json when the server builds the feed and the engine), plus price_dp (the price grid) and the sim_* mapping keys (SimFeed runs
its gold process and maps it onto the symbol: price = sim_base + (gold - 3926) * sim_scale, spread = gold spread * sim_spread_scale).

Price units: XAU/USD in dollars of gold price, EUR/USD in dollars per euro (1 pip = 0.0001). Quantities: XAU in ounces, EUR in euros.
"""
import copy
import json
import os

PROFILES = {
    "XAUUSD": {
        "label": "Gold (XAU/USD)", "symbol": "XAU/USD", "sym_id": 1019, "price_dp": 2,
        "coin_oz": 0.10, "min_qty": 0.01, "qty_step": 0.01, "coin_max_oz": 0.30, "leverage": 1000,
        "stop_dist": 1.0, "stop_choices": [1.0, 2.0, 3.0], "targets": [1.0, 1.2, 1.5, 2.0, 3.0], "target_default": 1.0,
        "haggle_step": 0.10, "wall_buffer": 0.30, "min_sl_gap": 0.05, "merchant_margin_price": 0.08,
        "tilt_full_scale": 0.6, "tilt_ha_scale": 1.20, "dia_unit": 1.0, "live_max_qty": 0.10, "news_shutters": True, "barrel_gap": 0.30, "stake_merge": 0.25, "gap_min": 0.25,
        "vol_dead": 0.20, "vol_calm": 0.55, "vol_storm": 1.60, "storm_spread": 0.45, "lightning_usd": 0.60, "pit_full_spread": 0.60,
        "paper_slippage_max": 0.06, "sim_slippage_max": 0.06,
        "sim_base": 3926.0, "sim_scale": 1.0, "sim_spread_scale": 1.0,
    },
    "EURUSD": {
        "label": "Euro (EUR/USD)", "symbol": "EUR/USD", "sym_id": 1000, "price_dp": 5,
        # one coin = 500 EUR: a 2-pip stop risks $0.10 (500 x 0.0002). PXTrader's smallest EUR/USD amount is unverified - raise if refused.
        "coin_oz": 500, "min_qty": 1, "qty_step": 1, "coin_max_oz": 1500, "leverage": 1000, "coins_max": 3, "loss_max_balance_pct": 0.05,
        "stop_dist": 0.0002, "stop_choices": [0.0002, 0.0004, 0.0006], "targets": [0.0002, 0.00024, 0.0003, 0.0004, 0.0006],
        "target_default": 0.0002,
        "haggle_step": 0.00002, "wall_buffer": 0.00006, "min_sl_gap": 0.00001, "merchant_margin_price": 0.000016,
        "tilt_full_scale": 0.00012, "tilt_ha_scale": 0.00024, "dia_unit": 0.00012, "live_max_qty": 3000, "news_shutters": False, "rounds_max": 100000, "barrel_gap": 0.00006, "stake_merge": 0.00005, "gap_min": 0.00005,
        "vol_dead": 0.00004, "vol_calm": 0.00011, "vol_storm": 0.00032, "storm_spread": 0.00004, "lightning_usd": 0.00012,
        "pit_full_spread": 0.00004, "paper_slippage_max": 0.00001, "sim_slippage_max": 0.00001,
        "sim_base": 1.1228, "sim_scale": 0.0002, "sim_spread_scale": 0.0000303,
    },
}

# what the admin page shows, in order: (key, label, help, kind) - kind: text | int | num | list
FIELDS = [
    ("label", "Name", "shown on this page only", "text"),
    ("symbol", "PXTrader symbol", "exactly as PXTrader writes it", "text"),
    ("sym_id", "PXTrader symbol id", "XAU/USD = 1019, EUR/USD = 1000 (read from the live page)", "int"),
    ("price_dp", "Price decimals", "the price grid: 2 for gold, 5 for EUR/USD", "int"),
    ("coin_oz", "One coin (quantity)", "ounces for gold, euros for EUR/USD; risk per coin = this x the stop", "num"),
    ("min_qty", "Smallest order", "the broker's minimum quantity", "num"),
    ("qty_step", "Quantity step", "the broker's quantity step", "num"),
    ("coin_max_oz", "Most per round", "the cap for a three-man volley", "num"),
    ("stop_dist", "Stop (anvil) distance", "price distance from the entry to the stop", "num"),
    ("stop_choices", "Stop choices", "comma-separated", "list"),
    ("targets", "Target choices", "comma-separated; the closest is always used", "list"),
    ("target_default", "Target", "price distance from the entry to the hand-off", "num"),
    ("haggle_step", "Haggle step", "how far one haggle raises the target", "num"),
    ("wall_buffer", "Wall gap", "a wall is built this far behind the Runner", "num"),
    ("min_sl_gap", "Smallest stop gap", "the broker refuses a stop closer than this to the price", "num"),
    ("merchant_margin_price", "Ice-cream girl margin", "price distance the coin must be ahead before she rides by", "num"),
    ("tilt_ha_scale", "Full tilt (Heikin-Ashi)", "a 1-minute HA body this big tilts the street fully", "num"),
    ("tilt_full_scale", "Full tilt (10-second move)", "used only when tilt_mode is delta", "num"),
    ("rounds_max", "Rounds per day", "the daily round limit (Zee 2026-11-05: turned off for EUR/USD = 100000)", "num"),
    ("news_shutters", "News shutters (1 = on)", "1 = no new rounds near high-impact news; 0 = ride the news (Zee 2026-11-04)", "num"),
    ("live_max_qty", "Live order cap", "the live feed refuses any real order bigger than this (in the coin's units: oz of gold, EUR)", "num"),
    ("dia_unit", "Diamond price unit", "one gold dollar in this symbol (scales the Diamond's EMA-5 margin and stop)", "num"),
    ("vol_dead", "Weather: dead below", "the 60-second range below which the market is asleep", "num"),
    ("vol_calm", "Weather: calm below", "", "num"),
    ("vol_storm", "Weather: storm above", "", "num"),
    ("storm_spread", "Storm spread", "a spread this wide is a storm", "num"),
    ("pit_full_spread", "Deepest mud pit", "the spread that fills the pit to the top", "num"),
    ("lightning_usd", "Lightning move", "a jump this big strikes lightning", "num"),
    ("gap_min", "Smallest gap", "a jump this big is a gap (a chasm)", "num"),
    ("barrel_gap", "Barrel gap", "", "num"),
    ("stake_merge", "Stake merge", "stakes closer than this merge", "num"),
    ("paper_slippage_max", "Paper slippage", "practice fills slip up to this", "num"),
    ("sim_base", "Sim: starting price", "the practice market starts here", "num"),
    ("sim_scale", "Sim: price scale", "practice moves = gold-dollar moves x this", "num"),
    ("sim_spread_scale", "Sim: spread scale", "practice spread = gold spread x this (gold 0.33)", "num"),
    ("sim_slippage_max", "Sim: broker slippage", "", "num"),
    ("leverage", "Leverage", "used for the margin check", "num"),
]
META = {"label"}


def path(state_dir):
    return os.path.join(state_dir, "admin.json")


def defaults():
    return {"active": "EURUSD", "profiles": copy.deepcopy(PROFILES)}   # Zee 2026-11-04: the game runs on EUR/USD; gold waits on the admin page


def load(state_dir):
    """The saved admin settings laid over the built-in profiles (a missing or broken file = the defaults)."""
    data = defaults()
    try:
        with open(path(state_dir), encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return data
    if isinstance(saved, dict):
        for name, prof in (saved.get("profiles") or {}).items():
            if name in data["profiles"] and isinstance(prof, dict):
                data["profiles"][name].update({k: v for k, v in prof.items() if k in PROFILES[name] or k in META})
        if saved.get("active") in data["profiles"]:
            data["active"] = saved["active"]
    return data


def clean(body):
    """Validate a POSTed admin document; returns (data, None) or (None, why)."""
    if not isinstance(body, dict) or body.get("active") not in PROFILES:
        return None, "bad_active"
    data = defaults()
    data["active"] = body["active"]
    kinds = {k: kind for k, _l, _h, kind in FIELDS}
    for name, prof in (body.get("profiles") or {}).items():
        if name not in PROFILES or not isinstance(prof, dict):
            continue
        for k, v in prof.items():
            if k not in PROFILES[name]:
                continue
            kind = kinds.get(k, "num")
            try:
                if kind == "text":
                    v = str(v)[:40]
                elif kind == "int":
                    v = int(v)
                elif kind == "list":
                    v = [float(x) for x in (v if isinstance(v, list) else str(v).split(",")) if str(x).strip() != ""]
                    if not v:
                        return None, f"empty_{k}"
                else:
                    v = float(v)
                    if v < 0:
                        return None, f"negative_{k}"
            except (TypeError, ValueError):
                return None, f"bad_{name}_{k}"
            data["profiles"][name][k] = v
    for name, prof in data["profiles"].items():
        if prof["target_default"] not in prof["targets"]:
            prof["targets"] = sorted(set(prof["targets"] + [prof["target_default"]]))
        if prof["stop_dist"] not in prof["stop_choices"]:
            prof["stop_choices"] = sorted(set(prof["stop_choices"] + [prof["stop_dist"]]))
        if not 0 <= int(prof["price_dp"]) <= 8:
            return None, f"bad_{name}_price_dp"
    return data, None


def save(state_dir, data):
    os.makedirs(state_dir, exist_ok=True)
    tmp = path(state_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path(state_dir))


def overrides(data):
    """The active profile as config overrides (meta keys dropped)."""
    prof = (data.get("profiles") or {}).get(data.get("active")) or PROFILES["XAUUSD"]
    return {k: v for k, v in prof.items() if k not in META}
