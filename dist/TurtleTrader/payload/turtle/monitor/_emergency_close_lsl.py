"""Emergency close all LSL_LB / LSL_VSISA positions to limit duplicate-fire damage."""
import MetaTrader5 as mt5

mt5.initialize(timeout=15000)
all_pos = mt5.positions_get(symbol="XAUUSD") or []
ours = [p for p in all_pos if "LSL" in (p.comment or "") or p.magic in (84001, 84002)]
print(f"Our open positions: {len(ours)}")
for p in ours:
    side = "BUY" if p.type == 0 else "SELL"
    print(f"  ticket={p.ticket} {side} {p.volume} @ {p.price_open:.2f} floating=${p.profit:.2f} comment={p.comment!r}")

closed = []
for p in ours:
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": "XAUUSD",
        "volume": p.volume, "position": p.ticket,
        "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
        "price": (mt5.symbol_info_tick("XAUUSD").bid if p.type == 0
                  else mt5.symbol_info_tick("XAUUSD").ask),
        "deviation": 50, "magic": p.magic, "comment": "EMERGENCY_CLOSE",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(req)
    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"  CLOSED ticket={p.ticket} fill_price={r.price}")
        closed.append(p.ticket)
    else:
        rc = r.retcode if r else None
        cm = r.comment if r else ""
        print(f"  FAILED to close {p.ticket}: retcode={rc} {cm}")

mt5.shutdown()
print(f"Closed {len(closed)} positions.")
