"""build_setup_review.py — draw every setup an EA took over a date range, and put a
comment box under each, as ONE self-contained HTML file.

Zee, 2026-09-07: "i want to comment on all setups taken by the ZeeUHV_diamond EA in the
last week. What this does is, it lets me verify whether the EA is taking trades as
expected or not. since this strategy of diamond is VISUAL. i wanna make sure visually
whether everything is ok."

THE DRAWING TOOL ALREADY EXISTS and is not reimplemented here. Every chart comes from
monitor/forensic_chart.py — draw_trade() for the marked-up setup (UHV, trigger,
breakout, entry, exit) and draw_context() for the zoomed-out circumstances. This file
selects the baskets, calls that tool, and lays the result out.

Three things this gets right that the single-day version did not:

1. A BASKET IS ONE DECISION, EVEN WHEN THE BROKER SPLITS IT. The 8 tickets of the
   01 Sep 00:42 basket closed across three consecutive SECONDS and appeared as three
   separate cards showing -237.40, -121.20 and -602.70 — three chances to misread one
   -961.30 event. Closes within MERGE_SEC of each other, same side and magic, are one
   card now.

2. COMMENTS ARE KEYED BY THE TRADE, NOT ITS POSITION. The old key was "{day}-{index}",
   so rebuilding a page with one extra trade slid every note onto the wrong setup.
   The key is now the broker timestamp, which never moves.

3. THE CHART IS DRAWN ON THE FEED THE EA JUDGED. Until v1.15 the Diamond ranked UHVs on
   BROKER volume; drawing it on OANDA marks a candle it never chose. Each card says
   which feed it used, and — because Zee has just moved the machine to his own chart —
   also reports whether OANDA would have crowned the SAME candle. That column is the
   visual verification he is actually asking for.

    py monitor/build_setup_review.py --from 2026-08-31 --to 2026-09-06 --ea ZeeUHV_Diamond
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import forensic_chart as FC  # noqa: E402  the existing drawing tool

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
FILLS = COMMON / "turtle_fills.csv"
OVOL = COMMON / "oanda_vol.csv"
OUT = ROOT / "dashboard" / "reviews"

BROKER_TO_PKT_H = 2          # broker clock is UTC+3, Zee reads PKT = UTC+5
MERGE_SEC = 15               # closes this close together are one decision

EA_NAME = {"88154": "ZeeUHV_Diamond", "88184": "BasedOnLaws", "0": "Zee (manual)"}
MAGIC_OF = {v: k for k, v in EA_NAME.items()}
# Which feed each EA ranked UHVs on during the reviewed period. The Diamond moved to
# OANDA on 2026-09-06 (v1.15); everything before that is broker.
EA_FEED = {"88154": "broker", "88184": "OANDA", "0": "broker"}
# Zee 2026-09-08: "write the EA name near the time of each trade setup so we know
# which EA took which setup". Short labels, because the badge sits beside the
# clock and a full class name would push the time off a phone screen.
EA_SHORT = {"88154": "Diamond", "88184": "BasedOnLaws", "0": "Manual"}
EA_CLASS = {"88154": "dia", "88184": "law", "0": "man"}
DIAMOND_OANDA_FROM = datetime(2026, 9, 7)     # first PKT day of the new default


def load_oanda_vol():
    """server-time -> volume. Server/broker clock, the same one the EA logs."""
    out = {}
    try:
        for ln in open(OVOL, encoding="utf-8", errors="replace"):
            c = ln.find(",")
            if c <= 0:
                continue
            try:
                t = datetime.strptime(ln[:c].strip(), "%Y.%m.%d %H:%M")
            except ValueError:
                continue
            try:
                out[t] = int(ln[c + 1:].strip())
            except ValueError:
                pass
    except FileNotFoundError:
        print("[review] oanda_vol.csv not found — cross-feed check unavailable")
    return out


def baskets(frm_pkt, to_pkt, magic):
    """Fills -> decisions. Merges closes within MERGE_SEC (the broker splits a basket
    across seconds; three cards for one event is three chances to misread it)."""
    rows = []
    with open(FILLS, encoding="utf-8", errors="replace") as f:
        for x in csv.reader(f):
            if len(x) < 13 or x[0] == "broker_time":
                continue
            if magic and x[12].strip() != magic:
                continue
            bt = datetime.strptime(x[0], "%Y.%m.%d %H:%M:%S")
            pkt = bt + timedelta(hours=BROKER_TO_PKT_H)
            if not (frm_pkt <= pkt < to_pkt):
                continue
            rows.append((bt, pkt, x))
    rows.sort(key=lambda r: r[0])

    out = []
    for bt, pkt, x in rows:
        side = x[4].replace("_closed", "")
        cur = out[-1] if out else None
        if (cur and cur["side"] == side and cur["magic"] == x[12].strip()
                and (bt - cur["bt_last"]).total_seconds() <= MERGE_SEC):
            b = cur
        else:
            b = {"broker_ts": x[0], "bt": bt, "bt_last": bt, "pkt": pkt,
                 "magic": x[12].strip(), "side": side, "tickets": 0, "lots": 0.0,
                 "exit_px": 0.0, "net": 0.0, "gross": 0.0, "swap": 0.0,
                 "comment": x[11], "split": 0}
            out.append(b)
        b["bt_last"] = bt
        b["tickets"] += 1
        b["lots"] += float(x[5])
        b["exit_px"] = float(x[6])
        b["gross"] += float(x[7])
        b["swap"] += float(x[9])
        b["net"] += float(x[10])
        if x[11].strip() and not b["comment"].strip():
            b["comment"] = x[11]
        if bt != b["bt"]:
            b["split"] = int((bt - b["bt"]).total_seconds())
    return out


def cross_feed(fire, ovol):
    """Would HIS chart have crowned the same candle? Compares the EA's chosen UHV with
    OANDA's loudest minute over the SAME retracement (origin -> breakout), all in
    broker time, which is the clock the fire line prints inside itself."""
    if not ovol or not fire:
        return None
    g = re.search(r"origin \w+ (\d\d):(\d\d).*UHV (\d\d):(\d\d) \(vol (\d+).*"
                  r"breakout (\d\d):(\d\d)", fire)
    m = re.search(r"(\d\d):(\d\d):\d\d.*\[LAWX\]", fire)
    if not (g and m):
        return None
    fire_pkt_h, fire_pkt_m = int(m.group(1)), int(m.group(2))
    # the log prefix is PKT; everything printed inside the line is broker (PKT-2)
    base = datetime(2000, 1, 1)          # date filled in by the caller via anchor
    return {"raw": g, "fire_hm": (fire_pkt_h, fire_pkt_m), "base": base}


def cross_feed_at(fire, ovol, entry_utc):
    if not ovol or not fire or entry_utc is None:
        return None
    g = re.search(r"origin \w+ (\d\d):(\d\d).*UHV (\d\d):(\d\d) \(vol (\d+).*"
                  r"breakout (\d\d):(\d\d)", fire)
    if not g:
        return None
    fire_broker = entry_utc + timedelta(hours=3)

    def at(hh, mm):
        t = fire_broker.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if t > fire_broker + timedelta(minutes=1):
            t -= timedelta(days=1)       # the fire crossed midnight
        return t

    o = at(int(g.group(1)), int(g.group(2)))
    u = at(int(g.group(3)), int(g.group(4)))
    ea_vol = int(g.group(5))
    b = at(int(g.group(6)), int(g.group(7)))
    if b < o:
        return None
    win = []
    t = o
    while t <= b:
        if t in ovol:
            win.append((ovol[t], t))
        t += timedelta(minutes=1)
    if not win:
        return {"ok": None, "note": "his chart has no data for this retracement"}
    best_v, best_t = max(win)
    return {"ok": (best_t == u), "ea_uhv": u, "ea_vol": ea_vol,
            "oanda_uhv": best_t, "oanda_vol": best_v,
            "oanda_at_ea": ovol.get(u), "bars": len(win)}


def b64(p):
    if not p or not Path(p).exists():
        return None
    return base64.b64encode(Path(p).read_bytes()).decode("ascii")


def how_closed(c):
    c = (c or "").strip()
    if c.startswith("[tp"):
        return "hit target"
    if c.startswith("[sl"):
        return "stopped out"
    return "closed at market" if not c else c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default="2026-08-31")
    ap.add_argument("--to", dest="to", default="2026-09-06", help="exclusive, PKT")
    ap.add_argument("--ea", default="ZeeUHV_Diamond",
                    help="EA name, or 'all' for every source that traded")
    ap.add_argument("--today", action="store_true",
                    help="the current PKT day, for the dashboard button")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    # "all" keeps every magic — the dashboard button says "today's trades", not
    # "the Diamond's trades", and a manual fill that moved the account belongs on it.
    magic = None if args.ea.lower() == "all" else MAGIC_OF.get(args.ea)
    if magic is None and args.ea.lower() != "all":
        sys.exit("unknown EA " + args.ea + "; known: " + ", ".join(MAGIC_OF) + ", all")
    if args.today:
        # PKT day, because that is the day Zee is looking at. The broker clock is
        # UTC+3 and the fills are stamped in it, so the window is done in PKT and
        # baskets() converts each fill before comparing.
        now_pkt = datetime.utcnow() + timedelta(hours=5)
        frm = datetime(now_pkt.year, now_pkt.month, now_pkt.day)
        to = frm + timedelta(days=1)
    else:
        frm = datetime.strptime(args.frm, "%Y-%m-%d")
        to = datetime.strptime(args.to, "%Y-%m-%d")

    rows = baskets(frm, to, magic)
    if not rows:
        # An empty day is a legitimate answer, not an error — the button must still
        # open a page rather than a 500.
        print("no baskets between %s and %s (PKT)" % (frm.date(), to.date()))
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(empty_page(args.ea, frm), encoding="utf-8")
            print("[review] -> " + args.out + "  (empty day)")
        return
    ovol = load_oanda_vol()
    print(f"[review] {args.ea}: {len(rows)} decisions, {args.frm} -> {args.to} "
          f"(PKT); OANDA table {len(ovol)} minutes")

    for i, b in enumerate(rows, 1):
        print(f"[review] {i}/{len(rows)}  {b['pkt']:%a %d %H:%M:%S}  {b['side']} "
              f"{b['tickets']}tk …", flush=True)
        feed = EA_FEED.get(b["magic"], "OANDA")
        if b["magic"] == "88154" and b["pkt"] >= DIAMOND_OANDA_FROM:
            feed = "OANDA"
        b["feed"] = feed
        FC.FORCE_BROKER_BARS = (feed == "broker")

        b["rr"] = None
        b["xf"] = None
        b["uhv_vol"] = None
        try:
            r = FC.resolve_trade(b["broker_ts"], b["side"], ea=args.ea)
            fire = (r or {}).get("fire") or ""
            g = re.search(r"entry ([\d.]+) stop ([\d.]+) target ([\d.]+)", fire)
            if g:
                en, sl, tp = (float(g.group(k)) for k in (1, 2, 3))
                risk, rew = abs(en - sl), abs(tp - en)
                b["rr"] = {"entry": en, "stop": sl, "target": tp, "risk": risk,
                           "reward": rew, "r": (rew / risk if risk else None)}
            v = re.search(r"UHV \d\d:\d\d \(vol (\d+)", fire)
            b["uhv_vol"] = int(v.group(1)) if v else None
            b["xf"] = cross_feed_at(fire, ovol, (r or {}).get("entry_utc"))
        except Exception as e:
            print(f"           geometry unavailable: {e}")

        setup = ctx = None
        try:
            setup = FC.draw_trade(b["broker_ts"], b["side"], b["exit_px"], ea=args.ea)
        except Exception as e:
            print(f"           setup chart failed: {e}")
        try:
            ctx = FC.draw_context(b["broker_ts"], b["side"])
        except Exception as e:
            print(f"           context chart failed: {e}")
        b["setup_b64"] = b64(setup)
        b["ctx_b64"] = b64(ctx)
        # A CHART THAT FAILED MUST SAY SO. A missing image reads as "no setup here",
        # which is a different and wrong claim.
        b["setup_err"] = None if b["setup_b64"] else "chart could not be drawn"

    dest = Path(args.out) if args.out else OUT / f"review_{args.ea}_{args.frm}_{args.to}.html"
    # mkdir the parent of the REQUESTED path, not just the default one. The
    # dashboard passes --out into its own folder; creating only OUT left the write
    # to fail with ENOENT and the route served a 500 that read like a build error.
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(rows, args.ea, frm, to), encoding="utf-8")
    print(f"[review] -> {dest}  ({dest.stat().st_size/1e6:.1f} MB)")
    return dest


def empty_page(ea, frm):
    return ("<title>Today's Setups</title>"
            "<style>body{margin:0;background:#0d0f13;color:#e7e9ee;"
            "font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            "display:grid;place-items:center;min-height:100vh;text-align:center}"
            "h1{font-size:22px;margin:0 0 6px}p{color:#98a0af;margin:0}</style>"
            "<div><h1>No trades yet today</h1><p>" + html.escape(ea)
            + " has not fired on " + frm.strftime("%A %d %B") + " (PKT). "
            "This page fills in as setups are taken.</p></div>")


def render(cards, ea, frm, to):
    net = sum(c["net"] for c in cards)
    wins = sum(1 for c in cards if c["net"] > 0)
    gross = sum(c["gross"] for c in cards)
    agree = [c for c in cards if c.get("xf") and c["xf"].get("ok") is True]
    disagree = [c for c in cards if c.get("xf") and c["xf"].get("ok") is False]

    nav, secs, last_day = [], [], None
    for i, c in enumerate(cards):
        cls = "win" if c["net"] > 0 else ("flat" if abs(c["net"]) < 0.005 else "loss")
        day = f"{c['pkt']:%a %d %b}"
        if day != last_day:
            nav.append(f'<h4>{day}</h4>')
            secs.append(f'<h3 class="daybar" id="d{i}">{day}</h3>')
            last_day = day
        nav.append(f'<a href="#s{i}"><span class="n">{i+1}</span>'
                   f'<span class="t">{c["pkt"]:%H:%M}</span>'
                   f'<span class="e"><b class="{EA_CLASS.get(c["magic"], "man")}">'
                   f'{html.escape(EA_SHORT.get(c["magic"], c["magic"]))}</b> '
                   f'{html.escape(c["side"])}</span>'
                   f'<span class="p {cls}">{c["net"]:+.2f}</span></a>')

        rr, geom = c.get("rr"), ""
        if rr:
            rv = f'{rr["r"]:.2f}R' if rr["r"] is not None else "—"
            geom = ('<div class="geo">'
                    f'<div><dt>entry</dt><dd>{rr["entry"]:.2f}</dd></div>'
                    f'<div><dt>stop</dt><dd>{rr["stop"]:.2f}</dd></div>'
                    f'<div><dt>target</dt><dd>{rr["target"]:.2f}</dd></div>'
                    f'<div><dt>risk</dt><dd>{rr["risk"]:.2f}</dd></div>'
                    f'<div><dt>reward</dt><dd>{rr["reward"]:.2f}</dd></div>'
                    f'<div class="hi"><dt>ratio</dt><dd>{rv}</dd></div></div>')

        xf, xfh = c.get("xf"), ""
        if xf and xf.get("ok") is True:
            xfh = (f'<p class="xf ok">Your chart agrees — OANDA\'s loudest bar of this '
                   f'retracement is the same minute the EA chose '
                   f'({xf["ea_uhv"]:%H:%M} broker, OANDA vol {xf["oanda_vol"]}).</p>')
        elif xf and xf.get("ok") is False:
            at_ea = xf.get("oanda_at_ea")
            at_ea_s = f'{at_ea}' if at_ea is not None else 'no data'
            xfh = (f'<p class="xf bad">Your chart disagrees — the EA chose '
                   f'{xf["ea_uhv"]:%H:%M} (broker vol {xf["ea_vol"]}, OANDA {at_ea_s}), '
                   f'but OANDA\'s loudest bar of this retracement is '
                   f'{xf["oanda_uhv"]:%H:%M} at {xf["oanda_vol"]}.</p>')
        elif xf and xf.get("note"):
            xfh = f'<p class="xf none">{html.escape(xf["note"])}</p>'

        figs = []
        if c["setup_b64"]:
            figs.append('<figure><figcaption>The setup — UHV, trigger, breakout, entry, exit'
                        '</figcaption><img src="data:image/png;base64,'
                        f'{c["setup_b64"]}" alt="Marked-up setup chart"></figure>')
        else:
            figs.append(f'<p class="err">{html.escape(c["setup_err"])}</p>')
        if c["ctx_b64"]:
            figs.append('<figure><figcaption>The circumstances — zoomed out</figcaption>'
                        f'<img src="data:image/png;base64,{c["ctx_b64"]}" alt="Context chart"></figure>')

        swp = (f'<div><dt>swap</dt><dd class="loss">{c["swap"]:+.2f}</dd></div>'
               if abs(c["swap"]) >= 0.005 else "")
        vol = (f'<div><dt>UHV vol</dt><dd>{c["uhv_vol"]}</dd></div>'
               if c.get("uhv_vol") else "")
        split = (f'<div><dt>fills spread</dt><dd>{c["split"]}s</dd></div>'
                 if c.get("split") else "")

        secs.append(f"""
<section class="setup" id="s{i}">
  <header>
    <span class="idx">{i+1}</span>
    <div class="who">
      <h2>{c['pkt']:%H:%M:%S}<span class="tz">PKT</span>
        <span class="eabadge {EA_CLASS.get(c['magic'], 'man')}">{html.escape(EA_SHORT.get(c['magic'], 'magic ' + c['magic']))}</span>
      </h2>
      <p><span class="side {c['side'].lower()}">{html.escape(c['side'])}</span>
         · {c['tickets']} tickets · {c['lots']:.2f} lots</p>
    </div>
    <div class="money"><b class="{cls}">{c['net']:+.2f}</b>
      <span class="how">{html.escape(how_closed(c['comment']))}</span></div>
  </header>
  <dl class="facts">
    <div><dt>gross</dt><dd>{c['gross']:+.2f}</dd></div>
    {swp}<div><dt>exit</dt><dd>{c['exit_px']:.2f}</dd></div>
    {vol}<div><dt>judged on</dt><dd>{c['feed']} volume</dd></div>{split}
  </dl>
  {geom}{xfh}{''.join(figs)}
  <div class="note">
    <label for="c{i}">Your comment on this setup</label>
    <textarea id="c{i}" data-k="{c['broker_ts']}" rows="4"
      placeholder="Is this a setup by your laws? Right UHV, right breakout, right exit?"></textarea>
    <span class="ok" id="ok{i}"></span>
  </div>
</section>""")

    xfline = ""
    if agree or disagree:
        tot = len(agree) + len(disagree)
        xfline = (f'<p class="xfsum">Cross-feed check: on <b>{len(agree)} of {tot}</b> '
                  f'setups your OANDA chart crowns the same candle the EA did. '
                  f'<b>{len(disagree)}</b> differ.</p>')

    return f"""<title>Today's Setups</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap">
<style>
  :root {{
    --ground:#f1f2f5; --surface:#ffffff; --sunk:#e9ebef;
    --ink:#15171c; --dim:#656c7a; --line:#e2e5ea;
    --gold:#a8781a; --gold-soft:#f0e2c4;
    --win:#0e7a4f; --loss:#c0392b;
    --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    --disp:"Archivo",var(--sans);
    --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  }}
  @media (prefers-color-scheme:dark) {{ :root:not([data-theme="light"]) {{
    --ground:#0d0f13; --surface:#161920; --sunk:#11141a;
    --ink:#e7e9ee; --dim:#98a0af; --line:#242832;
    --gold:#d9a53c; --gold-soft:#3a2f18; --win:#35c98d; --loss:#ff6f6a;
  }} }}
  :root[data-theme="dark"] {{
    --ground:#0d0f13; --surface:#161920; --sunk:#11141a;
    --ink:#e7e9ee; --dim:#98a0af; --line:#242832;
    --gold:#d9a53c; --gold-soft:#3a2f18; --win:#35c98d; --loss:#ff6f6a;
  }}
  *,*::before,*::after {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--ground); color:var(--ink); font-family:var(--sans);
    font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased; }}
  .masthead {{ border-bottom:1px solid var(--line); background:var(--surface); }}
  .mast-in {{ max-width:1080px; margin:0 auto; padding:26px 22px 20px; }}
  .eyebrow {{ font-family:var(--mono); font-size:11.5px; letter-spacing:.14em;
    text-transform:uppercase; color:var(--gold); margin:0 0 6px; }}
  h1 {{ font-family:var(--disp); font-weight:700; font-size:30px; letter-spacing:-.02em;
    margin:0 0 6px; text-wrap:balance; }}
  .lede {{ color:var(--dim); margin:0; max-width:64ch; }}
  .xfsum {{ margin:12px 0 0; font-size:14px; color:var(--dim); max-width:64ch; }}
  .tape {{ display:flex; flex-wrap:wrap; margin-top:20px; border:1px solid var(--line);
    border-radius:3px; overflow:hidden; }}
  .tape div {{ flex:1 1 110px; padding:11px 15px; border-right:1px solid var(--line); }}
  .tape div:last-child {{ border-right:0; }}
  .tape dt {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.12em;
    text-transform:uppercase; color:var(--dim); }}
  .tape dd {{ margin:2px 0 0; font-family:var(--mono); font-weight:600; font-size:19px;
    font-variant-numeric:tabular-nums; }}
  .page {{ max-width:1080px; margin:0 auto; padding:0 22px 90px;
    display:grid; grid-template-columns:200px 1fr; gap:34px; align-items:start; }}
  @media (max-width:860px) {{ .page {{ grid-template-columns:1fr; gap:0; }} nav {{ display:none; }} }}
  nav {{ position:sticky; top:18px; padding-top:26px; max-height:92vh; overflow-y:auto; }}
  nav h4 {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.13em;
    text-transform:uppercase; color:var(--gold); margin:14px 0 6px; font-weight:500; }}
  nav h4:first-child {{ margin-top:0; }}
  nav a {{ display:grid; grid-template-columns:18px 42px 1fr auto; gap:7px;
    align-items:baseline; padding:5px 0; border-bottom:1px solid var(--line);
    color:inherit; text-decoration:none; font-size:12.5px; }}
  nav a:hover .t, nav a:focus-visible .t {{ color:var(--gold); }}
  nav .n {{ font-family:var(--mono); color:var(--dim); }}
  nav .t {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}
  nav .e {{ color:var(--dim); font-size:11px; }}
  nav .p {{ font-family:var(--mono); font-variant-numeric:tabular-nums; font-size:11.5px; }}
  .daybar {{ font-family:var(--mono); font-size:11px; letter-spacing:.16em;
    text-transform:uppercase; color:var(--gold); margin:34px 0 0; padding-bottom:7px;
    border-bottom:2px solid var(--gold-soft); }}
  .setup {{ padding:28px 0 26px; border-bottom:1px solid var(--line); scroll-margin-top:16px; }}
  .setup header {{ display:grid; grid-template-columns:auto 1fr auto; gap:14px; align-items:start; }}
  .idx {{ font-family:var(--mono); font-size:12px; font-weight:600; color:var(--gold);
    background:var(--gold-soft); border-radius:2px; padding:3px 7px; line-height:1.2; }}
  .eabadge {{ font-family:var(--mono); font-size:10.5px; font-weight:600;
    letter-spacing:.08em; text-transform:uppercase; padding:3px 8px; border-radius:3px;
    margin-left:10px; vertical-align:2px; border:1px solid; }}
  .eabadge.dia {{ color:var(--gold); border-color:var(--gold); background:var(--gold-soft); }}
  .eabadge.law {{ color:#5b8def; border-color:#5b8def; background:rgba(91,141,239,.12); }}
  .eabadge.man {{ color:var(--dim); border-color:var(--line); background:var(--sunk); }}
  nav .e b {{ font-weight:600; }}
  nav .e b.dia {{ color:var(--gold); }}
  nav .e b.law {{ color:#5b8def; }}
  nav .e b.man {{ color:var(--dim); }}
  .who h2 {{ font-family:var(--disp); font-size:21px; font-weight:600; margin:0;
    font-variant-numeric:tabular-nums; letter-spacing:-.01em; }}
  .tz {{ font-family:var(--mono); font-size:10.5px; color:var(--dim); margin-left:7px;
    letter-spacing:.1em; }}
  .who p {{ margin:2px 0 0; color:var(--dim); font-size:13px; }}
  .side.buy {{ color:var(--win); font-weight:500; }}
  .side.sell {{ color:var(--loss); font-weight:500; }}
  .money {{ text-align:right; }}
  .money b {{ display:block; font-family:var(--mono); font-size:23px; font-weight:600;
    font-variant-numeric:tabular-nums; letter-spacing:-.02em; }}
  .how {{ font-size:11.5px; color:var(--dim); font-family:var(--mono); letter-spacing:.04em; }}
  .win {{ color:var(--win); }} .loss {{ color:var(--loss); }} .flat {{ color:var(--dim); }}
  .facts, .geo {{ display:flex; flex-wrap:wrap; gap:0 26px; margin:16px 0 0; }}
  .geo {{ margin-top:11px; padding:11px 15px; background:var(--sunk);
    border-left:2px solid var(--gold); border-radius:0 3px 3px 0; }}
  .facts div, .geo div {{ display:flex; flex-direction:column; }}
  dt {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.11em;
    text-transform:uppercase; color:var(--dim); }}
  dd {{ margin:1px 0 0; font-family:var(--mono); font-variant-numeric:tabular-nums;
    font-size:14.5px; }}
  .geo .hi dd {{ color:var(--gold); font-weight:600; }}
  .xf {{ margin:12px 0 0; padding:9px 13px; font-size:13.5px; border-radius:3px;
    border-left:2px solid var(--dim); background:var(--sunk); }}
  .xf.ok {{ border-left-color:var(--win); }}
  .xf.bad {{ border-left-color:var(--loss); }}
  figure {{ margin:20px 0 0; }}
  figcaption {{ font-size:12px; color:var(--dim); margin-bottom:7px; }}
  img {{ display:block; width:100%; height:auto; border:1px solid var(--line);
    border-radius:3px; background:#fff; }}
  .err {{ margin:20px 0 0; padding:11px 14px; font-size:13.5px; color:var(--loss);
    border:1px solid var(--loss); border-radius:3px; }}
  .note {{ margin-top:22px; background:var(--surface); border:1px solid var(--line);
    border-radius:4px; padding:14px 16px 12px; }}
  .note label {{ display:block; font-family:var(--mono); font-size:10.5px;
    letter-spacing:.12em; text-transform:uppercase; color:var(--dim); margin-bottom:8px; }}
  textarea {{ width:100%; background:transparent; color:var(--ink);
    font-family:var(--sans); font-size:14.5px; line-height:1.6; border:0;
    border-bottom:1px solid var(--line); padding:0 0 8px; resize:vertical; }}
  textarea:focus {{ outline:0; border-bottom-color:var(--gold); }}
  .ok {{ display:block; height:15px; margin-top:6px; font-family:var(--mono);
    font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--win); }}
  .bar {{ position:sticky; bottom:0; z-index:5; background:var(--surface);
    border-top:1px solid var(--line); }}
  .bar-in {{ max-width:1080px; margin:0 auto; padding:11px 22px; display:flex;
    gap:10px; align-items:center; flex-wrap:wrap; }}
  button {{ font-family:var(--sans); font-size:13.5px; font-weight:500; padding:8px 15px;
    border-radius:3px; border:1px solid var(--gold); background:var(--gold);
    color:#fff; cursor:pointer; }}
  :root[data-theme="dark"] button {{ color:#1a1408; }}
  @media (prefers-color-scheme:dark) {{ :root:not([data-theme="light"]) button {{ color:#1a1408; }} }}
  button.ghost {{ background:transparent; color:var(--gold); }}
  button:focus-visible, a:focus-visible {{ outline:2px solid var(--gold); outline-offset:2px; }}
  .msg {{ font-size:12.5px; color:var(--dim); }}
  @media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>

<header class="masthead">
  <div class="mast-in">
    <p class="eyebrow">XAUUSD · magic 88154 · visual verification</p>
    <h1>{html.escape(ea)} — {frm:%d %b} to {to - timedelta(days=1):%d %b %Y}</h1>
    <p class="lede">Every decision the EA made, drawn on the feed it actually judged.
      One card per <b>basket</b>: eight tickets on one setup is one decision, even when
      the broker splits the fills across seconds. All times PKT.</p>
    {xfline}
    <dl class="tape">
      <div><dt>decisions</dt><dd>{len(cards)}</dd></div>
      <div><dt>won</dt><dd>{wins} / {len(cards)}</dd></div>
      <div><dt>gross</dt><dd>{gross:+.2f}</dd></div>
      <div><dt>net</dt><dd class="{'win' if net > 0 else 'loss'}">{net:+.2f}</dd></div>
    </dl>
  </div>
</header>

<div class="page">
  <nav>{''.join(nav)}</nav>
  <main>{''.join(secs)}</main>
</div>

<div class="bar"><div class="bar-in">
  <button type="button" onclick="copyAll()">Copy all comments</button>
  <button type="button" class="ghost" onclick="clearAll()">Clear all</button>
  <span class="msg" id="msg">Notes save as you type — in this browser only.</span>
</div></div>

<script>
const TAS = [...document.querySelectorAll('textarea')];
TAS.forEach(t => {{
  // keyed by the BROKER TIMESTAMP, not the card's position, so rebuilding the page
  // with more trades in it never slides a note onto the wrong setup
  const k = 'rv:' + t.dataset.k;
  try {{ const v = localStorage.getItem(k); if (v) t.value = v; }} catch (e) {{}}
  let timer;
  t.addEventListener('input', () => {{
    clearTimeout(timer);
    timer = setTimeout(() => {{
      try {{ localStorage.setItem(k, t.value); }} catch (e) {{}}
      const ok = document.getElementById('ok' + t.id.slice(1));
      if (ok) {{ ok.textContent = 'saved'; setTimeout(() => {{ ok.textContent = ''; }}, 1400); }}
    }}, 400);
  }});
}});
function collect() {{
  return TAS.filter(t => t.value.trim()).map(t => {{
    const s = t.closest('.setup');
    return '### ' + s.querySelector('h2').innerText.replace(/\\s+/g, ' ').trim()
         + ' — ' + s.querySelector('.who p').innerText.replace(/\\s+/g, ' ').trim()
         + '  [' + s.querySelector('.money b').textContent.trim() + ']'
         + '  (' + t.dataset.k + ' broker)\\n' + t.value.trim();
  }}).join('\\n\\n');
}}
function copyAll() {{
  const txt = collect(), msg = document.getElementById('msg');
  if (!txt) {{ msg.textContent = 'No comments written yet.'; return; }}
  navigator.clipboard.writeText(txt).then(
    () => {{ msg.textContent = 'Copied — paste it back to Claude.'; }},
    () => {{ msg.textContent = 'Copy blocked; select the text by hand.'; }});
}}
function clearAll() {{
  if (!confirm('Erase every comment on this page?')) return;
  TAS.forEach(t => {{ t.value = ''; try {{ localStorage.removeItem('rv:' + t.dataset.k); }} catch (e) {{}} }});
  document.getElementById('msg').textContent = 'Cleared.';
}}
</script>
"""


if __name__ == "__main__":
    main()
