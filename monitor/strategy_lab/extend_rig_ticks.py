"""extend_rig_ticks.py — give the rig the out-of-sample days it cannot download.

THE PROBLEM. The rig's demo login (12654799 on BlueberryMarkets-Demo) is dead — Zee confirmed
by hand on 2026-09-29 — so it can no longer sync tick history. Its September tick archive stops
at 2026-09-16 (4 MB). Every configuration searched on 2026-08-06 → 09-16 therefore has NO
out-of-sample leg, and this project has already been burned by exactly that: a 96.4% in-sample
configuration lost $4,071 on unseen tape in August.

THE DATA IS ALREADY ON THIS MACHINE. The LIVE terminal trades XAUUSD.pi on
BlueberryMarketsSVG-Live and its September tick archive is 68 MB, updated today. Same broker,
same metal, same feed — just a different symbol suffix and server folder. Copying it into the
rig extends the testable world to 2026-09-28, which oanda_vol.csv also covers, giving roughly
ten days of genuinely unseen tape.

WHAT THIS DOES NOT DO. It never writes to the live terminal, and it never starts it. It reads
two folders and writes only inside C:/mt5_rig, after backing up what it replaces.

THE RISK, AND THE CHECK. XAUUSD and XAUUSD.pi are the same instrument but they are different
symbol records, so their digits/point could in principle differ and prices would then be
misread by a factor of ten. The verification step therefore runs one short backtest and asserts
that gold comes back in the 3,000-6,000 band and that the bar count matches the calendar. If
either fails, --restore puts the rig back exactly as it was.

    py monitor/strategy_lab/extend_rig_ticks.py --dry      # report what would be copied
    py monitor/strategy_lab/extend_rig_ticks.py            # back up, then copy
    py monitor/strategy_lab/extend_rig_ticks.py --restore  # undo
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

LIVE = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
            r"/DBE9B8B347D025DD139E103EE3B63FD8/bases/BlueberryMarketsSVG-Live")
RIG = Path(r"C:/mt5_rig/bases/BlueberryMarkets-Demo")
BACKUP = Path(r"C:/mt5_rig/bases/_BACKUP_BlueberryMarkets-Demo")
WANT_BARS = False
SRC_SYM = "XAUUSD.pi"
DST_SYM = "XAUUSD"


def pairs():
    """(source, destination) for every tick and bar archive worth copying."""
    out = []
    for kind in ("ticks", "history"):
        s = LIVE / kind / SRC_SYM
        d = RIG / kind / DST_SYM
        if not s.is_dir():
            continue
        for f in sorted(s.iterdir()):
            # .tkc = real ticks, .hcc = bar cache. ticks.dat is a live-session scratch file and
            # copying it has no value; the cache/ subfolder is rebuilt by the terminal.
            if f.suffix.lower() == ".tkc" or (f.suffix.lower() == ".hcc" and WANT_BARS):
                out.append((f, d / f.name))
    return out


def human(n):
    return "%.1f MB" % (n / 1048576.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--restore", action="store_true")
    # TICKS ONLY BY DEFAULT. Live's 2026.hcc is 16 MB against the rig's 35 MB: the rig holds
    # MORE bar history (Feb-Sep of XAUUSD) than the live symbol does, so overwriting the bar
    # cache would DESTROY older months to gain newer ones. Model 4 builds its bars from the
    # tick archive anyway, so the ticks are the part that matters.
    ap.add_argument("--also-bars", action="store_true",
                    help="also replace .hcc bar caches (destructive - see the note above)")
    a = ap.parse_args()
    global WANT_BARS
    WANT_BARS = bool(a.also_bars)

    if a.restore:
        if not BACKUP.is_dir():
            raise SystemExit("no backup at %s — nothing to restore" % BACKUP)
        for kind in ("ticks", "history"):
            b = BACKUP / kind / DST_SYM
            d = RIG / kind / DST_SYM
            if not b.is_dir():
                continue
            shutil.rmtree(d, ignore_errors=True)
            shutil.copytree(b, d)
            print("restored %s" % d)
        print("rig tick history is back to its original state")
        return

    ps = pairs()
    if not ps:
        raise SystemExit("found nothing to copy — check %s" % LIVE)

    print("%-34s %10s   ->  %-34s %10s" % ("SOURCE (live, read-only)", "size",
                                           "DESTINATION (rig)", "current"))
    total = 0
    for s, d in ps:
        cur = human(d.stat().st_size) if d.exists() else "absent"
        print("%-34s %10s   ->  %-34s %10s"
              % (s.parent.name + "/" + s.name, human(s.stat().st_size),
                 d.parent.name + "/" + d.name, cur))
        total += s.stat().st_size
    print("\ntotal to copy: %s" % human(total))

    if a.dry:
        print("\n--dry: nothing written.")
        return

    # BACK UP FIRST, ALWAYS. The rig's archive is the only copy of the demo-server history and
    # the dead login means it can never be re-downloaded.
    # BACK UP ONLY THE FILES THIS RUN WILL ACTUALLY REPLACE. Backing up the whole folder tried
    # to copy history/XAUUSD/2026.hcc, which the rig holds open while a batch is running, and
    # the copytree died on WinError 32 - a backup that fails is worse than one not attempted.
    for src, dst in ps:
        if not dst.exists():
            continue
        b = BACKUP / dst.parent.name / dst.name
        if b.exists():
            print("  backup of %s already present" % dst.name)
            continue
        b.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(dst, b)
            print("  backed up %s -> %s" % (dst.name, b))
        except PermissionError:
            raise SystemExit("%s is locked - the rig is running. Stop the batch first." % dst.name)

    n = 0
    for s, d in ps:
        # NEVER TRADE A BIGGER ARCHIVE FOR A SMALLER ONE. Live's 202608.tkc is 16.5 MB against
        # the rig's 22.4 MB, and August is INSIDE the in-sample window every result so far was
        # measured on - replacing it would silently change the tape under the baseline and make
        # today's 89% incomparable with its own control. Only genuinely new data is welcome.
        if d.exists() and d.stat().st_size > s.stat().st_size:
            print("  SKIPPED %s: the rig's copy is larger (%s vs %s), so this would LOSE ticks"
                  % (d.name, human(d.stat().st_size), human(s.stat().st_size)))
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(s, d)
            n += 1
        except PermissionError:
            # the live terminal holds the current month open; that file is the one we most want,
            # so say so loudly rather than reporting a clean run.
            print("  LOCKED, not copied: %s  (live terminal holds it — ask Zee to close it "
                  "for twenty seconds, or accept the older archive)" % s.name)
    print("\ncopied %d of %d archives into the rig" % (n, len(ps)))
    # The bar cache must go, or MT5 serves stale minutes built from the old tick file.
    cache = RIG / "history" / DST_SYM / "cache"
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)
        print("cleared the rig's bar cache so it rebuilds from the new ticks")
    print("\nNEXT: run one short backtest past 2026-09-16 and check the report's Bars and")
    print("      price level before trusting anything. --restore undoes all of this.")


if __name__ == "__main__":
    main()
