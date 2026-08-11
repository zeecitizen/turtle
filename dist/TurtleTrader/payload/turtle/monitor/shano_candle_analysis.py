"""
Cross-reference Shano's trades with actual 1-min candle data.
Find the exact candle patterns she was looking at before each trade.
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

TRADES_FILE = Path(__file__).parent / "shano_trades.json"
OHLCV_FILE = Path(r"C:\Users\zeesh\.claude\projects\c--Users-zeesh-Documents-GitHub-turtle\0bde9b45-766e-47c4-8fd9-800899154d6f\tool-results\mcp-tradingview-data_get_ohlcv-1777050326289.txt")

MOSCOW_OFFSET = timedelta(hours=3)

def load_ohlcv():
    """Load OHLCV bars from saved file."""
    raw = json.loads(OHLCV_FILE.read_text("utf-8"))
    # The file is a JSON array with schema [{type: string, text: string}]
    text_content = raw[0]["text"] if isinstance(raw, list) else raw
    if isinstance(text_content, str):
        data = json.loads(text_content)
    else:
        data = text_content
    return data.get("bars", [])

def unix_to_moscow(ts):
    """Convert unix timestamp to Moscow time string."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) + MOSCOW_OFFSET
    return dt.strftime("%H:%M")

def moscow_to_approx_unix(time_str, base_date_unix):
    """Convert Moscow time string to approximate unix timestamp."""
    h, m = time_str.split(":")[:2]
    s = 0
    if len(time_str.split(":")) > 2:
        s = int(time_str.split(":")[2])
    # Base date start (midnight Moscow) = base_date_unix adjusted
    moscow_seconds = int(h) * 3600 + int(m) * 60 + s
    # Approximate: find the bar closest to this Moscow time
    return moscow_seconds

def analyze():
    trades = json.loads(TRADES_FILE.read_text("utf-8"))["trades"]
    bars = load_ohlcv()

    if not bars:
        print("No OHLCV data loaded!")
        return

    print(f"Loaded {len(bars)} bars")
    print(f"Time range: {unix_to_moscow(bars[0]['time'])} -> {unix_to_moscow(bars[-1]['time'])} Moscow")

    # Build a time-indexed map of bars
    bar_map = {}
    for b in bars:
        moscow_time = unix_to_moscow(b["time"])
        bar_map[moscow_time] = b

    print(f"\n{'='*80}")
    print("SHANO'S TRADES vs CANDLE PATTERNS")
    print(f"{'='*80}")

    for trade in trades:
        trade_time = trade["time"]  # "14:39:49"
        trade_minute = trade_time[:5]  # "14:39"

        # Find the bar at this minute
        bar = bar_map.get(trade_minute)

        # Look at previous 5 bars for context
        bar_keys = list(bar_map.keys())
        if trade_minute in bar_keys:
            idx = bar_keys.index(trade_minute)
            prev_bars = [bar_map[bar_keys[i]] for i in range(max(0, idx-5), idx+1)]
        else:
            # Try to find closest bar
            prev_bars = []
            for k in bar_keys:
                if k <= trade_minute:
                    prev_bars.append(bar_map[k])
            prev_bars = prev_bars[-6:]  # Last 6 bars before trade

        if not prev_bars:
            print(f"\n  {trade_time} {trade['dir'].upper()} {trade['lots']} - NO BARS FOUND")
            continue

        # Analyze candle colors before trade
        colors = []
        for b in prev_bars:
            if b["close"] > b["open"]:
                colors.append("G")  # Green
            elif b["close"] < b["open"]:
                colors.append("R")  # Red
            else:
                colors.append("D")  # Doji

        # Calculate body sizes and volumes
        bodies = [abs(b["close"] - b["open"]) for b in prev_bars]
        volumes = [b["volume"] for b in prev_bars]

        emoji = "+" if trade["pnl"] > 0 else "X"
        print(f"\n  {emoji} {trade_time} {trade['dir'].upper():4} {trade['lots']:.2f} @ {trade['entry']:.3f} = ${trade['pnl']:+.2f}")
        print(f"    Candle colors before: {'  '.join(colors)}")
        print(f"    Bodies:              {' '.join(f'{b:.1f}' for b in bodies)}")
        print(f"    Volumes:             {' '.join(f'{v:4d}' for v in volumes)}")

        # Check for exhaustion pattern
        last_3_colors = colors[-3:] if len(colors) >= 3 else colors
        if all(c == "R" for c in last_3_colors):
            print(f"    >>> RED EXHAUSTION DETECTED (3+ reds)")
            if trade["dir"] == "buy":
                print(f"    >>> She BOUGHT after red exhaustion = REVERSAL play")
            else:
                print(f"    >>> She SOLD after red exhaustion = CONTINUATION play")
        elif all(c == "G" for c in last_3_colors):
            print(f"    >>> GREEN EXHAUSTION DETECTED (3+ greens)")
            if trade["dir"] == "sell":
                print(f"    >>> She SOLD after green exhaustion = REVERSAL play")
            else:
                print(f"    >>> She BOUGHT after green exhaustion = CONTINUATION play")

    # Summary: count how many trades had exhaustion pattern
    print(f"\n{'='*80}")
    print("PATTERN SUMMARY")
    print(f"{'='*80}")

if __name__ == "__main__":
    analyze()
