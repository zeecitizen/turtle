"""u97_bot.py (2026-11-05 evening: coin = 10,000 EUR, Zee: "0.02 wins mean nothing ... they don't buy bread") - plays Golden Gravity LIVE for Zee while he sleeps (2026-11-05: "play a few rounds and try to increase the capital by winning..
i have allocated a budget of $5 to testing this so its okay if you loose till $5.. please play on LIVE").

Uses only the game's own player actions (/api/act: fund -> shoot, eject, ack) - the same buttons Zee presses.
Rules (hard-coded):
  * real money (kind live), 1 coin, only on a fresh Turtle TV UHV 97.7% diamond (u97, age <= MAX_AGE_S), one round per diamond
  * the setting's own stop / target; an eject at -EJECT_PIPS (instead of riding to the ~20-pip stop)
  * STOP for good when the balance is BUDGET_USD below the starting balance, when the game refuses live, or when STOP file exists
Log: u97_bot.log beside this file."""
import json
import os
import time
import urllib.request
import uuid

BASE = "http://127.0.0.1:8790"
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "u97_bot.log")
STOPF = os.path.join(HERE, "STOP_BOT")
FLOOR_FIXED = 13.92                 # 2026-11-06: the floor of this session ($23.92 - $10), kept across bot restarts
BUDGET_USD = 10.0                  # Zee 2026-11-05 night: "stop if you loose $10"
MAX_AGE_S = 2.5
EJECT_PIPS = 2.0
PIP = 0.0001
COIN_EUR = 5000.0                  # one game coin (state/admin.json EURUSD coin_oz)


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def state():
    with urllib.request.urlopen(BASE + "/api/state", timeout=5) as r:
        return json.load(r)


def act(action, **args):
    body = json.dumps({"action": action, "nonce": "bot-" + uuid.uuid4().hex, "sent_at": time.time(), "args": args}).encode()
    req = urllib.request.Request(BASE + "/api/act", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        res = json.load(r)
    log(f"act {action} {args} -> {res}")
    return res


FEED_MAX_AGE_S = 8.0     # 2026-11-06: the PrimeXBT tab froze in the background - quotes came in bursts after minutes of silence. A quote older
FEED_STEADY_S = 120.0    # than this marks the feed unsteady, and the bot shoots only after this many seconds of continuously fresh quotes


def main():
    while True:                                                   # wait until the game has the account (it may still be reconnecting)
        try:
            s = state()
            if (s.get("account") or {}).get("balance") is not None:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(3)
    start = float(s["account"]["balance"])
    floor = FLOOR_FIXED if FLOOR_FIXED else start - BUDGET_USD
    log(f"START balance ${start:.2f}  floor ${floor:.2f}  (budget ${BUDGET_USD})")
    done_ids, shot_id, last_settled = set(), None, None
    main._bad_feed_t = time.time()                                # start unsteady: a restart never shoots on a cold feed
    tally, bot_ids = [], set()
    while True:
        if os.path.exists(STOPF):
            log("STOP file found - stopping"); return
        try:
            s = state()
        except Exception as e:  # noqa: BLE001
            log(f"state failed: {type(e).__name__}"); main._bad_feed_t = time.time(); time.sleep(2); continue
        fd = s.get("feed") or {}
        if not fd.get("ok") or float(fd["age_s"] if fd.get("age_s") is not None else 99.0) > FEED_MAX_AGE_S:
            main._bad_feed_t = time.time()
        ph = s.get("phase")
        bal = float((s.get("account") or {}).get("balance") or 0)
        r = s.get("round") or {}
        if ph == "settled":
            st = s.get("settlement") or {}
            rid = r.get("id") or st.get("round_id")
            if rid != last_settled:
                last_settled = rid
                res_usd = st.get('result_usd', r.get('result_usd'))
                if res_usd is not None and rid in bot_ids and abs(float(res_usd)) > 1e-9:   # only the bot's own rounds; a $0 round is no loss                           # Zee 2026-11-06: harvest rule - stop when the live win rate collapses below 94%
                    tally.append(float(res_usd) > 0)
                    bot_ids.discard(rid)
                    n = len(tally); wr = 100.0 * sum(tally) / n
                    log(f"TALLY {sum(tally)}/{n} won = {wr:.1f}%")
                    if n >= 20 and wr < 94.0:
                        log(f"HARVEST STOP: win rate {wr:.1f}% < 94% after {n} rounds - time to withdraw"); act("ack"); return
                log(f"SETTLED {rid} kind={r.get('kind')} result={st.get('result_usd', r.get('result_usd'))} outcome={st.get('outcome')} balance=${bal:.2f}")
            time.sleep(1.5)
            act("ack")
            continue
        if ph in ("open", "closing", "sending"):
            q = s.get("quote") or {}
            fill, side = r.get("fill"), r.get("side")
            if ph == "open" and fill and side and q.get("bid"):
                m = ((q["bid"] - fill) if side > 0 else (fill - q["ask"])) / PIP
                if m <= -EJECT_PIPS and not r.get("close_intent"):
                    log(f"EJECT at {m:.1f} pips")
                    act("eject")
                    time.sleep(1)
            time.sleep(0.25)
            continue
        if ph not in ("lobby", "aiming"):
            time.sleep(0.5); continue
        if bal and bal <= floor + 1e-9:
            log(f"BUDGET USED: balance ${bal:.2f} <= floor ${floor:.2f} - stopping"); return
        if time.time() - main._bad_feed_t < FEED_STEADY_S:
            why = f"feed not steady (needs {FEED_STEADY_S:.0f}s of fresh quotes)"
            if why != getattr(main, "_why", None):
                main._why = why; log(f"WAITING - {why}")
            time.sleep(1); continue
        lim = s.get("limits") or {}
        if not lim.get("live_allowed"):
            why = lim.get("why_not_live")
            if why != getattr(main, "_why", None):
                main._why = why; log(f"WAITING - live not allowed ({why})")
            time.sleep(2); continue
        main._why = None
        d = (s.get("market") or {}).get("diamond") or {}
        sid = d.get("id")
        if d.get("u97") and d.get("cut") and sid not in done_ids and (d.get("age") or 99) <= MAX_AGE_S:
            done_ids.add(sid)
            side = int(d["cut"])
            if ph == "aiming":
                act("unfund")
            tgt = (s.get("settings") or {}).get("target")
            # Zee 2026-11-06: "Play now at 15,000 EUR ... At about $66 we move up to 50,000 automatically". As many 5,000-EUR coins as the
            # balance carries (the game's own rule: risk + 1:1000 margin <= balance), 1 to 10 (50,000 EUR)
            q = s.get("quote") or {}
            px = (q.get("bid", 1.12) + q.get("ask", 1.12)) / 2.0
            per = COIN_EUR * (0.0002 + px / 1000.0)
            cap = max(1, min(10, int(bal / per))) if bal else 1
            rl = int(d.get("u97_risk", 1))                       # Zee 2026-11-06: size by zone - dead sure (risk 0) = the most the account carries,
            coins = cap if rl == 0 else 1                         # low risk (1) = 1 coin; rain / storm never reach here (the angel blocks them)
            res = act("fund", kind="live", side=side, target=tgt, coins=coins)
            if res.get("accepted"):
                res2 = act("shoot")
                if res2.get("accepted"):
                    for _ in range(20):                           # remember this round's id, so only the bot's own rounds are counted
                        try:
                            rr = (state().get("round") or {}).get("id")
                        except Exception:  # noqa: BLE001
                            rr = None
                        if rr:
                            bot_ids.add(rr); break
                        time.sleep(0.1)
                    log(f"SHOT {'BUY' if side > 0 else 'SELL'} {coins} coins ({coins * COIN_EUR:,.0f} EUR) on diamond {sid} risk level {d.get('u97_risk')} (age {d.get('age')}s) balance ${bal:.2f}")
                    shot_id = sid
                else:
                    act("unfund")
            continue
        time.sleep(0.2)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log(f"CRASH {type(e).__name__}: {e}")
