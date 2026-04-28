"""Fast Shano live status — single call, single line output.

Usage: python shano_status.py
Output: one-line JSON with today's realized P&L, open tickets, last burst state.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

FILLS = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv")
LOG = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\logs") / f"{datetime.now().strftime('%Y%m%d')}.log"
LAST_PRICE_FILE = Path(__file__).parent / ".shano_last_price.json"
EA_LIVE_STATE = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_live.json")


def read_ea_live_state(max_age_sec: int = 30):
    """Read ShanoExitManager's live JSON dump. Ground truth from MT5 itself.
    Returns None if missing or stale (>max_age_sec).
    """
    if not EA_LIVE_STATE.exists():
        return None
    try:
        age = datetime.now().timestamp() - EA_LIVE_STATE.stat().st_mtime
        if age > max_age_sec:
            return None
        return json.loads(EA_LIVE_STATE.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def read_live_price():
    """Read fresh XAUUSD bid/ask from hawk-written file. Returns None if missing/stale (>30s)."""
    if not LAST_PRICE_FILE.exists():
        return None
    try:
        age = datetime.now().timestamp() - LAST_PRICE_FILE.stat().st_mtime
        if age > 30:
            return None
        data = json.loads(LAST_PRICE_FILE.read_text())
        return data.get("last") or data.get("bid")
    except Exception:
        return None


def parse_fills():
    """Read today's fills. Per ticket, prefer deal_id>0 fill; fall back to EA snapshot.

    Returns (realized_pnl, closed_dict, open_position_records, unconfirmed_tickets, recent_fills).
    open_position_records: list of {ticket, dir, lots, entry_price, opened_at}
    recent_fills: list of {time, ticket, dir, lots, price, pnl, comment} for closed trades, latest 20.
    """
    today = datetime.now().strftime("%Y.%m.%d")
    closed_real = {}
    closed_snapshot = {}
    closed_meta = {}           # ticket -> latest fill record
    opens_by_ticket = {}
    unconfirmed = []
    if not FILLS.exists():
        return 0.0, closed_real, [], unconfirmed, []
    for line in FILLS.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith(today):
            continue
        parts = line.split(",")
        if len(parts) < 8:
            continue
        deal_id, ticket, _sym, action, lots, price, profit = (
            parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
        )
        try:
            profit_f = float(profit)
        except ValueError:
            profit_f = 0.0
        if action.endswith("_open"):
            opens_by_ticket[ticket] = {
                "ticket": ticket,
                "dir": action.replace("_open", "").lower(),
                "lots": float(lots) if lots else 0.0,
                "entry_price": float(price) if price else 0.0,
                "opened_at": parts[0],
            }
        elif action.endswith("_closed"):
            comment = parts[11] if len(parts) > 11 else ""
            rec = {
                "time": parts[0],
                "ticket": ticket,
                "dir": action.replace("_closed", "").lower(),
                "lots": float(lots) if lots else 0.0,
                "price": float(price) if price else 0.0,
                "pnl": profit_f,
                "deal_id": deal_id,
                "comment": comment,
                "is_real": bool(deal_id and deal_id != "0"),
            }
            if deal_id and deal_id != "0":
                closed_real[ticket] = profit_f
                closed_meta[ticket] = rec      # MT5-confirmed always wins
            else:
                closed_snapshot[ticket] = profit_f
                if ticket not in closed_meta:  # snapshot only as fallback
                    closed_meta[ticket] = rec
    final = dict(closed_real)
    for ticket, profit in closed_snapshot.items():
        if ticket not in final:
            final[ticket] = profit
            unconfirmed.append(ticket)
    realized = sum(final.values())
    open_records = [rec for tkt, rec in opens_by_ticket.items() if tkt not in final]
    # Build recent_fills sorted by time desc, latest 20
    recent_fills = sorted(closed_meta.values(), key=lambda r: r["time"], reverse=True)[:20]
    return realized, final, open_records, unconfirmed, recent_fills


def parse_log_state():
    """Tail MT5 log for last ShanoEA burst state, events, current price, account info,
    AND extract open positions from EA log (independent of turtle_fills.csv writes which
    can race with file-locks).

    Open-position detection: scan log for 'OPENED ticket=N | X.XX lots' / 'NEW PROBE DETECTED ticket=N'
    entries that don't have a subsequent 'CLOSED ticket=N' entry.
    """
    if not LOG.exists():
        return {"burst": None, "last_event": None, "log_mtime": None,
                "current_price": None, "margin_available": None, "recent_events": [],
                "log_opens": []}
    raw = LOG.read_bytes()[-40000:].replace(b"\x00", b"").decode("utf-8", errors="ignore")
    burst = None
    last_event = None
    current_price = None
    margin_avail = None
    recent_events = []
    opens = {}      # ticket -> {dir, lots, entry, opened_at}
    closed = set()  # tickets seen as CLOSED

    for line in raw.splitlines():
        m_burst = re.search(r"burst=(\d+)/(\d+)", line)
        if m_burst:
            burst = f"{m_burst.group(1)}/{m_burst.group(2)}"
        m_op = re.search(r"Open Price:\s*([\d.]+)", line)
        if m_op:
            current_price = float(m_op.group(1))
        m_margin = re.search(r"Margin Available:\s*([\d.]+)", line)
        if m_margin:
            margin_avail = float(m_margin.group(1))
        m_event = re.search(r"ShanoEA:\s+(.+)$", line)
        if m_event:
            ts_match = re.match(r"\S+\s+\S+\s+(\d{2}:\d{2}:\d{2})", line)
            ts = ts_match.group(1) if ts_match else ""
            text = m_event.group(1)[:120]
            last_event = text
            recent_events.append({"ts": ts, "text": text})

        # Probe opens (log line has "*** ticket=N" between DETECTED and the ticket)
        m_probe = re.search(r"NEW PROBE DETECTED.*?ticket=(\d+).*?\|\s*([\d.]+)\s*lots", line)
        if m_probe:
            tkt = m_probe.group(1)
            opens[tkt] = {"dir": "sell", "lots": float(m_probe.group(2)), "entry": None, "opened_at": ""}
        # Main opens
        m_main = re.search(r"MAIN OPENED ticket=(\d+).*?\|\s*([\d.]+)\s*lots", line)
        if m_main:
            tkt = m_main.group(1)
            opens[tkt] = {"dir": "sell", "lots": float(m_main.group(2)), "entry": None, "opened_at": ""}
        # Capture entry from "OPENING MAIN SELL X lots XAUUSD @ PRICE"
        m_open_main = re.search(r"OPENING MAIN SELL [\d.]+ lots \w+ @ ([\d.]+)\s*\(probe=(\d+)\)", line)
        if m_open_main:
            # main entry will arrive on next line; we'll match by next "MAIN OPENED" — track via sliding state
            _pending_entry_main = float(m_open_main.group(1))
        # Closes
        m_close = re.search(r"CLOSED ticket=(\d+)", line)
        if m_close:
            closed.add(m_close.group(1))

    # Build entry prices from "OPENING MAIN SELL ... @ PRICE (probe=X)" — match probe ticket → main entry below
    pending_main_entry = None
    for line in raw.splitlines():
        m1 = re.search(r"OPENING MAIN SELL [\d.]+ lots \w+ @ ([\d.]+)", line)
        if m1:
            pending_main_entry = float(m1.group(1))
            continue
        m2 = re.search(r"MAIN OPENED ticket=(\d+)", line)
        if m2 and pending_main_entry is not None:
            tkt = m2.group(1)
            if tkt in opens:
                opens[tkt]["entry"] = pending_main_entry
            pending_main_entry = None
        # Probe entry — opened by hawk via PineConnector. Read from "Open Price:" preceding a NEW PROBE line.

    # For probes without entry, fall back to current_price (best estimate)
    log_opens = []
    for tkt, info in opens.items():
        if tkt in closed:
            continue
        log_opens.append({
            "ticket": tkt,
            "dir": info["dir"],
            "lots": info["lots"],
            "entry_price": info["entry"] or current_price or 0,
            "opened_at": info["opened_at"],
            "source": "ea_log",
        })

    recent_events = recent_events[-12:]
    mtime = datetime.fromtimestamp(LOG.stat().st_mtime).strftime("%H:%M:%S")
    return {
        "burst": burst,
        "last_event": last_event,
        "log_mtime": mtime,
        "current_price": current_price,
        "margin_available": margin_avail,
        "recent_events": recent_events,
        "log_opens": log_opens,
    }


def compute_floating_pnl(open_records, current_price, contract_size=100.0):
    """Estimate floating P&L for each open position given current XAUUSD price."""
    if not current_price:
        return open_records
    enriched = []
    for r in open_records:
        rec = dict(r)
        if r["dir"] == "sell":
            move = r["entry_price"] - current_price
        else:
            move = current_price - r["entry_price"]
        rec["current_price"] = current_price
        rec["floating_pnl"] = round(move * r["lots"] * contract_size, 2)
        enriched.append(rec)
    return enriched


def main():
    realized, closed, open_records, unconfirmed, recent_fills = parse_fills()
    log_state = parse_log_state()

    # GROUND TRUTH: ShanoExitManager dumps shano_live.json every 1s via OnTimer
    # (tick-driven OnTick is supplementary). Allow up to 5 min staleness because
    # if the EA stops writing, MT5 positions don't move either — last snapshot
    # is still authoritative until proven otherwise. Beyond 5 min something is
    # actually broken (EA crashed/removed) so fall back to CSV+log.
    ea_live = read_ea_live_state(max_age_sec=300)

    if ea_live and ea_live.get("positions") is not None:
        # Authoritative state from EA. Replace open_records with MT5's own positions.
        live_price = ea_live.get("bid") or read_live_price() or log_state["current_price"]
        open_records = []
        for p in ea_live["positions"]:
            open_records.append({
                "ticket": str(p["ticket"]),
                "dir": p["dir"],
                "lots": p["lots"],
                "entry_price": p["entry"],
                "current_price": p.get("current", live_price),
                "floating_pnl": p["floating"],
                "role": p.get("role", "external"),
                "source": "ea_live",
            })
        floating_total = round(ea_live.get("floating", 0.0), 2)
        ea_balance = ea_live.get("balance")
        ea_equity = ea_live.get("equity")
        ea_burst_count = ea_live.get("burst_count")
        ea_burst_max = ea_live.get("burst_max")
        ea_age_seconds = round(datetime.now().timestamp() - EA_LIVE_STATE.stat().st_mtime, 1)

        # Override recent_fills with EA's deal-history dump (catches manual closes too).
        ea_history = ea_live.get("history") or []
        if ea_history:
            recent_fills = [{
                "time":    h.get("time", ""),
                "ticket":  str(h.get("ticket", "")),
                "deal_id": str(h.get("deal_id", "")),
                "dir":     h.get("dir", "sell"),
                "lots":    float(h.get("lots", 0)),
                "price":   float(h.get("price", 0)),
                "pnl":     float(h.get("pnl", 0)),
                "comment": h.get("comment", ""),
                "is_real": True,
            } for h in ea_history]
        # EA computes total_realized over ALL of today's deals (not just the 30 displayed).
        if "realized_today" in ea_live:
            realized = round(float(ea_live["realized_today"]), 2)
        if "closes_today" in ea_live:
            closed = {f"_total_{i}": 0 for i in range(int(ea_live["closes_today"]))}  # so len(closed) is correct
    else:
        # Fallback: derive from CSV + EA log (legacy path, less accurate).
        live_price = read_live_price() or log_state["current_price"]
        csv_tickets = {r["ticket"] for r in open_records}
        for r in log_state.get("log_opens", []):
            if r["ticket"] not in csv_tickets:
                open_records.append(r)
        open_records = compute_floating_pnl(open_records, live_price)
        floating_total = round(sum(r.get("floating_pnl", 0) for r in open_records), 2)
        ea_balance = ea_equity = ea_burst_count = ea_burst_max = ea_age_seconds = None
    burst_str = log_state["burst"]
    if ea_burst_count is not None and ea_burst_max:
        burst_str = f"{ea_burst_count}/{ea_burst_max}"

    # Win-rate calculation — MAIN TRADES ONLY (probes excluded by default).
    PROBE_LOT = 0.01
    is_main = lambda lots: lots > PROBE_LOT + 0.001

    # TODAY: prefer EA's full count (today_main_wins/losses) — based on full HistorySelect.
    # Fallback to walking the history list (limited to 30 entries).
    today_wins = today_losses = 0
    today_probes_skipped = 0
    if ea_live and ea_live.get("today_main_wins") is not None:
        today_wins = int(ea_live.get("today_main_wins", 0))
        today_losses = int(ea_live.get("today_main_losses", 0))
        today_probes_skipped = max(0, int(ea_live.get("closes_today", 0)) - today_wins - today_losses)
    elif ea_live and ea_live.get("history"):
        for h in ea_live["history"]:
            lots = float(h.get("lots", 0))
            p = float(h.get("pnl", 0))
            if not is_main(lots):
                today_probes_skipped += 1
                continue
            if p > 0.0001:
                today_wins += 1
            elif p < -0.0001:
                today_losses += 1
    today_total = today_wins + today_losses
    today_wr = round(100.0 * today_wins / today_total, 1) if today_total else None

    # OVERALL (last 7 days from EA's HistorySelect — bypasses CSV which has err=5004 gaps)
    # Falls back to CSV+date-filter only if EA hasn't dumped 7-day stats yet.
    overall_wins = overall_losses = 0
    overall_probes_skipped = 0
    overall_window = "7-day"
    if ea_live and ea_live.get("week_main_wins") is not None:
        overall_wins = int(ea_live.get("week_main_wins", 0))
        overall_losses = int(ea_live.get("week_main_losses", 0))
        overall_probes_skipped = int(ea_live.get("week_probe_closes", 0))
    else:
        # Fallback: CSV with date filter (less reliable due to file-lock errors)
        SHANO_ERA_START = "2026.04.27"
        overall_window = "csv-fallback"
        if FILLS.exists():
            for line in FILLS.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split(",")
                if len(parts) < 11:
                    continue
                date = parts[0][:10] if len(parts[0]) >= 10 else ""
                deal_id, action = parts[1], parts[4]
                if not action.endswith("_closed"):
                    continue
                if not deal_id or deal_id == "0":
                    continue
                if date and date < SHANO_ERA_START:
                    continue
                try:
                    lots = float(parts[5])
                    p = float(parts[10])
                except ValueError:
                    continue
                if not is_main(lots):
                    overall_probes_skipped += 1
                    continue
                if p > 0.0001:
                    overall_wins += 1
                elif p < -0.0001:
                    overall_losses += 1
    overall_total = overall_wins + overall_losses
    overall_wr = round(100.0 * overall_wins / overall_total, 1) if overall_total else None

    out = {
        "today_realized": round(realized, 2),
        "trades_closed": len(closed),
        "unconfirmed_tickets": unconfirmed,
        "open_positions": open_records,
        "open_count": len(open_records),
        "floating_pnl": floating_total,
        "net_pnl": round(realized + floating_total, 2),
        "current_price": live_price,
        "margin_available": log_state["margin_available"] if ea_live is None else ea_live.get("free_margin"),
        "balance": ea_balance,
        "equity": ea_equity,
        "burst": burst_str,
        "last_ea_event": log_state["last_event"],
        "recent_events": log_state["recent_events"],
        "recent_fills": recent_fills,
        "log_age": log_state["log_mtime"],
        "source": "ea_live" if ea_live else "csv+log",
        "ea_age_seconds": ea_age_seconds,
        "today_wins": today_wins,
        "today_losses": today_losses,
        "today_winrate": today_wr,
        "today_probes_skipped": today_probes_skipped,
        "overall_wins": overall_wins,
        "overall_losses": overall_losses,
        "overall_winrate": overall_wr,
        "overall_probes_skipped": overall_probes_skipped,
        "overall_window": overall_window,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
