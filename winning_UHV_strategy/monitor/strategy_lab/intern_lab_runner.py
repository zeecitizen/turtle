"""
Intern Lab Runner — long-running daemon that drives strategy_lab/lab.py.

Cycle (every 30 min):
  1. Run lab.py against latest trade history.
  2. Compute live P&L drift since last cycle.
  3. If live P&L is improving: stay the course, write status.
  4. If live P&L is stalling or worsening: ask Claude to propose 3 new
     variant configs based on the current results + last 30 trades.
     Append them to lab.py's variant list (via a JSON sidecar).
  5. Re-run lab including new variants. Apply best to live if delta > $50.
  6. Append iteration to history.jsonl.

Intent: while Zee is away, the system keeps probing for a better config.
Each iteration is small (one config tweak), reversible, and logged.
"""

from __future__ import annotations
import json
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

LAB_DIR = Path(__file__).parent
MON = LAB_DIR.parent
ROOT = MON.parent
PY = sys.executable

RESULTS_JSON = LAB_DIR / "results.json"
ITER_LOG = LAB_DIR / "iterations.jsonl"
STATUS_MD = LAB_DIR / "STATUS.md"
PROPOSED_JSON = LAB_DIR / "proposed_variants.json"
RUNNER_STATE = LAB_DIR / ".runner_state.json"
LIVE_JSON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_live.json")
CONFIG_JSON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_config.json")
LAB_PY = LAB_DIR / "lab.py"
API_KEY_FILE = MON / ".claude_api_key"

CYCLE_SECONDS = 30 * 60        # 30 min
APPLY_THRESHOLD_DELTA = 100.0  # apply variant only if it beats current by > $100 sim
DWELL_SECONDS = 60 * 60        # don't change config within 1h of last change
MIN_TRADES_BEFORE_CHANGE = 8   # need this many trades since last change to switch


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [LAB] {msg}"
    print(line, flush=True)
    try:
        (LAB_DIR / "lab_runner.log").open("a", encoding="utf-8").write(line + "\n")
    except Exception:
        pass


def load_live() -> dict:
    try:
        return json.loads(LIVE_JSON.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def load_results() -> dict:
    try:
        return json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_lab() -> dict:
    log("running lab.py ...")
    try:
        res = subprocess.run(
            [PY, str(LAB_PY)],
            capture_output=True, text=True, timeout=120,
            cwd=str(LAB_DIR),
        )
        if res.returncode != 0:
            log(f"lab.py exit={res.returncode} stderr={res.stderr[:200]}")
        log(res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "(no output)")
    except Exception as e:
        log(f"lab.py failed: {e}")
    return load_results()


def best_variant(snap: dict) -> dict | None:
    if not snap or not snap.get("results"):
        return None
    return max(snap["results"], key=lambda r: r["sim_total"])


def baseline_variant(snap: dict) -> dict | None:
    for r in snap.get("results", []):
        if r["id"] == "V0_baseline":
            return r
    return None


def apply_variant(variant_id: str) -> bool:
    log(f"applying variant {variant_id} to live config ...")
    try:
        res = subprocess.run(
            [PY, str(LAB_PY), "--apply", variant_id],
            capture_output=True, text=True, timeout=10,
        )
        log(res.stdout.strip())
        return res.returncode == 0
    except Exception as e:
        log(f"apply failed: {e}")
        return False


def propose_new_variants_via_claude(snap: dict, recent_history: list) -> list:
    """Ask Claude API for 3 fresh variant ideas based on current results."""
    api_key = None
    try:
        api_key = API_KEY_FILE.read_text("utf-8").strip()
    except Exception:
        pass
    if not api_key:
        log("no claude api key — skipping proposal step")
        return []

    try:
        import anthropic
    except ImportError:
        log("anthropic SDK not installed — skipping proposal step")
        return []

    prompt = f"""You are a quantitative strategist. The Shano momentum scalp on XAUUSD has these
recent variant simulation results (against the last 30 closed trades):

{json.dumps(snap.get("results", [])[:6], indent=2)}

Live config baseline:
{json.dumps(snap.get("baseline_config", {}), indent=2)}

Recent trades (newest first, lots>0.02 = main, lots<=0.02 = probe):
{json.dumps([{"t": t.get("time"), "lots": t.get("lots"), "pnl": t.get("pnl")} for t in recent_history[:30]], indent=2)}

Propose 3 NEW config variant ideas (different from those already tested). For
each, return JSON with:
  - id: short code starting "VX_..."
  - name: 1-line description
  - rationale: why this could outperform
  - overrides: dict of config keys to change (use only: probeConfirm, probeFail,
    probeLots, probeTimeout, trailTrigger, trailDrop, holdLotMax, fearIdeal,
    fearWashout, maxBurst, burstCooldown, maxPositions, overrideLots)
  - recovery_rate: 0.0-1.0 (how often you assume losing trades recover if held)

Return ONLY a JSON array of 3 objects, no prose."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # extract first JSON array
        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end < 0:
            log("claude response had no JSON array")
            return []
        return json.loads(text[start:end + 1])
    except Exception as e:
        log(f"claude proposal failed: {e}")
        return []


def write_status(snap: dict, action: str, reasoning: str):
    live = load_live()
    realized = live.get("realized_today", 0)
    week = live.get("week_realized", 0)
    cfg = live.get("config", {})

    best = best_variant(snap)
    base = baseline_variant(snap)

    lines = [
        "# Strategy Lab — Live Status",
        "",
        f"_Updated: {datetime.now().isoformat(timespec='seconds')}_",
        "",
        "## Live performance",
        f"- Today realized: **${realized:+.2f}**",
        f"- Week realized: **${week:+.2f}**",
        f"- Today main wins/losses: {live.get('today_main_wins')}W / {live.get('today_main_losses')}L",
        f"- Active config: fearIdeal=${cfg.get('fearIdeal')}, trailTrigger=${cfg.get('trailTrigger')}, "
        f"trailDrop=${cfg.get('trailDrop')}, probeConfirm=${cfg.get('probeConfirm')}",
        "",
        "## Last lab cycle",
        f"- Variants tested: {len(snap.get('results', []))}",
        f"- Top variant: **{best['name']}**" if best else "- No results yet",
        f"- Top sim total: ${best['sim_total']:+.2f}" if best else "",
        f"- vs baseline: ${(best['sim_total'] - base['sim_total']):+.2f}" if best and base else "",
        "",
        "## This iteration",
        f"- Action: **{action}**",
        f"- Reasoning: {reasoning}",
        "",
        "## How to inspect",
        "- Variant ranking: `monitor/strategy_lab/RESULTS.md`",
        "- Per-iteration log: `monitor/strategy_lab/iterations.jsonl`",
        "- Runner log: `monitor/strategy_lab/lab_runner.log`",
    ]
    STATUS_MD.write_text("\n".join(lines), encoding="utf-8")


def cycle(state: dict):
    """One iteration of the loop."""
    snap = run_lab()
    if not snap:
        log("no snap returned — skipping cycle")
        return

    best = best_variant(snap)
    base = baseline_variant(snap)
    if not best or not base:
        log("missing best/baseline — skipping")
        return

    delta = best["sim_total"] - base["sim_total"]
    live = load_live()
    realized = live.get("realized_today", 0)
    now = time.time()
    history = live.get("history", [])

    log(f"top variant: {best['id']} sim_total=${best['sim_total']:+.2f} "
        f"baseline=${base['sim_total']:+.2f} delta=${delta:+.2f} "
        f"(live realized today=${realized:+.2f})")

    action = "hold"
    reasoning = "best variant within tolerance — staying with current config"

    last_change = state.get("last_change_ts", 0)
    last_change_closes = state.get("last_change_closes_today", 0)
    closes_today = live.get("closes_today", 0)
    # closes_today resets at midnight; if it dropped below the snapshot we're
    # on a new day — treat that as fresh (closes_today is the new counter).
    if closes_today < last_change_closes:
        last_change_closes = 0
    trades_since_change = closes_today - last_change_closes
    dwell_left = max(0, DWELL_SECONDS - (now - last_change))
    tried = set(state.get("variants_tried", []))

    # Apply the best variant only if all guards pass:
    #   - delta meaningfully positive
    #   - not already live
    #   - dwell time elapsed since last change
    #   - enough trades since last change to gather evidence
    #   - haven't already tried this variant
    can_change = (
        delta >= APPLY_THRESHOLD_DELTA
        and best["id"] != "V0_baseline"
        and state.get("last_applied") != best["id"]
        and dwell_left == 0
        and trades_since_change >= MIN_TRADES_BEFORE_CHANGE
        and best["id"] not in tried
    )

    if delta >= APPLY_THRESHOLD_DELTA and best["id"] != "V0_baseline":
        if can_change:
            if apply_variant(best["id"]):
                action = f"applied {best['id']}"
                reasoning = f"delta=${delta:+.2f} > threshold ${APPLY_THRESHOLD_DELTA:.0f}; dwell ok; trades_since_change={trades_since_change}"
                state["last_applied"] = best["id"]
                state["last_change_ts"] = now
                state["last_change_closes_today"] = closes_today
                tried.add(best["id"])
                state["variants_tried"] = list(tried)
        else:
            reasons = []
            if state.get("last_applied") == best["id"]:
                reasons.append("already live")
            if dwell_left > 0:
                reasons.append(f"dwell {int(dwell_left/60)}min remaining")
            if trades_since_change < MIN_TRADES_BEFORE_CHANGE:
                reasons.append(f"only {trades_since_change} trades since last change (need {MIN_TRADES_BEFORE_CHANGE})")
            if best["id"] in tried:
                reasons.append("already tried this variant")
            action = "hold (guard)"
            reasoning = f"best is {best['id']} (delta=${delta:+.2f}) but: {', '.join(reasons)}"
    else:
        # Stalled — propose new variants
        history = live.get("history", [])
        proposals = propose_new_variants_via_claude(snap, history)
        if proposals:
            # Persist proposals (lab.py would need to read these — TODO integration)
            try:
                existing = []
                if PROPOSED_JSON.exists():
                    existing = json.loads(PROPOSED_JSON.read_text("utf-8"))
                PROPOSED_JSON.write_text(
                    json.dumps(existing + proposals, indent=2), encoding="utf-8"
                )
                action = "proposed variants"
                reasoning = f"claude proposed {len(proposals)} new variants — see proposed_variants.json"
                log(f"appended {len(proposals)} proposals")
            except Exception as e:
                log(f"failed to persist proposals: {e}")

    write_status(snap, action, reasoning)
    with ITER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "best": best["id"],
            "best_sim": best["sim_total"],
            "baseline_sim": base["sim_total"],
            "delta": round(delta, 2),
            "live_realized": realized,
            "action": action,
        }) + "\n")


def load_state() -> dict:
    try:
        return json.loads(RUNNER_STATE.read_text("utf-8"))
    except Exception:
        return {}


def save_state(state: dict):
    try:
        RUNNER_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="run a single cycle and exit")
    ap.add_argument("--interval", type=int, default=CYCLE_SECONDS,
                    help="seconds between cycles (default 1800)")
    args = ap.parse_args()

    state = load_state()
    log(f"intern lab runner starting (interval={args.interval}s, threshold=${APPLY_THRESHOLD_DELTA}, "
        f"dwell={DWELL_SECONDS}s, last_applied={state.get('last_applied','-')})")

    if args.once:
        cycle(state)
        save_state(state)
        return 0

    while True:
        try:
            cycle(state)
            save_state(state)
        except Exception as e:
            log(f"cycle failed: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
