"""
compare_shano_to_ea.py — time-align Shano's manual trades with our EA's
trades and report mismatches in entry timing + scaled P&L.

Shano traded across two accounts (Blueberry + FTMO Free Trial) on
2026-05-13 between 02:07-02:35 broker time. Her per-trade entries are
recorded here from the broker history screenshots.

For each Shano setup (deduped by ~5-second window across accounts),
find the closest EA trade in the MT5 log and report:
  - time gap (sec)
  - side match
  - Shano lot vs EA lot
  - Shano P&L vs scaled EA P&L
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

LOG = Path(r'C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260513.log')

# Shano's trades from screenshots, deduped by ~10s window per setup.
# Per-setup, capturing the best-data version (lot size, side, pnl)
SHANO_SETUPS = [
    # (time, side, lot, pnl_usd)
    ('02:07:45', 'buy',  0.10,  3.58),   # FTMO
    ('02:09:06', 'buy',  0.02,  3.72),   # Blueberry
    ('02:09:27', 'sell', 0.10,  0.32),   # FTMO
    ('02:10:01', 'sell', 0.10, 11.28),   # FTMO
    ('02:10:30', 'sell', 0.01,  0.38),   # Blueberry
    ('02:11:14', 'buy',  0.10, 27.76),   # FTMO
    ('02:14:28', 'sell', 0.10, -0.64),   # FTMO (her only loss)
    ('02:14:42', 'sell', 0.40,  2.00),   # Blueberry
    ('02:20:05', 'sell', 0.10, 27.76),   # FTMO
    ('02:22:54', 'buy',  0.10,  5.76),   # FTMO
    ('02:23:42', 'buy',  0.40,  8.40),   # Blueberry
    ('02:24:40', 'buy',  0.10,  9.20),   # Blueberry
    ('02:24:50', 'buy',  0.40, 30.40),   # Blueberry
    ('02:27:08', 'sell', 0.10,  2.56),   # FTMO
    ('02:30:27', 'sell', 0.40,  5.20),   # Blueberry
    ('02:30:35', 'sell', 0.10,  0.56),   # FTMO
    ('02:34:54', 'sell', 0.40,  3.20),   # Blueberry
    ('02:35:54', 'sell', 0.40, 30.40),   # Blueberry
]


def parse_ea_trades_in_window(date_yyyymmdd, hms_from='02:00', hms_to='03:00'):
    """Pull our EA's [SIGNAL]+[CLOSED net P&L] pairs from the MT5 log."""
    log_path = Path(str(LOG).replace('20260513', date_yyyymmdd))
    if not log_path.exists(): return []
    text = log_path.read_bytes().decode('utf-16-le', errors='replace')

    trades = []
    open_sig = None
    for ln in text.splitlines():
        if 'UhvSweepExhaustion' not in ln or '(XAUUSD,M1)' not in ln: continue
        m_time = re.search(r'(\d{2}:\d{2}:\d{2})', ln)
        if not m_time: continue
        ts = m_time.group(1)
        if ts < hms_from or ts > hms_to: continue
        if '[SIGNAL]' in ln:
            m = re.search(r'\[SIGNAL\]\s+(BUY|SELL)\s+@\s+([\d.]+)', ln)
            if m:
                open_sig = {'time': ts, 'side': m.group(1).lower(), 'entry': float(m.group(2))}
        elif '[CLOSED] net P&L:' in ln and open_sig:
            m = re.search(r'\$(-?\d+\.\d+)', ln)
            if m:
                open_sig['close_time'] = ts
                open_sig['pnl'] = float(m.group(1))
                trades.append(open_sig)
                open_sig = None
    return trades


def parse_hms(s):
    return datetime.strptime('2026.05.13 ' + s, '%Y.%m.%d %H:%M:%S')


def main():
    ea_trades = parse_ea_trades_in_window('20260513', '02:00', '03:00')
    print(f"EA fired {len(ea_trades)} trades in 02:00-03:00 broker window today.\n")

    print(f"{'Shano':<10} {'side':<5} {'lot':<6} {'Shano $':<10} | {'EA time':<10} {'gap':<8} {'EA $':<8} {'scaled':<10} {'verdict'}")
    print('-' * 110)

    matched_ea = set()
    captured = 0
    for st, side, lot, pnl_shano in SHANO_SETUPS:
        zt = parse_hms(st)
        best = None; best_gap = timedelta(minutes=99); best_idx = None
        for i, ea in enumerate(ea_trades):
            if i in matched_ea: continue
            et = parse_hms(ea['time'])
            gap = abs(et - zt)
            if gap < best_gap and ea['side'] == side and gap < timedelta(minutes=3):
                best = ea; best_gap = gap; best_idx = i
        if best:
            matched_ea.add(best_idx)
            captured += 1
            # Scale: Shano's pnl per 0.10 lot
            shano_per_010 = pnl_shano / (lot / 0.10) if lot > 0 else 0
            verdict = 'MATCHED' if abs(best['pnl'] - shano_per_010) / max(1, abs(shano_per_010)) < 2.0 else 'P&L DIVERGES'
            gap_s = int(best_gap.total_seconds())
            print(f"{st:<10} {side:<5} {lot:<6} ${pnl_shano:<+8.2f} | {best['time']:<10} {gap_s:<+6}s   ${best['pnl']:<+6.2f}  ${shano_per_010:<+8.2f}  {verdict}")
        else:
            print(f"{st:<10} {side:<5} {lot:<6} ${pnl_shano:<+8.2f} | (none)                              MISSED")

    print()
    print(f"Captured: {captured}/{len(SHANO_SETUPS)}  ({captured/len(SHANO_SETUPS)*100:.0f}%)")
    if matched_ea:
        misses_ea = [ea for i, ea in enumerate(ea_trades) if i not in matched_ea]
        if misses_ea:
            print(f"\nEA fired {len(misses_ea)} trades NOT matched to a Shano setup:")
            for ea in misses_ea:
                print(f"  {ea['time']} {ea['side']:4s} @ {ea['entry']}  exit P&L ${ea['pnl']:+.2f}")


if __name__ == "__main__":
    main()
