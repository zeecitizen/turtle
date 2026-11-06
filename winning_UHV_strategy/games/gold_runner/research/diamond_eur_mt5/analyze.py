import json, re, sys
from pathlib import Path
RUNS = Path(__file__).parent / 'runs'

def trades(deals):
    out, cur = [], None
    for d in deals:
        if d['io'] == 'in':
            if cur: out.append(cur)
            cur = dict(t=d['time'], side=d['type'], entry=d['price'], net=d['comm'] + d['swap'] + d['profit'], why='', exit=None)
        elif cur:
            cur['net'] += d['comm'] + d['swap'] + d['profit']; cur['exit'] = d['price']
            c = d['comment'].lower(); cur['why'] = 'tp' if c.startswith('tp') else 'sl' if c.startswith('sl') else 'clock/other'
    if cur: out.append(cur)
    return out

def stats(tr):
    n = len(tr)
    if not n: return dict(n=0)
    w = [x['net'] for x in tr if x['net'] > 0]; l = [x['net'] for x in tr if x['net'] < 0]
    aw = sum(w) / len(w) if w else 0; al = -sum(l) / len(l) if l else 0
    bal = peak = dd = 0
    for x in tr:
        bal += x['net']; peak = max(peak, bal); dd = max(dd, peak - bal)
    why = {k: sum(x['why'] == k for x in tr) for k in ('tp', 'sl', 'clock/other')}
    return dict(n=n, wins=len(w), wr=100 * len(w) / n, net=sum(x['net'] for x in tr), aw=aw, al=al,
                coin=100 * al / (aw + al) if aw + al else None, dd=dd, per=sum(x['net'] for x in tr) / n, zero=n - len(w) - len(l), why=why)

def receipt(r):
    for l in r['log']:
        m = re.search(r'(\d+) ticks, (\d+) bars generated', l)
        if m: return int(m.group(1)), int(m.group(2))
    return None, None

def fmt(s):
    if not s.get('n'): return '| 0 | - | - | - | - | - | - |'
    # $10 = 1 pip at 1.00 lot
    return (f"| {s['n']} | {s['wr']:.1f}% | {s['net']:+,.0f} ({s['net']/10:+.1f} p) | {s['aw']:.2f} ({s['aw']/10:.2f} p) | "
            f"-{s['al']:.2f} ({s['al']/10:.2f} p) | {s['dd']:,.0f} | {s['coin']:.1f}% |")

if __name__ == '__main__':
    res = {}
    for f in sorted(RUNS.glob('*.json')):
        r = json.loads(f.read_text()); tr = trades(r['deals'])
        H1 = [x for x in tr if x['t'] < '2026.07.01']; H2 = [x for x in tr if x['t'] >= '2026.07.01']
        tk, bars = receipt(r)
        fails = sum('[DIAFAIL]' in l and 're-anchor' not in l for l in r['log'])
        refail = sum('re-anchor' in l and 'retcode 10016' not in l for l in r['log'])
        fires = sum('[DIAFIRE]' in l for l in r['log'])
        res[f.stem] = dict(full=stats(tr), h1=stats(H1), h2=stats(H2), ticks=tk, bars=bars, rep_trades=r.get('trades'), rep_wr=r.get('wr'),
                           rep_net=r.get('net'), rep_dd=r.get('dd'), fires=fires, order_fail=fails, reanchor_fail=refail, err=r.get('error'))
        s = res[f.stem]
        print(f"{f.stem:16s} ticks/bars {tk}/{bars}={tk/bars if tk else 0:.1f} fires {fires} fail {fails} refail {refail} | rep {s['rep_trades']} {s['rep_wr']} {s['rep_net']} dd {s['rep_dd']}")
        for k in ('full', 'h1', 'h2'): print('   ', k, fmt(s[k]), s[k].get('why'), 'zero', s[k].get('zero'))
    (Path(__file__).parent / 'summary.json').write_text(json.dumps(res, indent=1))
