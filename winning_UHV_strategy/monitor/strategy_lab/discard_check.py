"""Print the newest full-period discard summary + per-month discard % from the rig agent logs."""
import re, collections, sys
from pathlib import Path
f = sorted(Path(r'C:\mt5_rig_axi\Tester').glob('Agent-*/logs/*.log'), key=lambda p: p.stat().st_mtime)[-1]
t = f.read_bytes()[-80000000:].decode('utf-16', errors='ignore').splitlines()
idx = [i for i, l in enumerate(t) if 'testing of Experts' in l][-1]
print(t[idx][30:170])
mon = collections.Counter(); tot = collections.Counter()
for l in t[idx:idx + 8000]:
    m = re.search(r'(\d{4})\.(\d\d)\.(\d\d) 23:59 - real ticks discarded for (\d+) minutes out of (\d+)', l)
    if m: mon[m.group(2)] += int(m.group(4)); tot[m.group(2)] += int(m.group(5))
    if 'total minute bars,' in l or 'bars generated' in l: print('  ', l.split('\t')[-1][:200])
print('  per month discarded %:', {k: round(100 * mon[k] / tot[k]) for k in sorted(tot)} if tot else 'none')
