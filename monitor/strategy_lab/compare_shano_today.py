"""
compare_shano_today.py — use today's actual MT5 log entries directly to
compare EA's real fires vs Shano's actual trades. No backtest needed.

This is the live-data version of compare_shano_to_ea.py — pulls the
SAME data that's been written to the log throughout the day, including
all v3.30/v3.40/v3.41/v3.42 entries.
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

LOG = Path(r'C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260513.log')

# Shano's setups from screenshots (broker time, 2026-05-13)
SHANO = [
    ('02:07:45', 'buy',  0.10,  3.58),
    ('02:09:06', 'buy',  0.02,  3.72),
    ('02:09:27', 'sell', 0.10,  0.32),
    ('02:10:01', 'sell', 0.10, 11.28),
    ('02:10:30', 'sell', 0.01,  0.38),
    ('02:11:14', 'buy',  0.10, 27.76),
    ('02:14:28', 'sell', 0.10, -0.64),
    ('02:14:42', 'sell', 0.40,  2.00),
    ('02:20:05', 'sell', 0.10, 27.76),
    ('02:22:54', 'buy',  0.10,  5.76),
    ('02:23:42', 'buy',  0.40,  8.40),
    ('02:24:40', 'buy',  0.10,  9.20),
    ('02:24:50', 'buy',  0.40, 30.40),
    ('02:27:08', 'sell', 0.10,  2.56),
    ('02:30:27', 'sell', 0.40,  5.20),
    ('02:30:35', 'sell', 0.10,  0.56),
    ('02:34:54', 'sell', 0.40,  3.20),
    ('02:35:54', 'sell', 0.40, 30.40),
]


def parse_log(window_from=None, window_to=None):
    text = LOG.read_bytes().decode('utf-16-le', errors='replace')
    trades = []
    open_sig = None
    pending_exit = None
    for ln in text.splitlines():
        if 'UhvSweepExhaustion' not in ln or '(XAUUSD,M1)' not in ln: continue
        m = re.search(r'(\d{2}:\d{2}:\d{2})', ln)
        if not m: continue
        ts = m.group(1)
        if window_from and ts < window_from: continue
        if window_to and ts > window_to: continue
        if '[SIGNAL]' in ln:
            sig_m = re.search(r'\[SIGNAL\]\s+(BUY|SELL)\s+@\s+([\d.]+)', ln)
            if sig_m:
                open_sig = {'time': ts, 'side': sig_m.group(1).lower(),
                            'entry': float(sig_m.group(2))}
        elif '[EXIT' in ln:
            m_ex = re.search(r'\[EXIT\s+(\w+)\].*?pnl=\$(-?\d+\.\d+).*?peak=\$(-?\d+\.\d+)', ln)
            if m_ex:
                pending_exit = {'reason': m_ex.group(1), 'pnl': float(m_ex.group(2)),
                                'peak': float(m_ex.group(3))}
        elif '[TRAIL_LOCK]' in ln:
            pass  # info only
        elif '[CLOSED] net P&L:' in ln and open_sig:
            m_p = re.search(r'\$(-?\d+\.\d+)', ln)
            if m_p:
                trades.append({
                    'open_time': open_sig['time'], 'side': open_sig['side'],
                    'entry': open_sig['entry'], 'close_time': ts,
                    'pnl': float(m_p.group(1)),
                    'reason': pending_exit['reason'] if pending_exit else 'sl',
                    'peak': pending_exit['peak'] if pending_exit else 0,
                })
                open_sig = None; pending_exit = None
    return trades


def main():
    # Shano window: 02:00-03:00
    trades = parse_log('02:00:00', '03:00:00')
    print(f"EA trades 02:00-03:00 broker today: {len(trades)}\n")

    print(f"{'open':<10} {'side':<5} {'entry':<10} {'close':<10} {'pnl':<10} {'peak':<8} {'reason'}")
    for t in trades:
        print(f"{t['open_time']:<10} {t['side']:<5} {t['entry']:<10.2f} {t['close_time']:<10} ${t['pnl']:<+8.2f} ${t['peak']:<+6.2f}  {t['reason']}")
    print()

    # Match to Shano
    print(f"{'Shano':<10} {'side':<5} {'lot':<5} {'$':<8} | {'EA time':<10} {'gap':<8} {'EA $':<10} {'verdict'}")
    print('-' * 95)
    matched = set()
    captured = 0
    for st, side, lot, pnl in SHANO:
        zt = datetime.strptime('2026-05-13 ' + st, '%Y-%m-%d %H:%M:%S')
        best = None; best_gap = timedelta(minutes=99); best_idx = None
        for i, t in enumerate(trades):
            if i in matched: continue
            if t['side'] != side: continue
            et = datetime.strptime('2026-05-13 ' + t['open_time'], '%Y-%m-%d %H:%M:%S')
            gap = abs(et - zt)
            if gap < timedelta(minutes=3) and gap < best_gap:
                best, best_gap, best_idx = t, gap, i
        if best:
            matched.add(best_idx)
            captured += 1
            shano_per_010 = pnl / (lot / 0.10) if lot > 0 else 0
            print(f"{st:<10} {side:<5} {lot:<5} ${pnl:<+6.2f} | {best['open_time']:<10} "
                  f"{int(best_gap.total_seconds()):<+5}s   ${best['pnl']:<+7.2f}  MATCHED")
        else:
            print(f"{st:<10} {side:<5} {lot:<5} ${pnl:<+6.2f} | (none)                              MISSED")
    print(f"\nCaptured: {captured}/{len(SHANO)}  ({captured/len(SHANO)*100:.0f}%)")

    extras = [t for i, t in enumerate(trades) if i not in matched]
    if extras:
        print(f"\nEA fires NOT matched to Shano ({len(extras)}):")
        for t in extras: print(f"  {t['open_time']} {t['side']:<5} ${t['pnl']:+.2f}")


if __name__ == "__main__":
    main()
