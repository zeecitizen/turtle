"""Shano Rule Compliance Check.

Static-analyze pine/turtle-shano.pine and mt5/ShanoExitManager.mq5 against
Shano's verbatim interview quotes. Output: JSON list of rules with status.

Run: python shano_rules.py
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PINE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\pine\turtle-shano.pine")
EA   = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\mt5\ShanoExitManager.mq5")
LIVE = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_live.json")
TV_SNAP = Path(__file__).parent / ".tv_indicator_snapshot.json"  # written by Claude cron via mcp


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _normalize(v, expected):
    """Coerce raw value v against the type of expected. Used for both source + snapshot."""
    if isinstance(expected, bool):
        if isinstance(v, bool): return v
        if isinstance(v, str):  return v.lower() == "true"
        return bool(v)
    if isinstance(expected, (int, float)):
        try: return float(v)
        except (TypeError, ValueError): return None
    return str(v)


def check_pine_input(src: str, name: str, expected, tv_snap: dict | None = None) -> tuple[bool, str]:
    """Verify pine input against Shano's expected value.

    Now checks BOTH the on-disk source default AND the live TV chart override.
    Returns ok=True only if BOTH match expected. If they disagree, surface the drift.
    """
    pattern = rf"i{re.escape(name)}\s*=\s*input\.\w+\(\s*([^,)\s]+)"
    m = re.search(pattern, src)
    if not m:
        return False, f"input not found in source: i{name}"
    raw = m.group(1).strip()
    if raw in ("true", "false"):
        src_val = (raw == "true")
    elif raw.startswith('"'):
        src_val = raw.strip('"')
    else:
        try:
            src_val = float(raw) if "." in raw else int(raw)
        except ValueError:
            src_val = raw

    src_norm = _normalize(src_val, expected)
    src_ok = (src_norm == expected if isinstance(expected, (str, bool))
              else abs(src_norm - float(expected)) < 0.001 if src_norm is not None else False)

    # If we have a TV snapshot, also check the live chart value
    if tv_snap and "input_map" in tv_snap:
        chart_val = tv_snap["input_map"].get(f"i{name}")
        if chart_val is None:
            return src_ok, f"src={src_val!r} (no chart snapshot for this input)"
        chart_norm = _normalize(chart_val, expected)
        chart_ok = (chart_norm == expected if isinstance(expected, (str, bool))
                    else abs(chart_norm - float(expected)) < 0.001 if chart_norm is not None else False)
        if src_ok and chart_ok:
            return True, f"{chart_val!r} (source + chart match)"
        if src_ok and not chart_ok:
            return False, f"⚠ chart override drift: source={src_val!r} but CHART={chart_val!r}"
        if not src_ok and chart_ok:
            return False, f"⚠ source drift: source={src_val!r} but chart={chart_val!r}"
        return False, f"both wrong: source={src_val!r}, chart={chart_val!r}"
    return src_ok, f"{src_val!r} (source only — no chart snapshot)"


def check_ea_input(src: str, name: str, expected) -> tuple[bool, str]:
    """Match `input <type> InpName = VALUE;`."""
    pattern = rf"input\s+\w+\s+Inp{re.escape(name)}\s*=\s*([^;]+);"
    m = re.search(pattern, src)
    if not m:
        return False, f"input not found: Inp{name}"
    raw = m.group(1).strip()
    actual: object
    if raw in ("true", "false"):
        actual = (raw == "true")
    elif raw.startswith('"'):
        actual = raw.strip('"')
    else:
        try:
            actual = float(raw) if "." in raw else int(raw)
        except ValueError:
            actual = raw
    if isinstance(expected, bool):
        ok = bool(actual) == expected
    elif isinstance(expected, (int, float)):
        ok = abs(float(actual) - float(expected)) < 0.001
    else:
        ok = str(actual) == str(expected)
    return ok, f"{actual!r}"


def contains(src: str, needle: str) -> bool:
    return needle in src


def main():
    pine_src = read(PINE)
    ea_src = read(EA)

    # Read live state for runtime confirms
    live = {}
    try:
        if LIVE.exists():
            live = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception:
        pass

    # Read TV chart indicator snapshot (written by Claude cron, ~30min freshness)
    tv_snap = None
    tv_snap_age_sec = None
    try:
        if TV_SNAP.exists():
            tv_snap = json.loads(TV_SNAP.read_text(encoding="utf-8"))
            tv_snap_age_sec = round(datetime.now().timestamp() - TV_SNAP.stat().st_mtime)
    except Exception:
        pass

    rules = []

    def add(category: str, urdu: str, english: str, ok: bool, evidence: str, source: str):
        rules.append({
            "category": category,
            "shano_words": urdu,
            "rule": english,
            "ok": bool(ok),
            "evidence": evidence,
            "source": source,
        })

    # ─── DETECTION ──────────────────────────────────────────────────────
    add("detection",
        "sirf body matter karti hai pichli se dekh kar compare karti hun",
        "Body-only detection (no wick component)",
        contains(pine_src, "math.abs(close - open)") and contains(pine_src, "math.abs(close[1] - open[1])"),
        "Pine uses math.abs(close-open), not high/low",
        "pine/turtle-shano.pine")

    add("detection",
        "pichli 2 candle se bari visibly bari",
        "Current bar must be 1.5x bigger than previous 2 bar bodies",
        *check_pine_input(pine_src, "BodyMult", 1.5, tv_snap)[:1] + (check_pine_input(pine_src, "BodyMult", 1.5, tv_snap)[1],),
        "iBodyMult input")
    rules[-1]["source"] = "pine iBodyMult"

    add("detection",
        "sirf dekhti hun kuch ni karti pehli red candle pe. haan dusri red candle pe 0.01 lot lagati hu",
        "2-candle pattern: prev red + current big red triggers probe",
        contains(pine_src, "isBear2     = isBear and prevIsBear"),
        "Pine isBear2 = isBear and prevIsBear",
        "pine isBear2")

    # ─── PROBE ──────────────────────────────────────────────────────────
    ok, ev = check_pine_input(pine_src, "ProbeLots", 0.01, tv_snap)
    add("probe",
        "0.01 lot lagati hu",
        "Probe lot size = 0.01",
        ok, ev, "pine iProbeLots")

    ok, ev = check_pine_input(pine_src, "ProbeConf", 0.58, tv_snap)
    add("probe",
        "agar 0.01 lot ki trade ka profit agar 0.58 USD se upar jata hai phir 0.4 ki lot laga deti hun",
        "Probe confirms at +$0.58 → fire main 0.40",
        ok, ev, "pine iProbeConf")

    ok, ev = check_pine_input(pine_src, "ProbeFail", 3.00, tv_snap)
    add("probe",
        "Minus 3 loss tak janay deti hun on that 0.01 trade",
        "Probe fails (cuts loss) at −$3.00",
        ok, ev, "pine iProbeFail")

    ok, ev = check_ea_input(ea_src, "ProbeTimeout", 50)
    add("probe",
        "i wait 50 seconds, still if its in loss, close it",
        "Probe timeout = 50 seconds",
        ok, ev, "EA InpProbeTimeout")

    add("probe",
        "0.01 wali on rehti hai.. 0.4 ko close karti hun, phir 0.01 ko close karti hun",
        "Probe stays open alongside main 0.40",
        contains(ea_src, "Don't close probe — it stays open alongside main") or
          contains(ea_src, "stays open alongside main"),
        "EA: probe persists when main opens",
        "EA logic")

    # ─── MAIN TRADE ─────────────────────────────────────────────────────
    ok, ev = check_pine_input(pine_src, "RealLots", 0.40, tv_snap)
    add("main_trade",
        "0.4 ki lot laga deti hun (capital 500-800 range)",
        "Main lot = 0.40 (Pine simulation)",
        ok, ev, "pine iRealLots")

    ok, ev = check_pine_input(pine_src, "PCLots", 0.40, tv_snap)
    add("main_trade",
        "0.4 ki lot laga deti hun",
        "Main lot fired to MT5 = 0.40",
        ok, ev, "pine iPCLots")

    add("main_trade",
        "FORAN.. without watching next candle (open 0.40 immediately when probe confirms)",
        "Main opens immediately on probe confirm — no candle wait",
        contains(ea_src, "PROBE CONFIRMED") and contains(ea_src, "OpenMainTrade"),
        "EA: ProcessProbe → OpenMainTrade direct call",
        "EA logic")

    # ─── EXIT ───────────────────────────────────────────────────────────
    ok, ev = check_ea_input(ea_src, "TrailTrigger", 8.0)
    add("exit",
        "8 pe bhi kar deti hun, 12 pe bhi kar deti hun (trail starts after $8 profit)",
        "Trail starts after profit reaches $8",
        ok, ev, "EA InpTrailTrigger")

    ok, ev = check_ea_input(ea_src, "TrailDrop", 2.0)
    add("exit",
        "jab drop honay lagta hai tab close karti hun (close on profit drop)",
        "Close when profit drops $2 from peak (approximation of her tick-watch)",
        ok, ev, "EA InpTrailDrop")

    ok, ev = check_ea_input(ea_src, "HoldLotMax", 0.10)
    add("exit",
        "0.08 wali chalti rahay, 0.01 wali chalti rahay, 0.1 wali bhi chalti rahay",
        "Lots ≤ 0.10 hold forever (no fear-based close)",
        ok, ev, "EA InpHoldLotMax")

    ok, ev = check_ea_input(ea_src, "FearIdeal", 70.0)
    add("exit",
        "−70 pe ideal hota agar hum close kar detay 180 tak bhi na janay detay",
        "Lots > 0.10: close at −$70 (ideal)",
        ok, ev, "EA InpFearIdeal")

    ok, ev = check_ea_input(ea_src, "FearWashout", 180.0)
    add("exit",
        "0.4 wali −180 pe close kar deti hun kyunk else wo pura account wash kar degi",
        "Lots > 0.10: hard close at −$180 (washout-prevention)",
        ok, ev, "EA InpFearWashout")

    add("exit",
        "IN ANY CASE SABSE BARA LOT SIZE PEHLAY CLOSE HOGA",
        "When closing multiple positions, close largest lot first",
        contains(ea_src, "SortCloseQueue"),
        "EA: SortCloseQueue sorts by lots descending",
        "EA logic")

    # ─── MACHINE GUN ────────────────────────────────────────────────────
    ok, ev = check_ea_input(ea_src, "MaxBurst", 5)
    add("machine_gun",
        "If 0.01 is profitable then 3 consecutive trades.. unusual cases mein 5 tak bhi gayi hun",
        "Max 5 trades per burst (machine gun cap)",
        ok, ev, "EA InpMaxBurst")

    ok, ev = check_ea_input(ea_src, "BurstCooldown", 0)
    add("machine_gun",
        "on a strong move she continues the machine gun sometimes uptil 5",
        "No artificial cooldown between bursts (let new probe trigger naturally)",
        ok, ev, "EA InpBurstCooldown")

    # ─── FILTERS ────────────────────────────────────────────────────────
    ok, ev = check_pine_input(pine_src, "SellOnly", False, tv_snap)
    add("filter",
        "Shano can't switch buy/sell context fast — but AI can. We take both sides when consecutive opposite signals appear.",
        "BOTH SIDES — buys + sells enabled (AI override of Shano's sell-only reflex)",
        ok, ev, "pine iSellOnly")

    ok, ev = check_pine_input(pine_src, "DailyCap", 500.0, tv_snap)
    add("filter",
        "500 USD hojaey profit khatam kar do",
        "Daily profit cap = $500",
        ok, ev, "pine iDailyCap")

    ok, ev = check_ea_input(ea_src, "DailyCap", 500.0)
    add("filter",
        "500 USD hojaey profit khatam kar do",
        "Daily profit cap on MT5 side = $500",
        ok, ev, "EA InpDailyCap")

    # ─── TIMING ─────────────────────────────────────────────────────────
    ok, ev = check_pine_input(pine_src, "SkipReopen", 20, tv_snap)
    add("timing",
        "first 20 minutes after market open on Monday absolutely no trade",
        "Skip first 20 min after week open",
        ok, ev, "pine iSkipReopen")

    ok, ev = check_pine_input(pine_src, "StopBefore", 60, tv_snap)
    add("timing",
        "before 2:00 AM pakistani time i dont trade at 1-2AM (1 hour before close)",
        "Stop new trades 60 min before week close",
        ok, ev, "pine iStopBefore")

    # ─── INSTRUMENT ─────────────────────────────────────────────────────
    ok, ev = check_pine_input(pine_src, "PCSymbol", "XAUUSD", tv_snap)
    add("instrument",
        "Gold (XAUUSD) ONLY — she does NOT trade BTC/crypto",
        "Trades XAUUSD only",
        ok, ev, "pine iPCSymbol")

    # ─── NEWS / EXTERNAL ────────────────────────────────────────────────
    add("philosophy",
        "I DONT WATCH NEWS AT ALL, I DONT WATCH FOREX FACTORY AT ALL",
        "No news/economic-calendar filter in system",
        not contains(ea_src, "newsapi") and not contains(ea_src, "forexfactory")
          and not contains(pine_src, "newsapi"),
        "Affirmative: no news API references in code",
        "EA + pine code")

    # ─── RUNTIME CHECKS (live state) ────────────────────────────────────
    if live:
        live_burst_max = live.get("burst_max")
        ok = live_burst_max == 5
        add("runtime",
            "5 tak bhi gayi hun aik long bar pe (live EA confirms 5 burst max)",
            "Running EA reports burst_max = 5",
            ok, repr(live_burst_max), "shano_live.json (EA runtime)")

        # Symbol match
        live_sym = live.get("symbol", "")
        add("runtime",
            "Gold (XAUUSD) ONLY",
            "Running EA symbol = XAUUSD",
            live_sym == "XAUUSD", repr(live_sym), "shano_live.json")

    # ─── SUMMARY ────────────────────────────────────────────────────────
    total = len(rules)
    passed = sum(1 for r in rules if r["ok"])
    out = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "compliance_pct": round(100 * passed / total, 1) if total else 0,
        "rules": rules,
    }
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
