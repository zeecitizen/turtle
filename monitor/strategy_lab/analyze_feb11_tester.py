"""
analyze_feb11_tester.py — compare UhvSweepExhaustion Strategy Tester output
against Zee's 27 manual setups from 2026.02.11.

Workflow:
  1. Run Strategy Tester in MT5 (see mt5/configs/tester_feb11.ini for steps)
  2. Right-click Results tab → Save Report → save HTML to:
       monitor/strategy_lab/tester_feb11_report.html
  3. py monitor/strategy_lab/analyze_feb11_tester.py

Outputs:
  - Per-setup capture table (which of Zee's 27 the EA caught)
  - False-positive list (EA fires that don't match a Zee setup)
  - Simulated P&L vs. Zee's actual +$835
  - Filter-rejection guesses for missed setups (best-effort from time/side)
"""
from __future__ import annotations
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPORT_HTML = Path(__file__).parent / "tester_feb11_report.html"

# Zee's 27 actual setups on 2026.02.11 (entry-time minute, side, broker-time HH:MM)
# Derived from his Trade History Report. Each entry = one decision (may have
# stacked 1-6 positions in the live account — but for setup-capture comparison
# we count decisions, not positions.
ZEE_FEB11_SETUPS = [
    # (entry HH:MM:SS, side, entry_price, close HH:MM:SS, close_price)
    ("01:32:19", "buy",  5045.07, "01:47:30", 5045.94),
    ("01:59:04", "buy",  5042.17, "02:00:43", 5042.96),
    ("02:09:38", "sell", 5040.68, "02:10:18", 5039.29),
    ("02:29:02", "buy",  5039.03, "02:30:28", 5041.41),
    ("16:49:07", "buy",  5047.93, "16:51:03", 5049.96),
    ("16:52:21", "buy",  5050.77, "16:52:27", 5051.82),
    ("16:54:10", "buy",  5056.74, "16:54:20", 5057.72),
    ("16:58:03", "buy",  5064.26, "16:58:27", 5064.94),
    ("17:02:45", "buy",  5055.71, "17:03:51", 5062.23),
    ("17:36:11", "buy",  5056.53, "17:36:26", 5056.92),
    ("17:36:13", "buy",  5057.05, "17:52:56", 5058.77),
    ("17:37:26", "buy",  5045.82, "17:40:02", 5046.66),
    ("17:49:59", "buy",  5048.32, "17:52:33", 5054.58),
    ("18:24:18", "buy",  5059.26, "18:28:33", 5060.27),
    ("18:41:50", "buy",  5078.10, "19:06:41", 5077.93),
    ("19:08:59", "sell", 5083.28, "19:09:08", 5082.35),
    ("19:11:05", "sell", 5083.39, "19:11:27", 5083.02),
    ("19:11:51", "sell", 5083.79, "19:19:10", 5081.77),
    ("19:20:34", "sell", 5084.21, "19:20:40", 5082.52),
    ("19:26:06", "sell", 5089.16, "19:26:50", 5087.43),
    ("19:29:31", "buy",  5086.34, "19:39:03", 5086.44),
    ("19:32:48", "buy",  5084.71, "19:37:34", 5085.41),
    ("19:36:19", "buy",  5082.91, "19:37:19", 5084.17),
    ("19:38:39", "buy",  5083.28, "19:38:50", 5084.59),
    ("19:38:59", "buy",  5086.33, "19:39:03", 5086.44),
    ("19:41:59", "sell", 5091.09, "19:42:54", 5090.93),
    ("19:42:26", "sell", 5093.18, "19:42:40", 5092.05),
]
# Total: 27 setups, $835.16 P&L across 69 stacked positions (94.2% WR)

# Match window: an EA fire within ±MATCH_WINDOW of a Zee entry is "the same setup"
MATCH_WINDOW_MIN = 5  # MT5 tester time vs Zee's broker time can drift slightly


def parse_tester_report(html_path: Path):
    """Parse MT5 Strategy Tester HTML report. Returns list of dict trades.

    MT5 reports are UTF-16 LE with this row shape (within Positions/Deals section):
      <td>OPEN_TIME</td><td>TICKET</td><td>SYMBOL</td><td>SIDE</td>
      <td>VOLUME</td><td>OPEN_PRICE</td><td>S/L</td><td>T/P</td>
      <td>CLOSE_TIME</td><td>CLOSE_PRICE</td><td>COMMISSION</td><td>SWAP</td>
      <td colspan="2">PROFIT</td>
    Same format as Zee's history report — we can reuse the parser pattern.
    """
    if not html_path.exists():
        print(f"ERROR: report not found at {html_path}")
        print("Run the Strategy Tester first (see mt5/configs/tester_feb11.ini)")
        print("Save the result with: right-click Results → Save Report (HTML)")
        sys.exit(1)

    raw = html_path.read_bytes()
    # MT5 saves reports as UTF-16 LE by default
    try:
        text = raw.decode("utf-16-le")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")

    # Strip HTML tags to a sequence of <td> cell texts, then walk rows.
    # Cell text extraction: grab everything between <td...> and </td>.
    cells = re.findall(r"<td[^>]*>(.*?)</td>", text, re.DOTALL | re.IGNORECASE)
    cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in cells]

    trades = []
    # Walk cells looking for the data shape: date pattern at position 0
    date_re = re.compile(r"^\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}$")
    i = 0
    while i < len(cells) - 13:
        if date_re.match(cells[i]) and date_re.match(cells[i + 8]):
            try:
                row = {
                    "open_time":  datetime.strptime(cells[i],     "%Y.%m.%d %H:%M:%S"),
                    "ticket":     cells[i + 1],
                    "symbol":     cells[i + 2],
                    "side":       cells[i + 3].lower(),
                    "volume":     float(cells[i + 4]) if cells[i + 4] else 0,
                    "open_price": float(cells[i + 5]) if cells[i + 5] else 0,
                    "close_time": datetime.strptime(cells[i + 8], "%Y.%m.%d %H:%M:%S"),
                    "close_price": float(cells[i + 9]) if cells[i + 9] else 0,
                    "profit":     float(cells[i + 12].replace(" ", "")) if cells[i + 12] else 0,
                }
                if row["side"] in ("buy", "sell") and row["symbol"]:
                    trades.append(row)
                i += 13
                continue
            except (ValueError, IndexError):
                pass
        i += 1
    return trades


def match_to_zee_setups(ea_trades):
    """For each Zee setup, find the closest EA fire (same side, within window)."""
    zee_with_dt = [
        (datetime.strptime("2026.02.11 " + s[0], "%Y.%m.%d %H:%M:%S"), s[1], s[2])
        for s in ZEE_FEB11_SETUPS
    ]
    captures = []  # (zee_time, side, price, matched_ea_trade_or_None)
    used_ea_indices = set()
    for zt, zside, zprice in zee_with_dt:
        best_idx, best_gap = None, timedelta(minutes=MATCH_WINDOW_MIN + 1)
        for i, ea in enumerate(ea_trades):
            if i in used_ea_indices:
                continue
            if ea["side"] != zside:
                continue
            gap = abs(ea["open_time"] - zt)
            if gap <= timedelta(minutes=MATCH_WINDOW_MIN) and gap < best_gap:
                best_idx, best_gap = i, gap
        match = ea_trades[best_idx] if best_idx is not None else None
        if best_idx is not None:
            used_ea_indices.add(best_idx)
        captures.append((zt, zside, zprice, match))
    # Remaining unmatched EA trades are false positives
    false_positives = [ea for i, ea in enumerate(ea_trades) if i not in used_ea_indices]
    return captures, false_positives


def main():
    print(f"Reading: {REPORT_HTML}")
    ea_trades = parse_tester_report(REPORT_HTML)
    print(f"EA fires in tester: {len(ea_trades)}")
    if not ea_trades:
        print("No trades found — check that the report has a Positions/Deals section.")
        sys.exit(0)

    captures, false_positives = match_to_zee_setups(ea_trades)

    matched = [c for c in captures if c[3] is not None]
    missed  = [c for c in captures if c[3] is None]

    print()
    print("════════════════════════════════════════════════════════════════")
    print(f"  SETUP CAPTURE: {len(matched)}/{len(ZEE_FEB11_SETUPS)}  ({len(matched)/len(ZEE_FEB11_SETUPS)*100:.1f}%)")
    print("════════════════════════════════════════════════════════════════")
    print()
    print("Zee setup → EA match:")
    for zt, zside, zprice, ea in captures:
        if ea:
            gap_s = (ea["open_time"] - zt).total_seconds()
            print(f"  ✓ {zt:%H:%M:%S} {zside:4s} @ {zprice:7.2f}  →  EA {ea['open_time']:%H:%M:%S} @ {ea['open_price']:7.2f}  (+{ea['profit']:6.2f}, gap {gap_s:+.0f}s)")
        else:
            print(f"  ✗ {zt:%H:%M:%S} {zside:4s} @ {zprice:7.2f}  →  MISSED")
    print()

    if false_positives:
        print(f"EA fires NOT matching any Zee setup ({len(false_positives)}):")
        for ea in false_positives:
            print(f"    ! {ea['open_time']:%H:%M:%S} {ea['side']:4s} @ {ea['open_price']:7.2f}  →  close {ea['close_price']:7.2f}  P&L {ea['profit']:+6.2f}")
        print()

    total_pnl = sum(ea["profit"] for ea in ea_trades)
    wins  = sum(1 for ea in ea_trades if ea["profit"] > 0)
    losses= sum(1 for ea in ea_trades if ea["profit"] <= 0)
    print("════════════════════════════════════════════════════════════════")
    print(f"  EA SIMULATED P&L (0.10 lots, no scale-in)")
    print("════════════════════════════════════════════════════════════════")
    print(f"  Trades: {len(ea_trades)}    Wins: {wins}   Losses: {losses}   WR: {wins/len(ea_trades)*100:.1f}%")
    print(f"  Total P&L: ${total_pnl:+.2f}")
    print(f"  Zee's actual (69 positions of 0.10, scaled): +$835.16")
    print(f"  Apples-to-apples ratio: {total_pnl/835.16*100:+.1f}% of Zee's day")
    print()

    print("════════════════════════════════════════════════════════════════")
    print("  MISSED SETUPS — filter most likely to blame")
    print("════════════════════════════════════════════════════════════════")
    print("  (heuristic — confirm by reading the EA's [SIGNAL CONSIDERED]")
    print("   journal lines for each timestamp in the tester journal tab)")
    print()
    for zt, zside, zprice, _ in missed:
        print(f"  {zt:%H:%M:%S} {zside:4s} @ {zprice:7.2f}")
    print()


if __name__ == "__main__":
    main()
