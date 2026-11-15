# 1 November 2026 — "lock the +$400 and ride" on the 99.7% save, a tester bug, and the AWS VM

Zee: *"it's winners are all capped at 400 USD ... maybe we can do something like this: Move the SL to 400 profit price when we reach 400 in profit and let the trade gather further profits without losing the inital 400 -> so if it falls we have our 400 safe and if it goes further we can keep holding till it makes the target of around 5400 from setting A"* — later: *"instead of 400 each win could bring 800.. that would also be a great improvement"*, and *"trying to take multiple trades per day"*.

Setting B = `2026-10-30 23-08-23` (tester 399 / 99.7% / +$164,148; MT5 395 / 99.75% / +$162,491, random delay +$156,881). Its exits are a 20-pip broker TP ($2 of price = $400 at 2 lots) against a $26 stop ($5,200), exit mode 1 with the Exit Lab on (`InpXTgt=4, InpXTgtK=26`: a $26 lab target the TP always beats). Setting A = `2026-10-27 23-50-31` rides to a $27 lab target ($5,400).

## 1. Tester bug found and fixed (sim_full.py)
Since the real-tick fill commit of 22 Oct, a **moved** stop (breakeven, lock, ladder, trail) was filled at the **entry tick**: `_tick_fill` searched the real ticks from the trade's entry time, and a stop sitting at a level price had already crossed matched the first tick after entry. Symptom: exit = entry price, exit time = entry time, reason 6, "MFE $4 in 0 minutes".

Fix: position field `LCT` (last tick point at which the stop survived its check); both stop fill searches start from `max(entry, LCT)`.
- B and A are byte-identical before and after (their stops never move; A's 1.75R trail never fires).
- MT5 receipt: "lock +$2 at +$4, target $26" = MT5 342 / 90.06% / +$122,325 / worst −$5,842 vs the fixed tester 346 / 89.88% / +$121,548 / −$5,842.
- Independent audit (workflow): fix correct, verified trade by trade (307/307 stop fills are the first raw tick through the stop; 0 exits at the entry tick); `exitlab_check.py m15` 17/17. **Still wrong:** the whole-minute USD block (~line 436) biases **$ / ATR tick-trail rows (`InpXTr` 1–3) low by 30–70%** — those rows cannot be ranked by the tester.
- Every Exit Lab / mode-0 result with a moved stop from 22 Oct – 1 Nov is suspect and should be re-run. Turtle TV was restarted with the fixed engine.

## 2. Why the idea cannot work as worded
- A stop must sit below the market (EA `want < bid`) and the lab does nothing in the entry minute, so "move the SL to +$400 at +$400" is just the TP with a worse fill: tester +$153k (−$11k vs B).
- B's natural path (TP off, stop + Friday only): 100% of trades reach +$2, 94% +$3, 90% +$4, 71% +$10, 44% +$26 — but 60% of the trades that reach +$2 end at the full stop first, the median hold is 18 h, and with `InpMaxPos=1` the long holds block B's other entries (215 trades instead of 399). Net −$3.7k, DD $183k.
- Every lock that waits past +$2 leaves the trades that peak in between on the −$5,200 stop: trigger +$2.5 → 12 full stops, +$3 → 18, +$4 → 28, +$8 → 55. Tester net falls from +$153k to +$10k as the trigger rises.

## 3. The grid: 247 variants of real EA inputs on B's entries (`research/lock_ride.py`, `lock_ride.json`)
Families: lock (`InpXBeR/InpXBeOff`), ladder (`InpXLockR`), $ / ATR / keep-% trails, candle trails, partials (`InpXP1R`), barbell broker TPs, A's exits, more positions, and "TP $3–6 with a protection" for the $800 idea. Six refiners added 54 variants; a statistics, an execution and a framing skeptic reviewed the shortlist.

Best rows (tester, M15 2023–26; B = 399 / 99.75% / +$164,148 / worst −$998):

| Variant | Trades | WR | Net | Worst | Full stops |
|---|---|---|---|---|---|
| lock +$1 (half) at +$2, ride to $26, 3 same-side positions | 401 | 98.3% | +$187,930 | −$1,872 | 0 |
| lock +$1 at +$1.75, ride to $26, 3 same-side positions | 403 | 98.3% | +$178,860 | −$998 | 0 |
| TP $4, lock +$1 at +$2, 3 same-side positions | 417 | 98.8% | +$174,699 | −$5,200 | 1 |
| lock +$1 at +$2, ride to $26 (1 position) | 373 | 98.1% | +$172,507 | −$998 | 0 |
| B + 3 same-side positions (TP untouched) | 419 | 99.5% | +$170,137 | −$1,872 | 0 |
| TP $4, lock +$1 at +$2 (1 position) | 397 | 99.0% | +$167,332 | −$5,200 | 1 |
| breakeven at +$2, ride to $26 | 362 | 11.9% | +$159,982 | −$2,640 | 0 |
| ladder every $2 | 387 | 51.7% | +$157,716 | −$998 | 0 |
| lock +$2 at +$4, ride to $26 (Zee's rule with a gap) | 346 | 89.9% | +$121,548 | −$5,842 | 28 |
| TP $4 only | 363 | 89.8% | +$104,605 | −$5,842 | 30 |

The 1-position half-lock pays $5,200 on 20 trades in four years and ~$196 on the other 93%; it beats B only in 2025–26 (2023–24: −$2.6k vs B). Every row that pays $800 per win (TP $4 + breakeven) has a ~52% win rate: past +$400 the move is a coin flip on these entries.

## 4. MT5 (M15, Blueberry ticks 2023 → Oct 2026, $100k, 2 lots) — the verdict

| Setting | No delay | Random delay (project rule) |
|---|---|---|
| **B** | 395 / 99.75% / **+$162,491** / worst −$990 | 389 / 99.74% / **+$156,881** / −$1,006 |
| lock +$1 at +$2, ride to $26 (1 position) | 368 / 98.6% / +$167,530 / −$990 | 366 / 97.3% / **+$135,067** / −$5,428 |
| lock +$1.1 at +$2, 3 same-side positions | 397 / +$188,227 / −$1,660 | 397 / **+$158,006** / −$5,914 |
| lock +$1 at +$1.75, 3 same-side positions | 399 / +$179,195 / −$990 | 395 / **+$129,203** / −$6,000 |
| B + 3 same-side positions (TP untouched) | 415 / +$168,458 / −$1,462 | 410 / **+$165,698** / −$1,428 |
| lock +$2 at +$4, ride to $26 (reference) | 342 / 90.1% / +$122,325 | 340 / 89.7% / +$116,498 |

- **Random delay kills every lock variant:** the lock is an EA stop modification, delayed 0–18 s, so some trades never get it and run to the full stop (worst −$5.4k to −$6.0k); B's TP rests at the broker and loses only $5.6k to the delay. Under the project rule the locks make $22k–$28k less than B.
- **The only row above B under random delay is B itself with 3 same-side positions:** +$165,698 vs +$156,881 (+5.6%, ~20 trades), worst −$1,428, no full stop. Thin, in-sample, and the report's WR/worst for multi-position rows merge concurrent deals (trust net and trades). Worth a look on the 371-day frequency save (tester: 533 trades, 98.9%, +$195k).
- Live adds a cost B never pays: ~350 lock exits per 4 years would be market fills with slippage ($8k–$20k at $0.10–0.25/oz).

**Conclusion:** B's +$400 cap *is* the 99.7%. Nothing on its entries converts the cap into bigger wins without spending the win rate or the worst loss, and the one tester-positive shape (half-lock) fails MT5's random delay. The honest lever for "more" remains the frequency frontier (31 Oct) plus, possibly, extra same-side positions.

## 5. Also today
- AWS VM (Windows Server 2025, m7i-flex.large, 150 GB, `51.20.122.18`): SSH + RDP set up, Python 3.12 / Git / PXBT MT5 installed, the repo copied to `C:\Users\zeesh\turtle`, this chat and the Claude config copied, Turtle TV verified running there (start it from the RDP session with `launch_turtle_tv.bat`). The 47 GB of data (`simdata`, `runs`, the 15-min CSV, audio) is still copying. No MT5 rigs on the VM yet.
- Files: `research/lock_ride.py`, `lock_ride_save.py`, `lock_ride.json`; four saved settings `2026-11-01 06-06-0x ride ...` with `mt5_m15` receipts; `sim_full.py` fix. Nothing committed.
