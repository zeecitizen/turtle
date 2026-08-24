"""oanda_deep_history.py — pull as much OANDA M1 history as TradingView will give,
and put every new minute into the permanent archive.

Zee 2026-08-25: he wants the courts run on HIS chart, never the broker's — "no no we
dont want broker feed, we want OANDA one". But anonymous tvDatafeed stops at ~8,180
M1 bars (~5.7 days) and says so itself: "you are using nologin method, data you access
may be limited". A logged-in account reaches further.

    py monitor/oanda_deep_history.py              # pull, archive, report
    py monitor/oanda_deep_history.py --probe      # just say how far back it can see

Credentials live in monitor/.tv_credentials.json (gitignored). Without them it still
runs anonymously — it simply gets less. Nothing here overwrites a settled minute:
every bar we have already recorded keeps the value we first saw, because OANDA
restates its own volume and a court cannot compare arms across a moving chart.
"""
from __future__ import annotations
import argparse
import calendar
import csv
import datetime as dt
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).parent
HIST = HERE / "strategy_lab" / "oanda_m1_history.csv"
CREDS = HERE / ".tv_credentials.json"
LADDER = (5000, 10000, 20000, 50000, 100000, 200000)


def _login():
    """(tv, how) — a logged-in feed if we can get one.

    TWO DOORS (2026-08-25). tvDatafeed 2.1.0 signs in by POSTing the password to
    /accounts/signin/, and TradingView answered that with {"code": "rate_limit"} —
    the same wall Zee hit in the browser with his backup codes. So an auth_token can
    be supplied directly instead: it is what the sign-in would have returned, it
    bypasses their login endpoint entirely, and it is a session credential rather
    than a password.

    To get one: sign in to TradingView normally, open DevTools (F12) -> Console, and
    run   window.user.auth_token   — paste the string into .tv_credentials.json as
    "auth_token".
    """
    from tvDatafeed import TvDatafeed
    if CREDS.exists():
        try:
            c = json.loads(CREDS.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  could not read credentials ({e})", flush=True)
            c = {}
        tok = (c.get("auth_token") or "").strip()
        if tok:
            tv = TvDatafeed()
            tv.token = tok                      # what __auth would have produced
            return tv, "auth_token supplied"
        u, p = (c.get("username") or "").strip(), (c.get("password") or "").strip()
        if u and p:
            tv = TvDatafeed(u, p)
            if getattr(tv, "token", None) in (None, "unauthorized_user_token"):
                print("  sign-in did not return a token (rate limit or 2FA) — "
                      "running anonymous", flush=True)
                return tv, "anonymous (sign-in refused)"
            return tv, f"logged in as {u}"
    return TvDatafeed(), "anonymous (limited history)"


def _have():
    have = {}
    if HIST.exists():
        for r in csv.DictReader(HIST.open(encoding="utf-8", errors="replace")):
            u = r.get("time_unix")
            if u:
                have[u] = True
    return have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="report reach, write nothing")
    a = ap.parse_args()

    from tvDatafeed import Interval
    tv, how = _login()
    print(f"  feed: {how}\n", flush=True)

    best = None
    for n in LADDER:
        try:
            d = tv.get_hist(symbol="XAUUSD", exchange="OANDA",
                            interval=Interval.in_1_minute, n_bars=n)
        except Exception as e:
            print(f"  asked {n:>7} -> error {e}", flush=True)
            continue
        if d is None or not len(d):
            print(f"  asked {n:>7} -> nothing", flush=True)
            continue
        print(f"  asked {n:>7} -> got {len(d):>7} bars   {d.index[0]} .. {d.index[-1]}",
              flush=True)
        if best is None or len(d) > len(best):
            best = d
        if len(d) < n:            # the server capped us; asking for more is pointless
            break
    if best is None:
        print("  nothing came back")
        return 1

    span = (best.index[-1] - best.index[0])
    print(f"\n  reach: {len(best)} bars = {span.days}d {span.seconds // 3600}h", flush=True)
    if a.probe:
        return 0

    have = _have()
    off = dt.datetime.now().astimezone().utcoffset() or dt.timedelta(0)
    new = []
    for ts, r in best.iterrows():
        utc = ts.to_pydatetime() - off
        u = str(calendar.timegm(utc.timetuple()))
        if u in have:
            continue                       # settled minutes are immutable
        new.append((u, float(r["open"]), float(r["high"]), float(r["low"]),
                    float(r["close"]), int(r["volume"])))
    if new:
        HIST.parent.mkdir(parents=True, exist_ok=True)
        write_header = not HIST.exists()
        with HIST.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["time_unix", "open", "high", "low", "close", "volume"])
            for row in new:
                w.writerow(row)
    print(f"  archived {len(new)} NEW minutes (had {len(have)})", flush=True)
    print("  now run:  py monitor/oanda_tables_backfill.py", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
