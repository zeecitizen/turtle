"""
Shano Strategy Backtest v2 -- Single-Candle Momentum Detection

Tests our detect_big_candle() against Shano's actual 32 trades.
Key change from v1: We now look for ONE big candle (body > prev 2),
not a streak of 3-5 same-color candles.

She enters WHILE the candle is growing, so we include the trade bar
in detection (not just completed bars before it).
"""
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TRADES_FILE = SCRIPT_DIR / "shano_trades.json"
OHLCV_FILE = Path(r"C:\Users\zeesh\.claude\projects\c--Users-zeesh-Documents-GitHub-turtle\0bde9b45-766e-47c4-8fd9-800899154d6f\tool-results\mcp-tradingview-data_get_ohlcv-1777050326289.txt")

from shano_strategy import detect_big_candle, load_config
from datetime import timedelta

MOSCOW_OFFSET = timedelta(hours=3)

def load_ohlcv():
    raw = json.loads(OHLCV_FILE.read_text("utf-8"))
    text_content = raw[0]["text"] if isinstance(raw, list) else raw
    if isinstance(text_content, str):
        data = json.loads(text_content)
    else:
        data = text_content
    return data.get("bars", [])

def unix_to_moscow(ts):
    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) + MOSCOW_OFFSET
    return dt.strftime("%H:%M")

def backtest():
    trades = json.loads(TRADES_FILE.read_text("utf-8"))["trades"]
    bars = load_ohlcv()
    config = load_config()

    # Build time-indexed bar list
    bar_by_time = {}
    bar_list = []
    for b in bars:
        moscow = unix_to_moscow(b["time"])
        bar_by_time[moscow] = b
        bar_list.append((moscow, b))

    bar_times = [t for t, _ in bar_list]

    print("=" * 80)
    print("SHANO STRATEGY BACKTEST v2 -- Single-Candle Momentum")
    print("Detection: current candle body > BOTH of previous 2 candle bodies")
    print("Entry: while candle is growing (include trade bar)")
    print("=" * 80)

    total_shano_pnl = 0
    detected_count = 0
    same_direction_count = 0
    missed_count = 0
    wrong_direction_count = 0

    for trade in trades:
        trade_time = trade["time"][:5]
        trade_dir = trade["dir"]
        trade_pnl = trade["pnl"]
        trade_lots = trade["lots"]
        total_shano_pnl += trade_pnl

        # Find bar index for this trade time
        if trade_time not in bar_times:
            closest = None
            for t in bar_times:
                if t <= trade_time:
                    closest = t
            if not closest:
                print(f"  SKIP {trade_time} - no bar data")
                continue
            trade_time_bar = closest
        else:
            trade_time_bar = trade_time

        idx = bar_times.index(trade_time_bar)

        # Get previous 5 bars + current bar for context
        # She enters WHILE the bar is forming, so include the trade bar
        lookback = 5
        start_idx = max(0, idx - lookback)
        context_bars = [b for _, b in bar_list[start_idx:idx + 1]]

        if len(context_bars) < 3:
            print(f"  SKIP {trade['time']} - not enough context bars")
            continue

        # Run detection INCLUDING the trade bar (she enters while it's growing)
        result = detect_big_candle(context_bars, config)

        # Also try detection on bars BEFORE trade bar (in case she saw it on prev bar)
        result_prev = detect_big_candle(context_bars[:-1], config) if len(context_bars) > 3 else None

        # Use whichever detected
        detected = result or result_prev
        which = "curr" if result else "prev" if result_prev else None

        # Show candle info for last 4 bars
        display_bars = context_bars[-4:] if len(context_bars) >= 4 else context_bars
        colors = []
        bodies = []
        for c in display_bars:
            body = abs(c["close"] - c["open"])
            bodies.append(f"{body:.1f}")
            if c["close"] > c["open"]:
                colors.append("G")
            elif c["close"] < c["open"]:
                colors.append("R")
            else:
                colors.append("D")

        emoji = "+" if trade_pnl > 0 else "X"

        if detected:
            detected_count += 1
            our_dir = detected["direction"]
            match = our_dir == trade_dir

            if match:
                same_direction_count += 1
                dir_label = "MATCH"
            else:
                wrong_direction_count += 1
                dir_label = "WRONG"

            print(f"  {emoji} {trade['time']} Shano:{trade_dir.upper():4} {trade_lots:.2f} ${trade_pnl:+.2f} | "
                  f"Ours:{our_dir.upper():4} body={detected['body']} ratio={detected['ratio_to_max_prev']}x [{dir_label}] "
                  f"({which}) | {' '.join(c+':'+b for c,b in zip(colors,bodies))}")
        else:
            missed_count += 1
            print(f"  {emoji} {trade['time']} Shano:{trade_dir.upper():4} {trade_lots:.2f} ${trade_pnl:+.2f} | "
                  f"NO SIGNAL | {' '.join(c+':'+b for c,b in zip(colors,bodies))}")

    print(f"\n{'=' * 80}")
    print("BACKTEST v2 RESULTS")
    print(f"{'=' * 80}")
    total = len(trades)
    print(f"Total Shano trades:   {total}")
    print(f"Pattern detected:     {detected_count}/{total} ({detected_count/total*100:.0f}%)")
    if detected_count > 0:
        print(f"Same direction:       {same_direction_count}/{detected_count} ({same_direction_count/detected_count*100:.0f}% of detected)")
        print(f"Wrong direction:      {wrong_direction_count}/{detected_count} ({wrong_direction_count/detected_count*100:.0f}% of detected)")
    print(f"Missed (no signal):   {missed_count}/{total} ({missed_count/total*100:.0f}%)")
    print(f"\nShano's total P&L:    ${total_shano_pnl:+.2f}")

    if detected_count > 0:
        accuracy = same_direction_count / detected_count * 100
        print(f"\nDirection accuracy:   {accuracy:.0f}%")
        if accuracy >= 60:
            print("-> GOOD: When we detect, we agree with Shano's direction")
        else:
            print("-> ISSUE: We disagree with Shano's direction too often")

    coverage = detected_count / total * 100
    print(f"Signal coverage:      {coverage:.0f}%")
    if coverage >= 50:
        print("-> GOOD: We detect signals for most of her trades")
    elif coverage >= 30:
        print("-> MODERATE: We catch some but miss many of her entries")
    else:
        print("-> LOW: We're missing most of her entries -- detection needs tuning")

    # Analyze MISSES
    print(f"\n{'=' * 80}")
    print("MISS ANALYSIS -- Why no signal?")
    print(f"{'=' * 80}")

    miss_reasons = {"body_not_bigger": 0, "body_too_small": 0, "not_enough_bars": 0}

    for trade in trades:
        trade_time = trade["time"][:5]
        if trade_time not in bar_times:
            closest = None
            for t in bar_times:
                if t <= trade_time:
                    closest = t
            if not closest:
                continue
            trade_time_bar = closest
        else:
            trade_time_bar = trade_time

        idx = bar_times.index(trade_time_bar)
        start_idx = max(0, idx - 5)
        context_bars = [b for _, b in bar_list[start_idx:idx + 1]]

        result = detect_big_candle(context_bars, config)
        result_prev = detect_big_candle(context_bars[:-1], config) if len(context_bars) > 3 else None

        if result or result_prev:
            continue  # Not a miss

        if len(context_bars) < 3:
            miss_reasons["not_enough_bars"] += 1
            continue

        # Check WHY it missed
        current = context_bars[-1]
        curr_body = abs(current["close"] - current["open"])
        prev_bodies = [abs(c["close"] - c["open"]) for c in context_bars[-3:-1]]

        if curr_body < config.get("min_body_points", 1.0):
            miss_reasons["body_too_small"] += 1
            print(f"  {trade['time']} {trade['dir'].upper()} ${trade['pnl']:+.2f}: "
                  f"body={curr_body:.1f} < min {config.get('min_body_points', 1.0)} (too small)")
        else:
            miss_reasons["body_not_bigger"] += 1
            print(f"  {trade['time']} {trade['dir'].upper()} ${trade['pnl']:+.2f}: "
                  f"body={curr_body:.1f} NOT > prev {[round(b,1) for b in prev_bodies]}")

    print(f"\nMiss breakdown:")
    for reason, count in miss_reasons.items():
        if count > 0:
            print(f"  {reason}: {count}")

if __name__ == "__main__":
    backtest()
