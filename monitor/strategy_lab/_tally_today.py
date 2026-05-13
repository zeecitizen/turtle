"""Quick tally of today's M1 EA trades post-restart."""
import re
from collections import Counter

p = r'C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260513.log'
text = open(p, 'rb').read().decode('utf-16-le', errors='replace')

# Pull all CLOSED net P&L lines (any prefix) from M1 chart
m1_closes = []
for ln in text.splitlines():
    if 'UhvSweepExhaustion' not in ln: continue
    if '(XAUUSD,M1)' not in ln: continue
    if 'net P&L:' not in ln: continue
    m_time = re.search(r'(\d{2}:\d{2}:\d{2})', ln)
    m_pnl = re.search(r'\$(-?\d+\.\d+)', ln)
    if m_time and m_pnl:
        m1_closes.append((m_time.group(1), float(m_pnl.group(1))))

# All closes today
print(f'Total M1 closes today: {len(m1_closes)}')
print(f'Net: ${sum(p for _, p in m1_closes):+.2f}')

# Only after 05:11 (restart)
since = [(t, p) for t, p in m1_closes if t >= '05:11']
print()
print(f'Since 05:11 broker time (post-restart): {len(since)} trades')
print(f'Net: ${sum(p for _, p in since):+.2f}')

wins = [(t, p) for t, p in since if p > 0]
losses = [(t, p) for t, p in since if p < 0]
print(f'Wins: {len(wins)}  Losses: {len(losses)}')
if wins:
    print(f'Avg win:  ${sum(p for _, p in wins)/len(wins):+.2f}  best ${max(p for _, p in wins):+.2f}')
if losses:
    print(f'Avg loss: ${sum(p for _, p in losses)/len(losses):+.2f}  worst ${min(p for _, p in losses):+.2f}')

# Loss-size distribution
print()
print('Loss-size buckets:')
for lo, hi in [(0,-1),(-1,-3),(-3,-5),(-5,-10),(-10,-20),(-20,-50),(-50,-200)]:
    n = sum(1 for _, p in since if hi < p <= lo)
    if n: print(f'  ({hi:+5.0f}, {lo:+5.0f}]: {n}')

# Last 20
print()
print('Last 20 closes:')
for t, pnl in since[-20:]:
    mark = '✓' if pnl > 0 else '✗'
    print(f'  {t}  {mark}  ${pnl:+7.2f}')
