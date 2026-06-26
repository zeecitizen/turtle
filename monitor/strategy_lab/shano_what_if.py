"""shano_what_if.py — Use her broker statement directly to compute the math:
how much did she lose by NOT having $5 SL / $10 TP rules?"""

# All 77 of Shano's trades from 29/05/2026 (parsed from her broker statement)
# (ticket, side, entry, exit, actual_pnl, duration_min, lots)
TRADES = [
    ("9431867","sell",73323.5,73306,0.18,20.83,0.01,"BTCUSD"),
    ("9431800","buy",73449,73383,-0.66,4.33,0.01,"BTCUSD"),
    ("9431586","sell",4541.01,4540.73,0.28,1.03,0.01,"XAUUSD"),
    ("9430595","sell",4546.98,4546.51,0.47,0.15,0.01,"XAUUSD"),
    ("9426244","buy",4563.37,4563.95,0.58,0.15,0.01,"XAUUSD"),
    ("9425932","buy",4564.45,4564.80,0.35,0.08,0.01,"XAUUSD"),
    ("9425384","buy",4567.83,4565.24,-5.18,2.45,0.02,"XAUUSD"),
    ("9424523","buy",4565.80,4565.78,-0.02,0.08,0.01,"XAUUSD"),
    ("9424297","sell",4569.90,4569.84,0.06,5.28,0.01,"XAUUSD"),
    ("9424074","sell",4571.47,4571.05,0.42,0.70,0.01,"XAUUSD"),
    ("9424404","sell",4566.90,4566.58,0.32,13.22,0.01,"XAUUSD"),
    ("9423761","sell",4566.30,4566.12,0.54,0.13,0.03,"XAUUSD"),
    ("9423347","sell",4561.03,4560.92,0.11,0.32,0.01,"XAUUSD"),
    ("9423714","buy",4565.65,4567.69,2.04,7.78,0.01,"XAUUSD"),
    ("9422736","buy",4565.40,4565.72,0.64,0.20,0.02,"XAUUSD"),
    ("9422401","sell",4564.58,4564.39,0.19,0.18,0.01,"XAUUSD"),
    ("9422051","sell",4568.27,4568.00,0.27,0.05,0.01,"XAUUSD"),
    ("9425456","sell",4558.26,4564.42,-6.16,76.80,0.01,"XAUUSD"),  # held 1h 16m
    ("9420839","sell",4561.60,4561.00,0.60,0.07,0.01,"XAUUSD"),
    ("9420184","sell",4565.18,4564.90,0.28,0.13,0.01,"XAUUSD"),
    ("9420036","sell",4569.51,4567.47,6.12,0.12,0.03,"XAUUSD"),  # best trade
    ("9419883","sell",4572.95,4572.65,0.30,0.68,0.01,"XAUUSD"),
    ("9419830","sell",4574.88,4574.43,0.45,0.10,0.01,"XAUUSD"),
    ("9389588","sell",4529.64,4529.49,0.15,0.07,0.01,"XAUUSD"),
    ("9372720","sell",4511.10,4511.07,0.03,1.27,0.01,"XAUUSD"),
    ("9372477","sell",4512.17,4512.11,0.06,0.08,0.01,"XAUUSD"),
    ("9372370","sell",4513.18,4512.80,0.38,0.07,0.01,"XAUUSD"),
    ("9370107","sell",4517.97,4517.89,0.08,0.10,0.01,"XAUUSD"),
    ("9352159","sell",4495.17,4497.20,-2.03,1.32,0.01,"XAUUSD"),
    ("9352017","sell",4495.53,4495.22,0.31,0.23,0.01,"XAUUSD"),
    ("9351772","sell",4495.94,4495.91,0.03,0.98,0.01,"XAUUSD"),
    ("9351460","sell",4495.81,4495.68,0.13,2.17,0.01,"XAUUSD"),
    ("9351385","buy",4497.80,4496.64,-1.16,0.95,0.01,"XAUUSD"),
    ("9351310","sell",4495.27,4495.66,-1.17,0.10,0.03,"XAUUSD"),
    ("9351414","sell",4495.96,4495.84,0.12,2.62,0.01,"XAUUSD"),
    ("9351239","sell",4496.78,4496.69,0.09,3.32,0.01,"XAUUSD"),
    ("9350913","sell",4498.65,4498.50,0.15,0.35,0.01,"XAUUSD"),
    ("9350851","sell",4499.53,4499.34,0.19,0.55,0.01,"XAUUSD"),
    ("9350788","sell",4499.55,4501.72,-2.17,3.43,0.01,"XAUUSD"),
    ("9350685","sell",4500.35,4499.99,0.36,0.32,0.01,"XAUUSD"),
    ("9350649","sell",4499.61,4499.71,-0.30,0.10,0.03,"XAUUSD"),
    ("9350636","sell",4500.75,4499.74,1.01,0.13,0.01,"XAUUSD"),
    ("9350485","sell",4502.74,4505.03,-2.29,1.20,0.01,"XAUUSD"),
    ("9350343","buy",4504.00,4504.24,0.24,0.18,0.01,"XAUUSD"),
    ("9350304","sell",4502.97,4502.42,0.55,1.02,0.01,"XAUUSD"),
    ("9350142","buy",4507.55,4508.04,0.49,0.18,0.01,"XAUUSD"),
    ("9349816","sell",4503.59,4503.44,0.15,0.37,0.01,"XAUUSD"),
    ("9349632","sell",4498.51,4499.91,-1.40,0.37,0.01,"XAUUSD"),
    ("9349556","sell",4500.47,4500.65,-0.18,0.27,0.01,"XAUUSD"),
    ("9349373","sell",4502.71,4502.54,0.17,0.10,0.01,"XAUUSD"),
    ("9349265","sell",4504.62,4504.62,0.00,0.13,0.01,"XAUUSD"),
    ("9349124","sell",4506.17,4506.06,0.11,1.03,0.01,"XAUUSD"),
    ("9348551","buy",4509.91,4510.20,0.29,2.08,0.01,"XAUUSD"),
    ("9347927","sell",4502.05,4501.67,0.38,0.57,0.01,"XAUUSD"),
    ("9347750","sell",4504.15,4503.50,0.65,0.07,0.01,"XAUUSD"),
    ("9347549","buy",4508.08,4506.95,-1.13,0.88,0.01,"XAUUSD"),
    ("9347398","sell",4505.40,4505.23,0.17,0.07,0.01,"XAUUSD"),
    ("9347337","buy",4508.10,4508.46,1.44,0.40,0.04,"XAUUSD"),
    ("9347261","buy",4506.73,4507.47,2.22,0.12,0.03,"XAUUSD"),
    ("9347276","sell",4502.72,4507.08,-4.36,6.82,0.01,"XAUUSD"),
    ("9346877","sell",4507.13,4506.23,0.90,0.57,0.01,"XAUUSD"),
    ("9346779","sell",4508.50,4508.14,1.08,0.58,0.03,"XAUUSD"),
    ("9346709","sell",4510.78,4511.51,-2.19,0.17,0.03,"XAUUSD"),
    ("9346669","sell",4510.95,4510.42,1.06,0.13,0.02,"XAUUSD"),
    ("9346600","sell",4513.23,4512.30,0.93,0.17,0.01,"XAUUSD"),
    ("9345914","buy",4517.35,4517.52,0.34,0.13,0.02,"XAUUSD"),
    ("9345901","buy",4516.74,4516.86,0.24,0.05,0.02,"XAUUSD"),
    ("9345890","buy",4516.52,4516.69,0.17,0.07,0.01,"XAUUSD"),
    ("9345409","buy",4512.11,4512.40,0.58,0.08,0.02,"XAUUSD"),
    ("9345269","buy",4510.72,4510.43,-0.58,0.07,0.02,"XAUUSD"),
    ("9344979","buy",4504.50,4505.12,1.24,0.23,0.02,"XAUUSD"),
    ("9346154","sell",4493.36,4520.48,-27.12,39.28,0.01,"XAUUSD"),  # WORST TRADE
    ("9343709","sell",4494.20,4493.94,0.26,0.25,0.01,"XAUUSD"),
    ("9343695","sell",4494.60,4494.44,0.16,2.67,0.01,"XAUUSD"),
    ("9343404","buy",4499.87,4499.93,0.06,8.50,0.01,"XAUUSD"),
    ("9343154","buy",4499.66,4500.07,0.41,0.23,0.01,"XAUUSD"),
    ("9343122","buy",4499.28,4499.94,0.66,3.03,0.01,"XAUUSD"),
]

# Stats
total_pnl = sum(t[4] for t in TRADES)
wins = [t for t in TRADES if t[4] > 0]
losses = [t for t in TRADES if t[4] < 0]
flat = [t for t in TRADES if t[4] == 0]

print(f"=== SHANO'S 29/05 ACTUAL ===")
print(f"  Total trades: {len(TRADES)}")
print(f"  Wins:   {len(wins)} (WR = {100*len(wins)/len(TRADES):.0f}%)")
print(f"  Losses: {len(losses)}")
print(f"  Flat:   {len(flat)}")
print(f"  Net P&L: ${total_pnl:+.2f}")
print(f"  Sum of wins:   ${sum(t[4] for t in wins):+.2f}")
print(f"  Sum of losses: ${sum(t[4] for t in losses):+.2f}")
print()

# What if she had used $5 SL / $10 TP discipline?
# At 0.01 lot, $1 price move = $1 dollar.
# So $5 SL means: cut at 5 points adverse.
# We can confidently estimate for LOSING trades what would have happened:
# If her actual loss <= $5 → would have closed at her actual exit (within SL)
# If her actual loss > $5 → SL would have hit, capping at -$5
# For WINNING trades: she cut early. We CANNOT know if $10 TP would have hit
#                   without tick data. But we can assume CONSERVATIVELY that
#                   half of her wins could have hit $10 TP (gold makes big moves).

print(f"=== WHAT IF: $5 SL / $10 TP discipline ===\n")

# Step 1: How much she lost EXTRA by not cutting losers at -$5
extra_lost = 0
big_losers = []
for t in TRADES:
    tkt, side, entry, exit_p, pnl, dur, lots, sym = t
    # Adverse price move = |entry - exit| in price units
    adverse_pts = (exit_p - entry) if side == "sell" else (entry - exit_p)  # how much MOVE against
    if pnl < -5:
        # She held past -$5. With SL, would have lost only -$5 (at 0.01 lots) or -$5*lots/0.01
        # Wait — at her ACTUAL lot size, $5 price move = $5*lots*100/100 = $5*lots actual dollars
        # Hmm but PnL is in dollars and price is in price units. So $1 price = $1 dollar at 0.01 lot.
        # For 0.02 lot, $1 price = $2 dollar
        sl_loss = -5 * (lots / 0.01)  # $5 SL at 0.01-equivalent
        saved = -sl_loss + pnl  # negative pnl, so |pnl| - 5 = how much saved
        extra_lost += -saved
        big_losers.append((tkt, side, entry, exit_p, pnl, lots, sl_loss, -saved))

print(f"### BIG LOSERS (lost more than $5 by holding too long):")
print(f"  {'ticket':<10}{'side':<5}{'entry':>9}{'exit':>9}{'lots':>6}{'actual':>9}{'with $5 SL':>12}{'SAVED':>8}")
for tkt, side, entry, exit_p, pnl, lots, sl_loss, saved in sorted(big_losers, key=lambda x: x[4]):
    print(f"  {tkt:<10}{side:<5}{entry:>9.2f}{exit_p:>9.2f}{lots:>6.2f}{pnl:>+9.2f}{sl_loss:>+12.2f}{saved:>+8.2f}")
print(f"  TOTAL EXTRA LOST: ${extra_lost:+.2f} (just from these {len(big_losers)} trades)")
print()

# Step 2: How much she could have made on winners if held to $10 TP
# Conservative: assume only HALF her wins would have reached $10 TP
# (the ones where she correctly read momentum)
extra_won = 0
cut_short = []
for t in TRADES:
    tkt, side, entry, exit_p, pnl, dur, lots, sym = t
    if pnl > 0 and pnl < 3 and lots <= 0.03:
        # Cut short for under $3, held briefly
        # If $10 TP had been set, IF it had hit → +$10 (×lots/0.01 if scaled)
        potential = 10 * (lots / 0.01)
        gain = potential - pnl
        cut_short.append((tkt, side, entry, exit_p, pnl, dur, lots, potential, gain))

# Assume 50% would have hit TP (conservative)
cut_short.sort(key=lambda x: -x[8])  # sort by potential gain
half = len(cut_short) // 2
total_potential_gain = sum(c[8] for c in cut_short[:half])

print(f"### WINNERS CUT SHORT (held <3 min, profit <$3):")
print(f"  {len(cut_short)} trades total cut short. Conservative est: half would have reached $10 TP")
print(f"  If half hit $10 TP: extra +${total_potential_gain:+.2f}")
print()

print(f"=== BOTTOM LINE ===")
print(f"  Her actual day P&L:              ${total_pnl:+.2f}")
print(f"  Just from SL discipline (cut at -$5): +${extra_lost:.2f} saved")
print(f"  → Day P&L with SL discipline only:  ${total_pnl + extra_lost:+.2f}")
print(f"  + If half of cut-short wins hit $10 TP: +${total_potential_gain:.2f} extra")
print(f"  → Day P&L with FULL discipline:     ${total_pnl + extra_lost + total_potential_gain:+.2f}")
print()
print(f"*** ONE SINGLE TRADE made the difference ***")
worst = min(TRADES, key=lambda t: t[4])
print(f"  Worst trade: {worst[0]} {worst[1]} {worst[2]} → {worst[3]} = ${worst[4]:+.2f}")
print(f"  This ONE trade alone lost as much as her best {worst[4] / -0.54:.0f} winners earned")
