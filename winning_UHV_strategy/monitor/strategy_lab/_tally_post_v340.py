"""Compare pre-v3.40 vs post-v3.40 trading performance today."""
import re
from collections import Counter

p = r'C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260513.log'
text = open(p, 'rb').read().decode('utf-16-le', errors='replace')

# v3.40 deployed at 12:11:22 broker
DEPLOY = '12:11'

# Parse trade events
closes = []
smart_cuts = []
for ln in text.splitlines():
    if 'UhvSweepExhaustion' not in ln: continue
    if '(XAUUSD,M1)' not in ln: continue
    m_time = re.search(r'(\d{2}:\d{2}:\d{2})', ln)
    if not m_time: continue
    ts = m_time.group(1)
    if '[EXIT smart_cut]' in ln:
        smart_cuts.append(ts)
    if 'net P&L:' in ln:
        m_pnl = re.search(r'\$(-?\d+\.\d+)', ln)
        if m_pnl:
            closes.append((ts, float(m_pnl.group(1))))

post = [(t, p) for t, p in closes if t >= DEPLOY]
pre = [(t, p) for t, p in closes if t < DEPLOY]

def summarize(label, lst):
    if not lst:
        print(f'{label}: no trades')
        return
    wins = [p for _, p in lst if p > 0]
    losses = [p for _, p in lst if p < 0]
    net = sum(p for _, p in lst)
    print(f'{label}: {len(lst)} trades  W:{len(wins)} L:{len(losses)} '
          f'WR:{len(wins)/len(lst)*100:.1f}%  net ${net:+.2f}')
    if wins:
        print(f'  avg win ${sum(wins)/len(wins):+.2f}  best ${max(wins):+.2f}')
    if losses:
        print(f'  avg loss ${sum(losses)/len(losses):+.2f}  worst ${min(losses):+.2f}')
    # Loss buckets
    big = sum(1 for _, p in lst if p < -10)
    huge = sum(1 for _, p in lst if p < -30)
    print(f'  losses ≥$10: {big}  losses ≥$30: {huge}')

print(f'v3.40 deployed at {DEPLOY} broker time')
print()
summarize('PRE-v3.40 (full day before patch)', pre)
print()
summarize('POST-v3.40 (after patch)', post)
print()
print(f'Smart cut fires today: {len(smart_cuts)}')
if smart_cuts:
    print(f'  Times: {smart_cuts[-10:]}')
