"""apply_runtime.py — set live Feb11TickMedium parameters without reattach.

Writes Common\\Files\\feb11_runtime_<magic>.json. The EA (v1.15+) polls this file
every 2 seconds via OnTimer and applies any changes immediately.

Usage:
    python apply_runtime.py --lots 0.10
    python apply_runtime.py --trail-arm 2 --trail-gb 5
    python apply_runtime.py --broker-sl 50 --broker-tp 100
    python apply_runtime.py --daily-dd 60
    python apply_runtime.py --magic 88011 --lots 0.05 --trail-arm 5 --trail-gb 15
    python apply_runtime.py --show              # show current runtime file contents
    python apply_runtime.py --reset             # delete file, EA falls back to Inp* startup values

Available params (use --kebab-case CLI / snake_case JSON key):
    lots                     position size for NEW trades (open positions unchanged)
    trail-arm   / trail_arm  trail-arm threshold in price units
    trail-gb    / trail_giveback  trail give-back in price units
    skim-cap    / skim_cap   take-profit cap in price units
    max-loss    / max_loss   EA's CB stop in price units
    broker-sl   / broker_sl_usd  broker-side SL parachute in USD
    broker-tp   / broker_tp_usd  broker-side TP parachute in USD
    daily-dd    / daily_dd   daily session DD limit in price units
    rng60-min   / rng60_min  min absolute 60-sec range to fire
    rng60-norm  / rng60_norm_min  min normalized 60-sec range
    spread-max  / spread_max max allowed spread to fire
    cooldown    / cooldown_sec
    max-hold    / max_hold_sec  max position hold time
    loss-streak-n     / loss_streak_n
    loss-streak-pause / loss_streak_pause

After write, check MT5 Experts log within ~2-3 sec for a line like:
    [Feb11TickMedium] runtime config updated: trailArm=2.00 trailGB=5.00
"""
import argparse
import json
import sys
from pathlib import Path

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")

# CLI flag → JSON key. Each maps to the key the EA reads from the file.
PARAMS = {
    "lots":             "lots",
    "trail-arm":        "trail_arm",
    "trail-gb":         "trail_giveback",
    "skim-cap":         "skim_cap",
    "max-loss":         "max_loss",
    "broker-sl":        "broker_sl_usd",
    "broker-tp":        "broker_tp_usd",
    "daily-dd":         "daily_dd",
    "rng60-min":        "rng60_min",
    "rng60-norm":       "rng60_norm_min",
    "spread-max":       "spread_max",
    "cooldown":         "cooldown_sec",
    "max-hold":         "max_hold_sec",
    "loss-streak-n":    "loss_streak_n",
    "loss-streak-pause":"loss_streak_pause",
}
INT_KEYS = {"cooldown_sec", "max_hold_sec", "loss_streak_n", "loss_streak_pause"}


def runtime_path(magic: int) -> Path:
    return COMMON / f"feb11_runtime_{magic}.json"


def parse_args():
    ap = argparse.ArgumentParser(
        description="Update Feb11TickMedium live params without reattach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--magic", type=int, default=88011,
                    help="EA magic number (default: 88011 = Feb11_MED on Atmos)")
    for flag in PARAMS:
        ap.add_argument(f"--{flag}", type=float, default=None,
                        help=f"set {PARAMS[flag]}")
    ap.add_argument("--show", action="store_true",
                    help="Show current runtime file contents")
    ap.add_argument("--reset", action="store_true",
                    help="Delete runtime file (EA falls back to Inp* startup values)")
    return ap.parse_args()


def main():
    args = parse_args()
    rt = runtime_path(args.magic)

    if args.show:
        if rt.exists():
            print(f"Current {rt.name}:")
            print(rt.read_text())
        else:
            print(f"{rt.name} does not exist — EA is using Inp* startup defaults.")
        return 0

    if args.reset:
        if rt.exists():
            rt.unlink()
            print(f"Deleted {rt.name}. EA will fall back to Inp* defaults on next OnTimer (~2s).")
        else:
            print(f"{rt.name} already absent.")
        return 0

    # Gather supplied params
    new_vals = {}
    for cli_flag, json_key in PARAMS.items():
        attr = cli_flag.replace("-", "_")
        val = getattr(args, attr)
        if val is None:
            continue
        if json_key in INT_KEYS:
            new_vals[json_key] = int(val)
        else:
            new_vals[json_key] = float(val)
    if not new_vals:
        print("No params supplied. Use --help for options, --show to inspect current state.")
        return 1

    # Merge with existing file if present (so partial updates don't wipe other keys)
    existing = {}
    if rt.exists():
        try:
            existing = json.loads(rt.read_text())
        except Exception:
            pass
    existing.update(new_vals)

    # MT5's ExtractDouble parses floats but NOT scientific notation. Format plainly.
    body = "{" + ",".join(f'"{k}":{v}' for k, v in existing.items()) + "}"
    rt.write_text(body)
    print(f"Wrote {rt.name}:")
    print(f"  {body}")
    print(f"EA will apply within ~2 seconds. Watch Experts log for confirmation:")
    print(f'  [Feb11TickMedium] runtime config updated: ...')
    return 0


if __name__ == "__main__":
    sys.exit(main())
