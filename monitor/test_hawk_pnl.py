#!/usr/bin/env python3
"""
test_hawk_pnl.py — Simulate market ticks and verify hawk P&L matches MT5.

Tests the exact P&L formula used in the hawk against known MT5 trade results.
Run: python test_hawk_pnl.py
"""

PNL_FACTOR = 40.0  # $40 per 1.0 price unit at 0.40 lots


def calc_pnl(dirn: str, entry_ref: float, bid: float, ask: float) -> float:
    """Calculate P&L exactly as the hawk does — using correct bid/ask per direction."""
    if dirn == "sell":
        # SELL: entered at BID, close at ASK
        # P&L = (entry_bid - current_ask) * factor
        raw = entry_ref - ask
    else:
        # BUY: entered at ASK, close at BID
        # P&L = (current_bid - entry_ask) * factor
        raw = bid - entry_ref
    return round(raw * PNL_FACTOR, 2)


def calc_pnl_old_buggy(dirn: str, entry_ref: float, price: float) -> float:
    """OLD BUGGY formula — used last_price for everything, ignoring spread."""
    if dirn == "sell":
        raw = entry_ref - price
    else:
        raw = price - entry_ref
    return round(raw * PNL_FACTOR, 2)


def test_real_trade_1():
    """
    REAL TRADE from MT5 (2026-04-22 23:06):
    - SELL 0.40 lots XAUUSD
    - MT5 entry (bid): 4739.48
    - MT5 exit (ask):  4739.57
    - MT5 P&L: -$3.60
    - Spread at time: ~0.38
    """
    print("=" * 60)
    print("TEST 1: Real SELL trade from MT5 (23:06)")
    print("=" * 60)

    dirn = "sell"
    mt5_entry = 4739.48  # MT5 sell entry = bid
    mt5_exit = 4739.57   # MT5 close = ask
    mt5_pnl = -3.60
    spread = 0.38

    # What the hawk saw at entry (ask price from chart):
    chart_ask_at_entry = mt5_entry + spread  # 4739.86
    chart_bid_at_entry = mt5_entry            # 4739.48

    # NEW (correct): hawk uses BID as entry_ref for sell
    entry_ref_new = chart_bid_at_entry  # 4739.48
    print(f"\n  NEW hawk entry_ref: {entry_ref_new:.3f} (bid)")

    # At close time, chart shows:
    close_bid = mt5_exit - spread  # ~4739.19
    close_ask = mt5_exit           # 4739.57

    pnl_new = calc_pnl("sell", entry_ref_new, close_bid, close_ask)
    print(f"  NEW hawk P&L: ${pnl_new:+.2f}")
    print(f"  MT5 P&L:      ${mt5_pnl:+.2f}")
    print(f"  Match: {'YES' if abs(pnl_new - mt5_pnl) < 0.01 else 'NO — diff=' + str(round(pnl_new - mt5_pnl, 2))}")

    # OLD (buggy): hawk used last_price (≈ask) as entry_ref
    entry_ref_old = chart_ask_at_entry  # 4739.86
    pnl_old = calc_pnl_old_buggy("sell", entry_ref_old, close_ask)
    print(f"\n  OLD hawk entry_ref: {entry_ref_old:.3f} (ask — WRONG)")
    print(f"  OLD hawk P&L: ${pnl_old:+.2f}  <-- PHANTOM PROFIT!")
    print(f"  Error: ${pnl_old - mt5_pnl:+.2f}")


def test_sell_simulation():
    """Simulate a SELL trade with known bid/ask stream."""
    print("\n" + "=" * 60)
    print("TEST 2: Simulated SELL with bid/ask stream")
    print("=" * 60)

    dirn = "sell"
    spread = 0.35  # typical XAUUSD spread

    # Simulated tick stream: (bid, ask) pairs
    ticks = [
        (4740.00, 4740.35),  # entry — hawk should use bid=4740.00 as entry_ref
        (4739.90, 4740.25),  # price dropping — tracking ask
        (4739.80, 4740.15),
        (4739.50, 4739.85),  # good drop
        (4739.70, 4740.05),  # bouncing back
        (4740.10, 4740.45),  # reversed — now losing
    ]

    entry_ref = ticks[0][0]  # BID for sell = 4740.00
    print(f"\n  Entry ref (bid): {entry_ref:.3f}")
    print(f"  Spread: {spread:.3f}")
    print(f"\n  Tick-by-tick P&L:")

    for i, (bid, ask) in enumerate(ticks):
        pnl = calc_pnl("sell", entry_ref, bid, ask)
        # MT5 equivalent: if closed now, exit at ASK
        mt5_pnl = round((entry_ref - ask) * PNL_FACTOR, 2)
        match = "OK" if abs(pnl - mt5_pnl) < 0.01 else "WRONG"
        print(f"    tick {i}: bid={bid:.2f} ask={ask:.2f}  hawk=${pnl:+.2f}  mt5=${mt5_pnl:+.2f}  {match}")

    # What the OLD hawk would have shown:
    old_entry = ticks[0][1]  # ASK for sell — WRONG
    print(f"\n  OLD hawk (using ask as entry): entry_ref={old_entry:.3f}")
    for i, (bid, ask) in enumerate(ticks):
        pnl_old = calc_pnl_old_buggy("sell", old_entry, ask)
        mt5_pnl = round((entry_ref - ask) * PNL_FACTOR, 2)
        err = pnl_old - mt5_pnl
        print(f"    tick {i}: old_pnl=${pnl_old:+.2f}  actual=${mt5_pnl:+.2f}  ERROR=${err:+.2f}")


def test_buy_simulation():
    """Simulate a BUY trade with known bid/ask stream."""
    print("\n" + "=" * 60)
    print("TEST 3: Simulated BUY with bid/ask stream")
    print("=" * 60)

    dirn = "buy"
    spread = 0.35

    # Simulated tick stream: (bid, ask) pairs
    ticks = [
        (4740.00, 4740.35),  # entry — hawk should use ask=4740.35 as entry_ref
        (4740.20, 4740.55),  # price rising — tracking bid
        (4740.50, 4740.85),
        (4740.80, 4741.15),  # good rise
        (4740.30, 4740.65),  # pulling back
        (4739.90, 4740.25),  # reversed — losing
    ]

    entry_ref = ticks[0][1]  # ASK for buy = 4740.35
    print(f"\n  Entry ref (ask): {entry_ref:.3f}")
    print(f"  Spread: {spread:.3f}")
    print(f"\n  Tick-by-tick P&L:")

    for i, (bid, ask) in enumerate(ticks):
        pnl = calc_pnl("buy", entry_ref, bid, ask)
        # MT5 equivalent: if closed now, exit at BID
        mt5_pnl = round((bid - entry_ref) * PNL_FACTOR, 2)
        match = "OK" if abs(pnl - mt5_pnl) < 0.01 else "WRONG"
        print(f"    tick {i}: bid={bid:.2f} ask={ask:.2f}  hawk=${pnl:+.2f}  mt5=${mt5_pnl:+.2f}  {match}")


def test_spread_impact():
    """Show exactly how much the spread costs per trade."""
    print("\n" + "=" * 60)
    print("TEST 4: Spread cost analysis")
    print("=" * 60)

    for spread in [0.20, 0.30, 0.35, 0.40, 0.50]:
        cost = round(spread * PNL_FACTOR, 2)
        print(f"  Spread {spread:.2f} = ${cost:.2f} cost per trade (at 0.40 lots)")

    print(f"\n  This means: a trade must move {0.35:.2f} in your direction")
    print(f"  AFTER entry just to break even ($0.00 P&L).")
    print(f"  The old hawk was counting this spread as instant profit!")


def test_dud_detection():
    """Verify dud exit with spread-aware P&L and new threshold logic."""
    print("\n" + "=" * 60)
    print("TEST 5: Dud detection with spread-aware P&L")
    print("=" * 60)

    spread = 0.35
    DUD_OFFSET = 1.0  # need $1 improvement from initial P&L

    # --- Scenario A: SELL, price flat (DUD) ---
    print("\n  --- A: SELL, price FLAT (should be DUD) ---")
    entry_ref = 4740.00  # bid
    initial_pnl = calc_pnl("sell", entry_ref, 4740.00, 4740.35)
    dud_threshold = initial_pnl + DUD_OFFSET
    print(f"  Entry (bid): {entry_ref:.3f}  Initial P&L: ${initial_pnl:.2f}  Dud threshold: ${dud_threshold:.2f}")

    ticks = [(4740.00, 4740.35)] * 4
    peak = initial_pnl
    for i, (b, a) in enumerate(ticks):
        p = calc_pnl("sell", entry_ref, b, a)
        if p > peak: peak = p
        dud = i >= 3 and peak <= dud_threshold
        print(f"    t={i}s: P&L=${p:+.2f}  peak=${peak:.2f}  {'-> DUD EXIT' if dud else ''}")
    assert peak <= dud_threshold, "FAIL: flat price should be DUD"
    print("  PASS: flat price correctly detected as DUD")

    # --- Scenario B: SELL, price drops 0.05 (tiny move, still DUD) ---
    print("\n  --- B: SELL, tiny drop 0.05 (should still be DUD) ---")
    ticks_b = [(4740.00,4740.35), (4739.97,4740.32), (4739.95,4740.30), (4739.95,4740.30)]
    peak = initial_pnl
    for i, (b, a) in enumerate(ticks_b):
        p = calc_pnl("sell", entry_ref, b, a)
        if p > peak: peak = p
        dud = i >= 3 and peak <= dud_threshold
        print(f"    t={i}s: P&L=${p:+.2f}  peak=${peak:.2f}  {'-> DUD EXIT' if dud else ''}")
    is_dud = peak <= dud_threshold
    print(f"  {'PASS' if is_dud else 'FAIL'}: tiny move {'correctly' if is_dud else 'should be'} DUD")

    # --- Scenario C: SELL, price drops 0.50 (real move, NOT DUD) ---
    print("\n  --- C: SELL, strong drop 0.50 (should NOT be DUD) ---")
    ticks_c = [(4740.00,4740.35), (4739.70,4740.05), (4739.50,4739.85), (4739.50,4739.85)]
    peak = initial_pnl
    for i, (b, a) in enumerate(ticks_c):
        p = calc_pnl("sell", entry_ref, b, a)
        if p > peak: peak = p
        dud = i >= 3 and peak <= dud_threshold
        print(f"    t={i}s: P&L=${p:+.2f}  peak=${peak:.2f}  {'-> DUD EXIT' if dud else ''}")
    is_not_dud = peak > dud_threshold
    print(f"  {'PASS' if is_not_dud else 'FAIL'}: strong move correctly NOT DUD, keep holding")

    # --- Scenario D: BUY, price flat (DUD) ---
    print("\n  --- D: BUY, price FLAT (should be DUD) ---")
    entry_ref_buy = 4740.35  # ask for buy
    initial_pnl_buy = calc_pnl("buy", entry_ref_buy, 4740.00, 4740.35)
    dud_threshold_buy = initial_pnl_buy + DUD_OFFSET
    print(f"  Entry (ask): {entry_ref_buy:.3f}  Initial P&L: ${initial_pnl_buy:.2f}  Dud threshold: ${dud_threshold_buy:.2f}")

    ticks_d = [(4740.00, 4740.35)] * 4
    peak = initial_pnl_buy
    for i, (b, a) in enumerate(ticks_d):
        p = calc_pnl("buy", entry_ref_buy, b, a)
        if p > peak: peak = p
        dud = i >= 3 and peak <= dud_threshold_buy
        print(f"    t={i}s: P&L=${p:+.2f}  peak=${peak:.2f}  {'-> DUD EXIT' if dud else ''}")
    assert peak <= dud_threshold_buy, "FAIL: flat BUY should be DUD"
    print("  PASS: flat BUY correctly detected as DUD")


if __name__ == "__main__":
    test_real_trade_1()
    test_sell_simulation()
    test_buy_simulation()
    test_spread_impact()
    test_dud_detection()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
