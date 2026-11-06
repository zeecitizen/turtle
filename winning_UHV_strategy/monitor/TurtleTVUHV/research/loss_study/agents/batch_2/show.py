import json, sys
b = json.load(open('batch_2.json'))
cards = {c['id']: c for c in b['losses'] + b['twins']}
ids = sys.argv[1:]
n = 18
for i in ids:
    c = cards[i]
    print(f"== {i} {c['outcome']} side {c['side']} level {c['level']} extreme {c['extreme']} fill {c['fill']:.5f} stop {c['stop']:.5f} uhv_v {c['uhv_v']} brk {c['brk_ticks_so_far']} box {c['box']} cam {c['camEff']}x{c['camStk']} entry {c['entry_pkt']} uhv@{c['uhv_candle_pkt']} atr {c['atr_pips']} adx {c['adx']}")
    rows = c['last40_closed_candles_pkt_ohlcv']
    hi40 = max(r[2] for r in rows); lo40 = min(r[3] for r in rows)
    print(f"   40-bar hi {hi40} lo {lo40} range {(hi40-lo40)*1e4:.1f}p ; level vs hi {(c['level']-hi40)*1e4:+.1f}p vs lo {(c['level']-lo40)*1e4:+.1f}p")
    for r in rows[-n:]:
        print('   ', r[0], f"{r[1]:.5f} {r[2]:.5f} {r[3]:.5f} {r[4]:.5f}", r[5], 'G' if r[4] >= r[1] else 'R')
