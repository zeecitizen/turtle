# Overnight 2026-06-07 — Dashboard build + canonical iterations

Zee asleep ~03:21 broker. Heartbeat: 1-hour cycle.

## ✅ Cycle 0 — Dashboard rebuild (Zee's request)

### Done
1. **World session clocks** integrated into `status.html` (apex page served at
   https://claudezeeshan.com/). Four live-ticking SVG analog clocks
   (Sydney / Tokyo / London / New York) with:
   - Real-time hour/minute/second hands per city
   - Border glows GREEN when that session is open
   - Live countdown: "OPEN · 4h 12m left" / "opens in 1h 47m"
   - Lifted from `dashboard/claude_trader/hub.html` so styling matches

2. **Monday's-test 7-day comparison table** on `status.html`:
   - Columns: Day · Date · Expected USD · Real USD (editable) · Status
   - Live tally: "X / Y profitable days" with sum of expected vs sum of actual
   - Status badges: pending / ✅ target hit / 🟡 positive / 🔴 loss
   - Inline-editable Real column: type a number, blur (or hit Enter), persists
   - "Roll to next week" button: archives current week + seeds next 7 days
   - Pulls expected_usd from canonical detector ($3.27/day at 0.01 lot)

3. **Backend** `/api/weekly` GET/POST + `?roll=1`:
   - File: `monitor/weekly_tracker.json` (week_starts, ea_version, lot_size, days[], archive[])
   - GET returns full week JSON; POST overwrites days[]; roll archives + seeds next
   - Added `/api/weekly` to apex skip-redirect list (no 301 hop)
   - Round-trip POST verified end-to-end on the public URL

### Public URLs (all green)
- `https://claudezeeshan.com/` → dashboard (System Status + Clocks + Weekly Table + Tasks)
- `https://claudezeeshan.com/api/canonical-status` → backtest pie-chart values
- `https://claudezeeshan.com/api/weekly` → 7-day table data (GET + POST)
- `https://setups.claudezeeshan.com/setups.html` → original 36-card EA labels (Zee labelled all)
- `https://setups.claudezeeshan.com/setups2.html` → 5-card canonical fires (Zee labelled c1-c5)
- `https://setups.claudezeeshan.com/setups3.html` → **44-card MCQ batch (current)**

## 🔜 Cycle 1+ — Detector fixes per MCQ + EA port

While Zee labels the 44 MCQ cards overnight:
1. Parse `zee_labels.json` for any `m1..m44` entries with each turn
2. Aggregate failure modes by question (which gates fail most often?)
3. Apply matched detector fixes (c1=trend stability, c2=earliest breakout,
   c3=wider UHV window, c4=stricter origin)
4. Re-run detector → expect WR jump + setup count stays workable
5. Update `canonical_status.json` so investor pie chart reflects truth
6. Begin MQL5 port of corrected gates to S1Trader.mq5 v2.61

Halt conditions: account safety risk, infra outage requiring Zee's hands.
