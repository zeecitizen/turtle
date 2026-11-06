import json, math, re
from pathlib import Path
from analyze import trades, stats, receipt
RUNS = Path(__file__).parent / 'runs'
RES = Path(r'C:\Users\zeesh\turtle\games\gold_runner\research')

def binom_p(n, k, p):
    """two-sided exact binomial p-value of k wins in n vs breakeven p"""
    pk = [math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(n+1)]
    obs = pk[k]
    return min(1.0, sum(x for x in pk if x <= obs * (1 + 1e-9)))

def row(label, s, full=True):
    if not s.get('n'): return f"| {label} | 0 | - | - | - | - | - | - | - |"
    pv = binom_p(s['n'], s['wins'], s['coin'] / 100) if s['coin'] else float('nan')
    return (f"| {label} | {s['n']} | **{s['wr']:.1f}%** | {s['coin']:.1f}% | {s['wr']-s['coin']:+.1f} | {s['net']:+,.0f} ({s['net']/10:+.1f} p) | "
            f"+{s['aw']:.2f} ({s['aw']/10:.2f} p) | -{s['al']:.2f} ({s['al']/10:.2f} p) | {s['dd']:,.0f} | {pv:.2f} |")

HDR = ("| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |\n"
       "|---|---|---|---|---|---|---|---|---|---|")
LAB = {'off': 'filter off', 'er45': 'ER >= 0.45', 'er38t2': 'ER >= 0.38 + trend 2', 'er38t3': 'ER >= 0.38 + trend 3 (gold 94.8% row)'}
def load(n):
    f = RUNS / f'{n}.json'
    if not f.exists(): return None
    r = json.loads(f.read_text()); tr = trades(r['deals'])
    return r, tr
out = []
for geo, title in (('nat', 'Geometry 1 - native Diamond scaled to EUR/USD'), ('game', 'Geometry 2 - game: TP 2 pips / SL 2 pips from the fill, no clock'),
                   ('gameq', 'Geometry 2b - game distances anchored to the QUOTE (engine default), for comparison')):
    out.append(f"\n### {title}\n")
    for per, sel in (('Jan 2 - Nov 3 2026', lambda x: True), ('Jan - Jun', lambda x: x['t'] < '2026.07.01'), ('Jul - Nov 3', lambda x: x['t'] >= '2026.07.01')):
        out.append(f"\n**{per}**\n\n" + HDR)
        for fl in ('off', 'er45', 'er38t2', 'er38t3'):
            L = load(f'{geo}_{fl}')
            if not L: continue
            r, tr = L
            out.append(row(LAB[fl], stats([x for x in tr if sel(x)])))
out.append("\n### Sensitivity (NOT the Diamond as shipped or not the main setting)\n\n" + HDR)
for n, lab in (('nat_off-d0', 'native, filter off, ZERO delay'), ('game_off-d0', 'game, filter off, ZERO delay'), ('game_er45-d0', 'game, ER 0.45, ZERO delay'),
               ('game_er38t2-d0', 'game, ER 0.38+T2, ZERO delay'),
               ('nat_off-h0', 'native, filter off, hump budget OFF'), ('nat_er45-h0', 'native, ER 0.45, hump budget OFF'), ('nat_er38t2-h0', 'native, ER 0.38+T2, hump budget OFF'),
               ('game_off-h0', 'game, filter off, hump budget OFF'), ('game_er45-h0', 'game, ER 0.45, hump budget OFF'), ('game_er38t2-h0', 'game, ER 0.38+T2, hump budget OFF')):
    L = load(n)
    if L: out.append(row(lab, stats(L[1])))
# receipts
out.append("\n### Receipts per run\n\n| run | ticks | bars | ticks/bar | report trades | report WR | report net | report equity DD | fires | refused orders | exits tp/sl/clock |\n|---|---|---|---|---|---|---|---|---|---|---|")
for f in sorted(RUNS.glob('*.json')):
    r = json.loads(f.read_text()); tk, b = receipt(r); s = stats(trades(r['deals']))
    fails = sum('[DIAFAIL]' in l and 're-anchor' not in l for l in r['log'])
    w = s.get('why', {})
    out.append(f"| {f.stem} | {tk:,} | {b:,} | {tk/b:.1f} | {r.get('trades')} | {r.get('wr')} | {r.get('net')} | {r.get('dd')} | {sum('[DIAFIRE]' in l for l in r['log'])} | {fails} | {w.get('tp')}/{w.get('sl')}/{w.get('clock/other')} |")
(Path(__file__).parent / 'tables.md').write_text('\n'.join(out), encoding='utf-8')

# parity CSVs
def fires(name):
    r = json.loads((RUNS / f'{name}.json').read_text()); rows = []
    for l in r['log']:
        if '[DIAFIRE]' not in l: continue
        p = l.split('[DIAFIRE] ')[1].strip().split(',')
        t = p[0][:16]  # decision minute (bar-open of the bar after the breakout candle)
        rows.append([t, p[1], p[2], p[3], p[4], p[5], p[6], p[9], p[10], p[11]])
    fails = [l.split('\t')[-1] for l in r['log'] if '[DIAFAIL]' in l and 're-anchor' not in l]
    return rows, fails
RES.mkdir(exist_ok=True)
for name, fn in (('parity', 'diamond_eur_fires_mt5.csv'), ('parity_oct', 'diamond_eur_fires_mt5_oct2026.csv')):
    if not (RUNS / f'{name}.json').exists(): continue
    rows, fails = fires(name)
    with open(RES / fn, 'w', newline='') as h:
        h.write('time_server,side,uhv_time,uhv_high,uhv_low,retrace_extreme,entry_quote,uhv_tickvol,breakout_tickvol,origin_time\n')
        for x in rows: h.write(','.join(x) + '\n')
    print(fn, len(rows), 'fires; refused:', fails)
print(open(Path(__file__).parent / 'tables.md', encoding='utf-8').read()[:3000])
