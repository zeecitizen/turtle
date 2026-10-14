"""Summary page for the PXBT trades of 13-14 Oct 2026: trades/review-20261014.html (served at /saad-review).
Importing build_trade_pages also (re)writes the six single-trade pages."""
from build_trade_pages import CSS, FIX, OUT, money

ROWS = [
    ("67046250", "13 Oct 8:01 PM", "SELL 2", "4165.57 → 4151.58", 2799, "Pin bar on the 9 EMA with the trend. TP1 banked, rest trailed. Worked exactly as designed."),
    ("67082390", "13 Oct 10:23 PM", "BUY 0.1", "4156.63 → 4156.22", -4.10, "An old v1.11 copy on Claude's PC, on a 1-minute chart by mistake. Closed by hand; copy removed."),
    ("67099697", "13 Oct 11:45 PM", "BUY 2", "4162.51 → 4160.39", -424, "Bounce off the 9 EMA in a falling market; never near TP1; shut by the daily-close rule."),
    ("67111138", "14 Oct 3:01 AM", "BUY 2", "4162.39 → 4154.77", -1524, "Setup from before the daily break, bought at the reopen (a code hole). Stopped at the night's exact low."),
    ("67117659", "14 Oct 5:33 AM", "SELL 2", "4157.62 → 4157.62", 0, "Reached breakeven, missed TP1 by 66 cents, then an $11 snap-back. The breakeven step saved $1,828."),
    ("67138222", "14 Oct 8:16 AM", "BUY 2", "4169.02 → 4158.02", -2200, "Pin bar on the 50 EMA, bought at the top of a rally, no target. Best move +$1.37."),
    ("67144848", "14 Oct 9:45 AM", "BUY 2", "4166.69 → 4157.63", -1812, "EMAs merged (no trend), chop exactly at the limit, no target. Best move +$0.37."),
    ("67182851", "14 Oct 1:31 PM", "SELL 2", "4149.33 → 4144.30", 1007, "Pin bar on the 9 EMA with the trend. TP1 banked, rest trailed. Worked as designed."),
]


def cell(tk):
    return f'<a href="/trade{tk}.html">{tk}</a>' if tk not in ("67182851",) else tk


rows = "\n".join(
    f'<tr><td class="t">{d}</td><td class="t">{cell(tk)}</td><td class="t">{side}</td><td class="t">{px}</td>'
    f'<td class="n {"pos" if pnl > 0 else "neg" if pnl < 0 else ""}">{("+" if pnl > 0 else "−" if pnl < 0 else "")}${abs(pnl):,.2f}</td><td>{why}</td></tr>'
    for tk, d, side, px, pnl, why in ROWS)


def f(var, per):
    r = FIX.get((var, per))
    return money(r["net"]) if r else "—"


review = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Saad Trades Review</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;800&family=Share+Tech+Mono&family=Manrope:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="eyebrow">PrimeXBT demo · account 1364880 · XAUUSDp · 13–14 Oct 2026 · Saad_strategy_15min</div>
    <h1>Why the Saad trades lost money</h1>
    <p class="sub">Eight trades in 24 hours took the account from $10,000 to $6,511.83: two winners, one scratch, five losers. Below are each trade, the causes in order of money, what the full-year MT5 test says about each pattern, and what to change.</p>
    <div class="strip">
      <div><span>Trades</span><b>8</b></div><div><span>Winners</span><b class="pos">2 · +$3,806</b></div>
      <div><span>Losers</span><b class="neg">5 · −$5,964</b></div><div><span>Net</span><b class="neg">−$3,488</b></div>
      <div><span>Balance</span><b>$6,511.83</b></div>
    </div>
  </div>

  <h2>The trades</h2>
  <p class="sub">PKT times. Click a ticket for its full lifecycle, chart and diagnosis (67046250 has its own page from yesterday).</p>
  <div class="tw"><table>
    <thead><tr><th>PKT</th><th>Ticket</th><th>Side</th><th>Entry → exit</th><th>Result</th><th>In one line</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table></div>

  <h2>The causes, biggest first</h2>
  <div class="card verdict"><h3>1. The size: 2 lots on $10,000 is five times the designed risk</h3>
    <p>The EA was built and tested at <b>1 lot per $25,000</b>. Over the full year (MT5, Axi real ticks, 1 lot) it made <b>+$202,222</b>. Along the way it had <b>27 losing streaks of 4+ trades</b> (the longest was 11), <b>29 days out of 184 as bad as yesterday</b>, a worst day of −$3,782 and a worst drawdown of $12,681.</p>
    <p>At 2 lots on $10,000 the same ordinary bad stretch becomes a worst day of <b>−$7,563</b> and a drawdown of <b>$25,361, which is 254% of the account</b>. Yesterday wasn't unusual for the strategy. The size turned it into a 35% loss.</p>
    <div class="tw"><table><thead><tr><th>Lots on $10,000</th><th>Worst day (year)</th><th>Worst drawdown (year)</th><th>As % of $10k</th></tr></thead><tbody>
      <tr><td class="n">2 (now)</td><td class="n neg">−$7,563</td><td class="n neg">$25,361</td><td class="n neg">254%</td></tr>
      <tr><td class="n">0.4 (the report's 0.1 per $2,500)</td><td class="n">−$1,513</td><td class="n">$5,072</td><td class="n">51%</td></tr>
      <tr><td class="n"><b>0.2</b></td><td class="n">−$756</td><td class="n">$2,536</td><td class="n"><b>25%</b></td></tr>
      <tr><td class="n">0.1</td><td class="n">−$378</td><td class="n">$1,268</td><td class="n">13%</td></tr>
    </tbody></table></div></div>
  <div class="card"><h3>2. A normal losing streak: buys into a falling, choppy market</h3>
    <p>All four big losers were <b>BUYs while the 15-minute 9 EMA was under the 50 EMA</b>. The chop reading was near the EA's 0.11 limit, and most of them went almost nothing our way (+$0.37 to +$3.94) before reversing. Both winners were SELLs with the trend.</p>
    <p>But over the full year these are <b>not losing categories</b>:</p>
    <ul>
      <li>buys against the 15-minute trend: +$44,361 (257 trades)</li>
      <li>low-chop setups: +$53,561</li>
      <li>"no target" buys: +$77,462</li>
    </ul>
    <p>The strategy makes its money at turns, so it has days like this. Report.md §10 tested "buy only with the trend": it cut the year's profit by about 75%.</p></div>
  <div class="card warn"><h3>3. Operations: two bots on one account, a wrong chart, a shaky connection</h3>
    <ul><li><b>Two copies of the EA</b> share account 1364880 and magic number 88302: v1.17 on the trading machine and an old <b>v1.11</b> on Claude's PC. On the 13th the v1.11 copy tried to move 67046250's stop. After its chart was switched to <b>M1</b>, it opened 67082390 off a 1-minute candle. It has since been removed (nothing logged after 10:25 PM).</li>
    <li><b>The trading machine kept reconnecting.</b> On the 14th from 7:10 to 8:26 AM PKT the account was re-authorised from 119.154.92.250 every few minutes, after the connection quality dropped to 46%. Stops live at the broker, so no trade lost money because of it. But the breakeven, TP1 and trail steps need the EA online.</li>
    <li>On Axi, <b>VSISA is attached to an H1 chart</b> (loaded 2:42 AM today). VSISA reads the chart's candles, so on H1 it trades hourly candles, not the 5-minute ones it was tested on.</li></ul></div>
  <div class="card"><h3>4. A code hole: setups across the daily break</h3>
    <p><code>InpGapCancel</code> cancels a <i>waiting</i> setup when the market closes. But a setup formed by the last candle before the break is only created at the reopen, after that check, and then traded on the reopen candle. That was trade 67111138 (−$1,524). It's fixed in a research copy (<code>Saad_gapfix.mq5</code>).</p></div>

  <h2>What I tested in MT5 (full year, Axi real ticks, 1 lot)</h2>
  <div class="tw"><table><thead><tr><th>Change</th><th>Full year</th><th>Jan–Jun</th><th>Jul–Oct</th><th>Verdict</th></tr></thead><tbody>
    <tr><td>Today's rules (v1.17 trades)</td><td class="n">{f('base', 'full')}</td><td class="n">{f('base', 'tune')}</td><td class="n">{f('base', 'julo')}</td><td>baseline</td></tr>
    <tr><td>No BUYs on the 50 EMA (<code>InpLongRule = 0</code>)</td><td class="n">{f('no50long', 'full')}</td><td class="n">{f('no50long', 'tune')}</td><td class="n">{f('no50long', 'julo')}</td><td class="neg">rejected: worse in both halves</td></tr>
    <tr><td>Gap fix (no setup from the candle before a closure)</td><td class="n">{f('gapfix', 'full')}</td><td class="n">{f('gapfix', 'tune')}</td><td class="n">{f('gapfix', 'julo')}</td><td>correct behaviour, not a profit fix (2 trades a year)</td></tr>
  </tbody></table></div>

  <h2>What to change</h2>
  <div class="card good"><ol>
    <li><b>Size: 0.2 lots on $10,000</b> (a worst-year drawdown of about 25% of the account). Trading 2 lots needs about $50,000.</li>
    <li><b>One EA per account.</b> Remove every other copy (old versions on other terminals, the VPS, phones). Give any second EA its own <code>InpMagicNumber</code>.</li>
    <li><b>The 15-minute EA on M15 charts only</b>, and VSISA on M5. TradeLifecycle v1.03 now draws the two EMAs, so a wrong timeframe is easy to spot.</li>
    <li><b>A stable connection for the trading machine</b> (or a VPS), so the breakeven, TP1 and trail steps happen on time.</li>
    <li>Optional: ship the gap fix as a setting, for correctness.</li>
  </ol></div>

  <footer>Data: PrimeXBT's own XAUUSDp candles (downloaded from the broker for 12–14 Oct), the account's deals (PrimeXBT journal on Claude's PC, matching the statement), the v1.11 copy's own log, and full-year MT5 tests of the same EA on Axi real ticks (Jan 6 – Oct 8 2026). The trading machine's own Experts log wasn't available, so the EA's choices are reconstructed from its rules and code. The reconstruction was checked: it reproduces 67046250's logged TP1 (4150.75) exactly. <a href="/">Dashboard</a></footer>
</div>
</body>
</html>"""
(OUT / "review-20261014.html").write_text(review, encoding="utf-8")
print("wrote review-20261014.html")
