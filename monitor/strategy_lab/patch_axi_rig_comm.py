"""One-off: teach axi_rig.parse to charge commission (custom tick symbols carry none)."""
p = r'C:\Users\zeesh\turtle\monitor\strategy_lab\axi_rig.py'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep('def parse(path):\n',
    'def parse(path, comm_per_lot=0.0):\n'
    '    """comm_per_lot: charge this $ per lot per round trip on exit deals when the report shows no commission\n'
    '    (custom tick symbols carry none; Axi XAUUSD.pro charges ~$4/lot round trip)."""\n')
rep(r'r"<td>(?:buy|sell)</td><td>(in|out)</td><td>[\d.]+</td><td>[\d.]+</td>"',
    r'r"<td>(?:buy|sell)</td><td>(in|out)</td><td>([\d.]+)</td><td>[\d.]+</td>"')
rep('''    months, days, daily = {}, set(), {}
    for d, io, c, s, p in deals:
        v = num(c) + num(s) + num(p)''', '''    has_comm = any(num(c) != 0 for d, io, vol, c, s, p in deals)
    extra = 0.0
    if comm_per_lot and not has_comm:
        fixed = []
        for d, io, vol, c, s, p in deals:
            cc = -comm_per_lot * float(vol) if io == "out" else 0.0
            extra += cc
            fixed.append((d, io, vol, str(cc), s, p))
        deals = fixed
    months, days, daily = {}, set(), {}
    for d, io, vol, c, s, p in deals:
        v = num(c) + num(s) + num(p)''')
rep('''    tr, cur = [], None
    for d, io, c, s, p in deals:''', '''    tr, cur = [], None
    for d, io, vol, c, s, p in deals:''')
rep('''    net = num(field("Total Net Profit") or "0")''', '''    net = num(field("Total Net Profit") or "0") + extra''')
rep('''    r = parse(rep)
    r.update(tag=tag''', '''    r = parse(rep, comm_per_lot=4.0 if symbol.endswith("_TK") else 0.0)
    r["comm_added"] = symbol.endswith("_TK")
    r.update(tag=tag''')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
