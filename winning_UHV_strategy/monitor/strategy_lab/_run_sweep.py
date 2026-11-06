"""One-shot experiment sweep — creates N variants via the dashboard API,
runs compute on each, prints a comparison table.
"""
import json
import urllib.request

BASE = "http://localhost:3457"


def post(path, body=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def delete(path):
    req = urllib.request.Request(f"{BASE}{path}", method="DELETE")
    urllib.request.urlopen(req, timeout=10).read()


def main():
    # Sweep grid
    probe_confirms = [0.20, 0.30, 0.40, 0.45, 0.58]
    fear_ideals = [35.0, 70.0, 120.0]

    results = []
    created_ids = []

    for fi in fear_ideals:
        for pc in probe_confirms:
            name = f"sweep pc={pc} fi={fi}"
            print(f"  running {name}...")
            created = post("/api/shadow/create")
            exp_id = created["id"]
            created_ids.append(exp_id)
            post(f"/api/shadow/{exp_id}", {
                "name": name,
                "params": {"probeConfirm": pc, "fearIdeal": fi}
            })
            res = post(f"/api/shadow/{exp_id}/compute")
            if "error" in res:
                print(f"    error: {res['error']}")
                continue
            if res.get("warning"):
                print(f"    warning: {res['warning']}")
                continue
            m = res.get("metrics", {})
            results.append({
                "probeConfirm": pc,
                "fearIdeal": fi,
                "n": res.get("n_probes_analyzed"),
                "actual_pnl": m.get("actual_total_pnl"),
                "sim_main_pnl": m.get("sim_main_total_pnl"),
                "would_confirm": m.get("would_confirm_at_threshold"),
                "extra_vs_058": m.get("extra_confirms_vs_058"),
                "missed_potential": m.get("missed_potential_pnl"),
                "wr": m.get("sim_win_rate_pct"),
                "avg_win": m.get("sim_avg_win"),
                "avg_loss": m.get("sim_avg_loss"),
            })

    # Cleanup
    for eid in created_ids:
        try: delete(f"/api/shadow/{eid}")
        except Exception: pass

    if not results:
        print("\nNo results — probe shadow CSV may be empty or analyzer hasn't logged enough.")
        return

    # Print comparison
    print()
    print("=" * 96)
    print(f"  SWEEP RESULTS — {results[0]['n']} probes analyzed")
    print("=" * 96)
    print(f"  {'probeConfirm':<13}{'fearIdeal':<11}{'confirms':<10}{'extra':<8}{'sim P&L':<12}{'WR%':<7}{'avg+':<8}{'avg-':<8}{'missed':<10}")
    print("  " + "-" * 92)

    for r in sorted(results, key=lambda x: -x["sim_main_pnl"]):
        sim = r["sim_main_pnl"]
        bar = "*" if sim == max(x["sim_main_pnl"] for x in results) else " "
        print(f"  {bar} ${r['probeConfirm']:<11.2f}${r['fearIdeal']:<9.0f}{r['would_confirm']:<10}{r['extra_vs_058']:+<7}${sim:+8.2f}    {r['wr']:<7.1f}${r['avg_win']:<7.2f}${r['avg_loss']:<7.2f}${r['missed_potential']:+8.2f}")

    print()
    actual = results[0]["actual_pnl"]
    best = max(results, key=lambda x: x["sim_main_pnl"])
    worst = min(results, key=lambda x: x["sim_main_pnl"])
    print(f"  Actual today (real trades): ${actual:+.2f}")
    print(f"  Best variant:  pc=${best['probeConfirm']} fi=${best['fearIdeal']} -> ${best['sim_main_pnl']:+.2f}")
    print(f"  Worst variant: pc=${worst['probeConfirm']} fi=${worst['fearIdeal']} -> ${worst['sim_main_pnl']:+.2f}")


if __name__ == "__main__":
    main()
