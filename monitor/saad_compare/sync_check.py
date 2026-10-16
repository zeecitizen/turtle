"""sync_check.py - "3 · Check sync" on the compare page: is MT5 still in sync with the TradingView chart?

Zee 2026-10-16: "can you build a tool on this webpage.. a button on this webpage.. that can check for sync issues and
present a bulleted list below it, of any sync issues found/fixed"

Every check returns {"status": ok | fixed | issue | info, "title", "detail"}. What can be fixed safely is fixed here
(re-export the chart's candles, recompile the EA in the Blueberry terminal, correct the page's server-time offset);
everything else is reported with the reason and what to do. The background is the write-up at the bottom of the page
("How MT5 is synced with TradingView") and VERSION_HISTORY.md, Saad_strategy_1min v1.03 / v1.04.
"""
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import server                 # first: it puts monitor/strategy_lab on the path
import axi_rig
import tv_bars_bridge as bridge

CSV = bridge.COMMON / "tv_bars_XAUUSD.csv"
# v1.03 / v1.04 chart-alignment inputs and the value that mirrors the chart
ALIGN = {"InpBarSource": "1", "InpLockMode": "1", "InpBandAtLevel": "true", "InpUsdTrailMode": "1", "InpNoEntryExitBar": "true"}
WARMUP_MIN = 30          # the indicator draws no setup until ~iSlow*2+19 candles of history


def _r(out, status, title, detail=""):
    out.append({"status": status, "title": title, "detail": detail})


def _read_csv():
    rows = {}
    if not CSV.exists():
        return rows
    for ln in CSV.read_text(encoding="ascii", errors="ignore").splitlines():
        p = ln.split(",")
        if len(p) >= 5:
            try:
                rows[p[0]] = tuple(round(float(x), 2) for x in p[1:5])
            except ValueError:
                pass
    return rows


def _export(out, why):
    sym, n = bridge.export(CSV, more=2)
    _r(out, "fixed", "Candle file re-exported from the chart", f"{why} → {n} closed candles of {sym} written to {CSV}")


def _utc_to_server(s):
    return bridge.server_time(datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp())


def check(state, page_offset=None):
    out, fix = [], {}

    # ── A. the TradingView chart ─────────────────────────────────────────────
    try:
        tv = server.read_tv()
        state["tv"] = tv
    except Exception as e:
        _r(out, "issue", "TradingView chart not readable", f"{e}. Start TradingView with the CDP bridge and the Saad indicator on the chart.")
        return out, fix
    sym, res = tv["symbol"], str(tv["res"])
    if "BLUEBERRY" not in sym.upper():
        _r(out, "issue", f"Chart symbol is {sym}, not BLUEBERRY:XAUUSD",
           "MT5 runs on Blueberry (the same broker feed). Another broker's chart has different candles and prices; switch the chart to BLUEBERRY:XAUUSD.")
    else:
        _r(out, "ok", f"Chart is {sym}")
    if res != "1":
        _r(out, "issue", f"Chart timeframe is {res} min, not 1 min",
           "Saad_strategy_1min and the candle bridge are 1-minute. Switch the chart to 1 minute.")
    else:
        _r(out, "ok", "Chart timeframe is 1 minute")
    _r(out, "ok", f"Indicator settings read: {len(tv['settings'])} inputs match pine/saad_15min.pine; {len(tv['trades'])} chart trades")
    for n in tv["notes"]:
        _r(out, "issue", "Chart-only setting the EA does not have", n + ". Turn it off on the chart, or the two will differ.")

    # ── B. the EA ───────────────────────────────────────────────────────────
    dfl = axi_rig.ea_defaults(server.EA)
    missing = [ea for ea in list(server.DIRECT.values()) + [c[0] for c in server.CHOICES.values()] if ea not in dfl]
    if missing:
        _r(out, "issue", "Chart settings with no EA input", ", ".join(missing) + " - the page cannot pass them to MT5.")
    else:
        _r(out, "ok", f"All {len(server.DIRECT) + len(server.CHOICES)} mapped chart settings exist as EA inputs")
    bad = [f"{k}={tv['ea_sets'].get(k, dfl.get(k))} (needs {v})" for k, v in ALIGN.items() if str(tv["ea_sets"].get(k, dfl.get(k, ""))).lower() != v]
    if bad:
        _r(out, "issue", "EA alignment inputs are not on the chart's behaviour", "; ".join(bad) + ". Set them back in mt5/Saad_strategy_1min.mq5.")
    else:
        _r(out, "ok", "EA alignment inputs on: chart candles, lock per candle, band at the break level, $ trail per candle, no entry in an exit candle")
    src = server.ROOT / "mt5" / f"{server.EA}.mq5"
    ex5 = server.BB_DATA / "MQL5" / "Experts" / f"{server.EA}.ex5"
    if not ex5.exists() or ex5.stat().st_mtime < src.stat().st_mtime:
        try:
            me = server.BB_EXE.with_name("MetaEditor64.exe")
            dst = ex5.with_suffix(".mq5")
            dst.write_bytes(src.read_bytes())
            log = server.BB_DATA / "compare_compile.log"
            subprocess.run([str(me), f"/compile:{dst}", f"/log:{log}"], timeout=180)
            ok = "Result: 0 errors" in log.read_text(encoding="utf-16", errors="ignore")
            _r(out, "fixed" if ok else "issue", "EA in the Blueberry terminal was older than the code" + ("" if ok else " - compile FAILED"),
               f"Copied mt5/{server.EA}.mq5 and compiled it in the Blueberry terminal" + ("" if ok else f"; see {log}"))
        except Exception as e:
            _r(out, "issue", "EA in the Blueberry terminal is older than the code", f"could not compile: {e}")
    else:
        _r(out, "ok", "EA in the Blueberry terminal is compiled from the current code")

    # ── C. the candle file the EA reads ─────────────────────────────────────
    try:
        bsym, bars = bridge.read_bars(10 ** 6)
        bars = bridge.closed(bars)
    except Exception as e:
        bars = []
        _r(out, "issue", "Could not read the chart's candles", str(e))
    if bars:
        chart = {bridge.line(b).split(",")[0]: tuple(round(x, 2) for x in b[1:5]) for b in bars}
        fil = _read_csv()
        if not fil:
            _export(out, "the file was missing")
        else:
            common = [k for k in chart if k in fil]
            diff = [k for k in common if chart[k] != fil[k]]
            lost = [k for k in chart if k not in fil and min(fil) <= k <= max(fil)]     # holes inside the file
            tail = [k for k in chart if k > max(fil)]                                  # newer than the last export: normal
            first_trade = min((_utc_to_server(t["in"]) for t in tv["trades"]), default=None)
            short = first_trade is not None and min(fil) > (first_trade - timedelta(minutes=WARMUP_MIN)).strftime("%Y.%m.%d %H:%M")
            if diff or lost or short:
                why = []
                if diff:
                    why.append(f"{len(diff)} candle(s) differed from the chart (e.g. {diff[0]}: file {fil[diff[0]]} vs chart {chart[diff[0]]}) - the chart restated them")
                if lost:
                    why.append(f"{len(lost)} chart candle(s) were missing (e.g. {lost[0]})")
                if short:
                    why.append(f"the file started at {min(fil)}, after the chart's first trade - 30 min warm-up")
                _export(out, "; ".join(why))
            else:
                if tail:
                    bridge.export(CSV, more=0)
                _r(out, "ok", f"Candle file = the chart: {len(common)} candles identical ({min(fil)} .. {max(fil)} server time)"
                   + (f"; {len(tail)} newer candle(s) appended" if tail else ""))
        # live bridge
        cmd = ("Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Where-Object { $_.CommandLine -like '*tv_bars_bridge*--live*' } "
               "| Select-Object -ExpandProperty ProcessId")
        running = server._ps(cmd)
        last = max(_read_csv() or {"": 0})
        if running:
            _r(out, "ok", f"Live bridge running (pid {running.split()[0]}), last candle {last} server time")
        else:
            _r(out, "info", "Live bridge is not running",
               "Needed only while Saad_strategy_1min trades live on a chart: run monitor\\saad_compare\\start_tv_bars_bridge.bat and keep it open. "
               "Tests on this page do not need it (they export the candles first).")

    # ── D. time ─────────────────────────────────────────────────────────────
    now = time.time()
    off = round((bridge.server_time(now) - datetime.fromtimestamp(now, timezone.utc).replace(tzinfo=None)).total_seconds() / 3600)
    if page_offset is not None and int(float(page_offset)) != off:
        fix["offset"] = str(off)
        _r(out, "fixed", f"Page server time was UTC+{int(float(page_offset))}, the broker is on UTC+{off} now",
           "Set to UTC+%d (New York + 7 h: UTC+3 in US summer time, UTC+2 from the first Sunday of November). Run MT5 again." % off)
    else:
        _r(out, "ok", f"Server time UTC+{off} (New York + 7 h) - the page and the candle file agree")

    # ── E. the last comparison ───────────────────────────────────────────────
    mt = state.get("mt5")
    if not mt:
        _r(out, "info", "No MT5 run yet", "Press 2 · Run MT5 (Blueberry demo XAUUSD, execution delay 'none'), then check again to compare trade by trade.")
        return out, fix
    if "blueberry" not in str(mt.get("symbol", "")).lower() and "bb" not in str(mt.get("symbol", "")).lower():
        _r(out, "issue", f"Last MT5 run was on {mt.get('symbol')}", "Different broker feed than the chart - use 'Blueberry demo XAUUSD - your open terminal'.")
    if str(mt.get("delay")) not in ("0",):
        _r(out, "info", f"Last MT5 run used execution delay {mt.get('delay')}",
           "Random delay moves entries and exits by seconds and some trades into the next minute; use 'none' to check sync, random to judge money.")
    used = mt.get("sets_used")
    if used is not None:
        changed = [k for k in set(used) | set(tv["ea_sets"]) if str(used.get(k)) != str(tv["ea_sets"].get(k))]
        if changed:
            _r(out, "issue", f"Chart settings changed since the last MT5 run ({len(changed)})",
               ", ".join(f"{k} {used.get(k)} → {tv['ea_sets'].get(k)}" for k in sorted(changed)[:12]) + ". Press 2 · Run MT5 again before reading the trade list.")
    offset = float(mt.get("offset", off))
    frm, to = mt.get("frm", ""), mt.get("to", "")
    tvT = [t for t in tv["trades"] if frm <= t["in"][:10] <= to]
    mtP = list(mt.get("positions", []))
    mins = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M")
    used_i, pairs, only_tv = set(), [], []
    for t in tvT:
        best = None
        for i, p in enumerate(mtP):
            if i in used_i or p["side"] != t["side"]:
                continue
            d = abs((mins(p["in"]) - mins(t["in"])).total_seconds())
            if d <= 120 and (best is None or d < best[0]):
                best = (d, i)
        if best:
            used_i.add(best[1])
            pairs.append((t, mtP[best[1]]))
        else:
            only_tv.append(t)
    only_mt = [p for i, p in enumerate(mtP) if i not in used_i]
    last_mt = max((p["in"] for p in mtP), default="")
    fil = _read_csv()
    file_from = min(fil) if fil else ""

    def why_missing(s):
        if last_mt and s[:10] > last_mt[:10]:
            return "after the last day the Blueberry tester has ticks for (MT5 data usually ends the day before today)"
        if file_from and _utc_to_server(s).strftime("%Y.%m.%d %H:%M") < file_from:
            return "before the candle file starts - the EA has no chart candles there"
        return "unexplained - run py monitor\\saad_compare\\why_compare.py and read the EA's SETUP / SKIP lines at that minute"

    if not only_tv and not only_mt:
        _r(out, "ok", f"Trades: {len(pairs)} of {len(tvT)} chart trades are the same trade in MT5 ({frm} .. {to})")
    else:
        _r(out, "issue" if any("unexplained" in why_missing(t["in"]) for t in only_tv) else "info",
           f"Trades: {len(pairs)} of {len(tvT)} chart trades matched; {len(only_tv)} chart only, {len(only_mt)} MT5 only")
        for t in only_tv[:20]:
            r = why_missing(t["in"])
            _r(out, "issue" if "unexplained" in r else "info", f"Chart only: #{t['num']} {t['side']} {t['in']} UTC @ {t['en']:.2f} ({t['pnl']:+,.0f})", r)
        for p in only_mt[:20]:
            r = why_missing(p["in"])
            _r(out, "issue" if "unexplained" in r else "info", f"MT5 only: {p['side']} {p['in']} UTC @ {p['en']:.2f} ({p['pnl']:+,.0f})", r)
    late = [(t, p) for t, p in pairs if p.get("out") and t["out"][:16] != p["out"][:16]]
    if late:
        big = [(t, p) for t, p in late if abs(t["pnl"] - p["pnl"]) > 150]
        _r(out, "info", f"{len(late)} matched trade(s) exit in a different minute",
           "Stop hits inside a minute happen on MT5's real ticks (the chart steps per candle). "
           + ("Over $150 apart: " + "; ".join(f"#{t['num']} chart {t['out'][11:]} {t['pnl']:+,.0f} vs MT5 {p['out'][11:]} {p['pnl']:+,.0f}" for t, p in big[:8])
              if big else "None is more than $150 apart."))
    if pairs:
        cg, mg = sum(t["pnl"] for t, _ in pairs), sum(p["pnl"] for _, p in pairs)
        _r(out, "info", f"Matched trades: chart {cg:+,.0f} vs MT5 {mg:+,.0f} ({(mg - cg) / len(pairs):+,.0f} a trade)",
           "The chart fills at the break level + 0.01 with a fixed spread; MT5 pays the real spread and slippage.")
    return out, fix
