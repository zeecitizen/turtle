"""Does the TickSpeedGauge actually lead price, or only follow it?

THE ONLY TEST THAT MATTERS for this EA. Everything the gauge displays - delta, OBI, the
master band - is a hypothesis until this script says forward beats backward.

    py monitor/strategy_lab/tickspeed_calibrate.py tickspeed2_ETHUSDTp.csv

Reads the schema-2 CSV the EA writes into MT5's Common\\Files. For each signal column it
correlates the signal against the price change over the NEXT h seconds and over the PAST h
seconds, at several horizons.

    forward > backward  ->  the signal LEADS price. Real.
    backward > forward  ->  the signal FOLLOWS price. A mirror, like the old INFER delta.

Run on 2026-10-03 against 810 seconds of ETHUSDTp: delta never cleared the noise band at any
horizon, and OBI's backward correlation beat forward at EVERY horizon. See TICK_SPEED.md
section 26. The cause is in the feed - PXBT's crypto book churns every 100 ms while the mid
updates in 5% of seconds, so "consumption" is overwhelmingly the maker requoting, not
aggression.
"""
import csv
import os
import sys

COMMON = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
HORIZONS = (1, 2, 5, 15, 30, 60, 120)
SIGNALS = ('delta', 'obi_touch', 'obi_deep')


def corr(a, b):
    n = len(a)
    if n < 30:
        return float('nan')
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return float('nan')
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va ** 0.5 * vb ** 0.5)


def main(name):
    path = name if os.path.isfile(name) else os.path.join(COMMON, name)
    if not os.path.isfile(path):
        sys.exit('no such log: %s' % path)

    rows = [r for r in csv.DictReader(open(path))
            if r.get('bid') and r.get('ask') and r.get('delta')]
    if len(rows) < 120:
        sys.exit('only %d usable rows - log a longer session first' % len(rows))

    # order by the monotonic clock: TimeCurrent() freezes between ticks and repeats
    if rows[0].get('local_ms'):
        rows.sort(key=lambda r: int(r['local_ms']))

    mid = [(float(r['bid']) + float(r['ask'])) / 2 for r in rows]
    n = len(mid)
    noise = 1.0 / n ** 0.5

    print('%s' % os.path.basename(path))
    print('%d seconds   noise band +/- %.3f' % (n, noise))

    moved = [abs(mid[i + 1] - mid[i]) for i in range(n - 1)]
    live = sum(1 for m in moved if m > 1e-12)
    print('mid changed in %d of %d seconds (%.0f%%)' % (live, len(moved), 100.0 * live / len(moved)))
    if live * 20 < len(moved):
        print('*** WARNING: the price barely updates. A quote feed this sparse cannot')
        print('*** validate a 1-2 second signal no matter what the correlations say.')
    print()

    head = 'horizon | ' + ' | '.join(s.center(17) for s in SIGNALS)
    print(head)
    print('-' * len(head))
    for h in HORIZONS:
        if n - h < 60:
            continue
        cells = []
        for key in SIGNALS:
            sig = [float(r[key]) for r in rows]
            fwd = [mid[i + h] - mid[i] for i in range(n - h)]
            bwd = [mid[i] - mid[i - h] for i in range(h, n)]
            f, b = corr(sig[:len(fwd)], fwd), corr(sig[h:], bwd)
            cells.append(('%+.3f/%+.3f' % (f, b)).center(17))
        print('%6ds | %s' % (h, ' | '.join(cells)))
    print()
    print('each cell is  forward/backward.  forward must beat backward, and clear the noise')
    print('band, at a CONSISTENT horizon. One lucky cell is not a signal.')

    # the blunt version of the same question
    print()
    strong = [(float(rows[i]['delta']), mid[i + 1] - mid[i])
              for i in range(n - 1) if abs(float(rows[i]['delta'])) >= 0.90]
    if strong:
        flat = sum(1 for d, m in strong if abs(m) < 1e-12)
        same = sum(1 for d, m in strong if d * m > 0)
        print('at |delta| >= 0.90  (%d seconds of near-total one-sided flow):' % len(strong))
        print('   price did not move at all : %d  (%.0f%%)' % (flat, 100.0 * flat / len(strong)))
        print('   price moved the same way  : %d' % same)
        print('   price moved against       : %d' % (len(strong) - same - flat))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'tickspeed2_ETHUSDTp.csv')
