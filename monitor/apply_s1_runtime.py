"""apply_s1_runtime.py — programmatically change S1Trader v2.53+ runtime config.

S1Trader v2.53 polls Common\\Files\\s1_runtime_<magic>.json every 2 seconds
via OnTimer. Use this script to flip gate inputs without touching MT5.

Usage examples:
    py monitor/apply_s1_runtime.py --h1bias true
    py monitor/apply_s1_runtime.py --hhhl-m5 false --hhhl-h1 false
    py monitor/apply_s1_runtime.py --h1bias-bars 8
    py monitor/apply_s1_runtime.py --show
    py monitor/apply_s1_runtime.py --reset      # restore Inp* defaults
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

COMMON_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")


def parse_bool(s: str) -> bool:
    return s.lower() in ("true", "1", "yes", "on")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--magic", type=int, default=88004, help="EA magic number (default 88004 = S1Trader)")
    ap.add_argument("--h1bias", type=parse_bool, default=None)
    ap.add_argument("--hhhl-m5", type=parse_bool, default=None, dest="hhhl_m5")
    ap.add_argument("--hhhl-h1", type=parse_bool, default=None, dest="hhhl_h1")
    ap.add_argument("--h1bias-bars", type=int, default=None, dest="h1bias_bars")
    ap.add_argument("--momentum", type=parse_bool, default=None, dest="momentum_override_enabled",
                    help="Toggle v2.59 momentum override gate (bypasses slow trend filter on fast moves)")
    ap.add_argument("--momentum-pts", type=float, default=None, dest="momentum_override_pts",
                    help="30-min close-delta threshold for momentum override (default 5.0)")
    # v2.88 hot-reloadable tunables
    ap.add_argument("--auto-close-ms", type=int, default=None, dest="auto_close_ms",
                    help="v2.88: auto-close each position X ms after open (0=disabled)")
    ap.add_argument("--trail-lock-pts", type=float, default=None, dest="trail_lock_pts",
                    help="v2.88: arm trail when peak ≥ this many pts (0=trail off)")
    ap.add_argument("--trail-rev-pts", type=float, default=None, dest="trail_rev_pts",
                    help="v2.88: exit on this pullback from peak (0=trail off)")
    ap.add_argument("--daily-loss-halt", type=float, default=None, dest="daily_loss_halt",
                    help="v2.88: halt new entries when day net ≤ -this (0=disabled)")
    ap.add_argument("--daily-profit-target", type=float, default=None, dest="daily_profit_target",
                    help="v2.88: harvest-lock when day net ≥ this (0=disabled)")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    fname = COMMON_DIR / f"s1_runtime_{args.magic}.json"

    if args.reset:
        if fname.exists():
            fname.unlink()
            print(f"Removed {fname}. EA will fall back to Inp* defaults in ~2 sec.")
        else:
            print(f"No runtime file to reset at {fname}.")
        return

    cfg = {}
    if fname.exists():
        try:
            cfg = json.loads(fname.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: could not parse existing {fname}: {e}. Starting fresh.")
            cfg = {}

    if args.show:
        print(f"Current runtime config @ {fname}:")
        print(json.dumps(cfg, indent=2))
        return

    changed = []
    if args.h1bias is not None:
        cfg["require_h1bias"] = args.h1bias
        changed.append(f"require_h1bias={args.h1bias}")
    if args.hhhl_m5 is not None:
        cfg["require_hhhl_m5"] = args.hhhl_m5
        changed.append(f"require_hhhl_m5={args.hhhl_m5}")
    if args.hhhl_h1 is not None:
        cfg["require_hhhl_h1"] = args.hhhl_h1
        changed.append(f"require_hhhl_h1={args.hhhl_h1}")
    if args.h1bias_bars is not None:
        cfg["h1bias_bars"] = args.h1bias_bars
        changed.append(f"h1bias_bars={args.h1bias_bars}")
    if args.momentum_override_enabled is not None:
        cfg["momentum_override_enabled"] = args.momentum_override_enabled
        changed.append(f"momentum_override_enabled={args.momentum_override_enabled}")
    if args.momentum_override_pts is not None:
        cfg["momentum_override_pts"] = args.momentum_override_pts
        changed.append(f"momentum_override_pts={args.momentum_override_pts}")
    # v2.88 hot-reloadable tunables
    if args.auto_close_ms is not None:
        cfg["auto_close_ms"] = args.auto_close_ms
        changed.append(f"auto_close_ms={args.auto_close_ms}")
    if args.trail_lock_pts is not None:
        cfg["trail_lock_pts"] = args.trail_lock_pts
        changed.append(f"trail_lock_pts={args.trail_lock_pts}")
    if args.trail_rev_pts is not None:
        cfg["trail_rev_pts"] = args.trail_rev_pts
        changed.append(f"trail_rev_pts={args.trail_rev_pts}")
    if args.daily_loss_halt is not None:
        cfg["daily_loss_halt"] = args.daily_loss_halt
        changed.append(f"daily_loss_halt={args.daily_loss_halt}")
    if args.daily_profit_target is not None:
        cfg["daily_profit_target"] = args.daily_profit_target
        changed.append(f"daily_profit_target={args.daily_profit_target}")

    if not changed:
        print("No changes specified. Use --h1bias / --hhhl-m5 / --auto-close-ms / --trail-lock-pts / --show / --reset")
        return

    from datetime import datetime, timezone, timedelta
    cfg["_written_at"] = datetime.now(timezone(timedelta(hours=5))).strftime("%Y-%m-%d %H:%M PKT")

    fname.parent.mkdir(parents=True, exist_ok=True)
    fname.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Wrote {fname}")
    print(f"Changes: {', '.join(changed)}")
    print("EA will apply within ~2 sec. Watch MT5 Experts log for confirmation:")
    print('  "[S1] runtime config updated: ..."')


if __name__ == "__main__":
    main()
