"""Tabulate the MT5 tester's own deal lists (no simulation)."""
import sys, json, math
sys.path.insert(0, r'C:\Users\zeesh\turtle\games\gold_runner\research\diamond_eur_mt5')
from analyze import trades, stats
from pathlib import Path
R = Path(__file__).parent / 'runs'
def binp(k, n, p):  # two-sided normal approx with continuity
    if n == 0: return float('nan')
    z = (abs(k - n * p) - 0.5) / math.sqrt(n * p * (1 - p)); return math.erfc(max(z, 0) / math.sqrt(2))
res = {}
for f in sorted(R.glob('*.json')):
    r = json.loads(f.read_text()); tr = trades(r['deals'])
    res[f.stem] = {k: stats([x for x in tr if s(x)]) for k, s in (('full', lambda x: 1), ('h1', lambda x: x['t'] < '2026.07.01'), ('h2', lambda x: x['t'] >= '2026.07.01'))}
rnd = res.get('rnd')
for name, s in res.items():
    line = [name]
    for k in ('full', 'h1', 'h2'):
        x = s[k]
        if not x.get('n'): line.append(f'{k}: 0'); continue
        p = binp(x['wins'], x['n'], rnd[k]['wr'] / 100) if rnd else float('nan')
        line.append(f"{k}: n {x['n']} WR {x['wr']:.1f} BE {x['coin']:.1f} net {x['net']/10:+.0f}p dWR {x['wr']-rnd[k]['wr']:+.1f} p {p:.3f}")
    print(' | '.join(line))
(Path(__file__).parent / 'summary.json').write_text(json.dumps(res, indent=1))
