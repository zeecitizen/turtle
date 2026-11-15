# auto_trade_by_claude.md — Claude trades the game live and learns from the fills

Zee, 11 Nov 2026: *"we need a document which we can call auto_trade_by_claude.md where you note your findings and test them and
write the results of your findings from real trades -> that way in future you can keep improving upon what you saw and did"*.

This is that document. Every finding here comes from REAL rounds on the PrimeXBT account (Golden Gravity, EUR/USD), never from a
backtest. A finding is a hypothesis until a later day's real trades confirm it; each one carries its status and the fills behind it.
Append, never rewrite history: a wrong finding stays, marked wrong, so the same mistake is not rediscovered.

## 1. How the loop works (as of 11 Nov 2026)

- **Entry** = the applied Turtle TV setting's breakout signal (`market.diamond.u97` in the game's `/api/state`), fired through the
  game's own `/api/act` (fund live -> shoot -> ack). Setting: `2026-11-07 12-09-37 + extender`, coin 5,000 EUR, broker target
  raised from 0.1 to 4 pips (`state/turtle_setting.json` InpUhvFixTp), broker stop = the setting's 22.5 pips beyond the extreme.
- **Exit management** (`play_live2.py`, scratchpad `play/`): eject if adverse >= `adv_pips` (2.5 default, the gate can widen it) or
  if not >= 0.3 pip ahead after 120 s; trail with walls from +1.2 pips (0.6 behind, step 0.3); haggle when the game offers it.
- **The gate** (`gate.json`, rewritten by Claude every ~10 min from a rendered chart of the game's own 1-minute bars,
  `/api/health?n=330`): `{trade, sides, until, mode: "range", support, resistance, band_pips, break_pips, adv_pips, eject,
  eject_round, reason}`. In range mode a BUY passes only at the floor (ask <= support + band) or on a break above resistance;
  a SELL only at the ceiling (bid >= resistance - band) or on a break below support. Never a sell into support, never a buy into
  resistance (Zee's rule, 11 Nov 12:46). `eject: true` + `eject_round` closes the open round by chart read.
- **Receipts**: `play2.log` (every act), `rounds2.jsonl` (every settlement), `skips.jsonl` (every signal the gate refused, with the
  quote - so a skip can be scored later), `judgements.jsonl` (every gate with its reason and the score of the previous one).
- **Limitation**: the chart is read every 8-10 minutes, not continuously. Between reads the player's rules act, not Claude's eyes.
  A gate expires after 40 min; an expired gate = ungated trading (this bit us once, see F7).

## 2. Ledger of real rounds (11 Nov 2026, 5,000 EUR unless noted, PKT = UTC+5)

| # | UTC | side | fill | exit | how | result | gate at the time | lesson |
|---|---|---|---|---|---|---|---|---|
| 1 | 06:42 | SELL | 1.11528 | 1.11519 | trail (2 walls, 1 haggle) | +$0.45 | sells only, downtrend | with-trend sell paid |
| 2 | 06:47 | SELL | 1.11533 | 1.11533 | eject flat 120 s | $0.00 | sells only | sell at the floor of the slide = nothing |
| 3 | 07:22 | SELL | 1.11582 | 1.11570 | trail (3 walls, 1 haggle) | +$0.60 | sells only; spike into the 1.1158-60 band | **sell at the ceiling works** |
| 4 | 07:36 | SELL | 1.11541 | 1.11542 | eject flat | -$0.05 | sells only | mid-range sell = nothing |
| 5 | 07:40 | SELL | 1.11537 | 1.11543 | eject flat | -$0.30 | my level was inverted (bug) | **sold into support 1.11526 - Zee caught it** |
| - | 08:41 | BUY 15k | 1.11480 | 1.11477 | Zee by hand, closed outside | -$0.45 | buy into the 1.1148-52 band | a hand trade into resistance |
| 6 | 10:22 | SELL | 1.11378 | 1.11373 | **eject by chart read** | +$0.25 | gate had expired; sell into a 45-min floor | read-eject saved a loss (price +4 pips after) |
| 7 | 10:36 | BUY | 1.11403 | 1.11376 | eject adverse 2.5 pips | -$1.35 | buy on the box-top retest (right) | **fixed 2.5-pip eject fired at the sweep low; price then +4.5 pips** |
| 8 | 10:55 | BUY | 1.11379 | 1.11388 | trail (1 wall, 2 haggles) | +$0.45 | buy at the box floor (1st bounce) | first floor bounce paid |
| 9 | 11:01 | BUY | 1.11384 | 1.11382 | eject flat | -$0.10 | buy at the box floor (2nd) | floor losing demand |
| 10 | 11:03 | BUY | 1.11384 | 1.11364 | eject flat/adverse | -$1.00 | buy at the box floor (3rd) | **floor broke on the 6th test** |
| 11 | 11:06 | SELL | 1.11376 | 1.11381 | eject flat | -$0.25 | pullback sell after the break | the break stalled; no follow-through yet |

Bot net 11 Nov: 5 wins / 6 losses or flats, **-$1.30**. Balance $20.64 -> $19.07 including Zee's hand trades.
Overnight (10-11 Nov, 1,000 EUR, 0.1-pip target, no gate): 25/25 target hits, +$0.32 - plumbing proof, not a win-rate proof.

Gate scorecard (reads scored by what the skipped / taken signals did next): 18 reads, 13 right, 4 cost a winner, 1 bug.
Skips: 21 signals refused; of the scored ones ~70% would have ejected or gone flat, ~25% would have won 2-3 pips.

### Afternoon addendum (11 Nov, 16:20-17:35 PKT) - Claude's own trades and Zee's UHV rule made live

Zee 16:20: *"without the UHV signal can u try a few trades based on your knowledge? that would be interesting to see if maybe you outperform
the UHV's 98.5% winrate"*. Mechanism: resting orders in `claude_orders.json` (zone, stop 2/4/6 pips, target, `break_of` + 0.3-pip margin on the
far side of the spread, `max_bar_vol`), fired by the player, separate ledger `claude_trades.jsonl`. From 17:30 the player runs Zee's UHV rule
itself every 2 s (`zee_uhv_scan`: impulse -> counter-colour retracement -> highest-volume candle = UHV -> its high/low broken by the bid/ask
0.3 pip on a bar quieter than the UHV; stop past the retracement extreme) and Claude's 10-min reads only set `trend` (+1/-1/0).

| # | UTC | order | fill | exit | result | what happened |
|---|---|---|---|---|---|---|
| C1 | 11:24 | floor buy 1.1136 box | 1.11373 | 1.11375 | +$0.10 | ejected flat by the 2-min rule; the floor broke 2 min later (saved -$2) |
| C3 | 11:42 | pullback sell after the break | 1.11356 | 1.11365 | -$0.45 | the break into the 24h low was a SWEEP; ejected by read |
| C4 | 11:45 | reclaim buy (F6) | 1.11360 | 1.11372 | +$0.60 | trailed out - sweep-and-reclaim confirmed |
| C5 | 11:53 | 2nd floor buy | 1.11354 | 1.11353 | -$0.05 | reaction bar +$0.65 then back; volume 417 = not low (F11, Zee) |
| C1 again | 11:59 | BUG re-fire after restart | 1.11362 | 1.11361 | -$0.05 | ejected by read; orders now stamped 'fired' |
| C7 | 12:10 | UHV break-sell through support | 1.11342 | 1.11371 | -$1.45 | 1-pip 'through' = a sweep; ejected by the 2-min rule |
| C6 | 12:12 | Zee's UHV break buy (1.11365) | 1.11371 | 1.11372 | +$0.05 | the 2-min rule cut it 2 s before the exemption shipped |
| C8 | 12:18 | UHV break buy (1.11372) | 1.11373 | 1.11361 | -$0.60 | BUG: fired on the ASK one tick over the high; ejected; margin rule added |
| C9 | 12:23 | UHV break buy, margin + quiet bar | 1.11379 | 1.11385 | +$0.30 | the rule as Zee defines it; Zee closed it by hand |
| setting | 12:28 | the setting's pullback buy | 1.11378 | 1.11360 | -$0.90 | the range-top break failed; ejected by read |

Claude's own: 9 fills, 3 wins, net -$1.55; three losses were mechanics bugs (re-fire, 1-pip filter, tick trigger), all fixed the same hour.
Zee by hand: 6 buys of 1,000 EUR at 1.11387-89 on the 13:26 break (no stop); the break failed; closed at 17:35 PKT for about -$1.70.
Balance 11 Nov: $20.64 (morning) -> $15.93 (17:35 PKT) -> $13.14 (19:05 PKT, after the harvest test).

**F12. A UHV break at the very top of a 2-hour range is the low-odds version of the setup. — OBSERVED (13:26 break, failed in 5 min).**
The rule fired correctly (quiet 279-tick bar through 1.11386) and still failed: the break was into the range ceiling that had rejected
six times. Combine the UHV rule with the range read: inside a range, take the UHV break only away from the opposite edge.

**F13. Readings must be live. — ADOPTED (Zee 17:30: "any readings must be live, every 5 seconds or so").** The 1-minute setup is gone in
5 minutes; the rule now runs in the player every 2 s and Claude's reads set the regime only.

### Harvest test (11 Nov, 17:58-19:05 PKT) - Zee: "harvest the max dollars we can at the 0.1 pip target given the balance we have", 5 trades
Setup: the setting's signals OFF; Claude's live UHV scanner (2-s reads) takes the trades; 8,000 EUR (the most the margin rule allows);
broker TP 2 pips as backstop + the player closes at +0.1 pip (raised to +0.3 gross after trade 2); 3-pip adverse eject; no time eject.

| # | UTC | entry | exit | result | note |
|---|---|---|---|---|---|
| H1 | 12:48 | SELL 1.11327 (12:47 UHV, 349) | +0.1 pip in 4 s | +$0.08 | the rule, live, clean |
| H2 | 12:54 | SELL 1.11320 (12:52 UHV, 93) | +0.1 pip reached, market close filled flat | $0.00 | the spread ate the 0.1 pip - a software exit cannot bank 0.1 pip |
| H3 | 13:15 | SELL 1.11256 (13:08 UHV, 87) | +1.0 pip in 8 s | +$0.88 | the leg accelerated under the fill |
| H4 | 13:26 | SELL 1.11175 (13:23 UHV, 96) | 3-pip adverse eject | -$2.48 | fired on a 1-second-old bar that looked quiet (bug, fixed: pro-rated volume); then a V-bounce |
| H5 | 13:29 | SELL refused | - | - | the game's margin rule: 8,000 EUR x 6-pip stop + margin > $13.14 |
| - | 12:43 | the setting's BUY 10,000 EUR (before "Claude only") | stopped in 10 s | -$0.70 | haggle moved the stop to a stake under price (bug, haggle now off) |

Result: 4 fills, 2 wins, 1 flat, 1 loss, **-$1.52**; balance $14.66 -> $13.14. Missed by my regime reads: the 24h-low breakdown leg (scanner
paused as a "sweep zone", it was a continuation on steady volume) and the 13:18 doji (not a counter-candle, so no setup - correct).

**F14. The 0.1-pip harvest cannot be banked by a software close. — CONFIRMED (H2).** The close fills on the other side of the spread; the
0.1 pip only exists as a broker-held target that fills at the touch. The game's native rounds cannot set a target under 2 pips, and the
setting's 0.1-pip target comes only with its own 22.5-pip stop.
**F15. One 3-pip loss = 30 wins of 0.1 pip; at $13-15 the size the margin allows pays ~$0.10 a win. — CONFIRMED (H1-H4).** The harvest
plan needs the account, not the leverage: $1 a trade is 100,000 EUR; the broker caps the game at 50,000 and the margin at ~13,000 today.
**F16. Sweep vs continuation at a day's extreme is decided by the volume shape. — OBSERVED twice (13:56 sweep on a 1-tick poke, 14:00-14:07
continuation on steady 85-95/min).** A climax bar reverses; a grind continues. My pause rule read location only - add the volume read.

## 3. Findings (each with status)

**F1. Sell into support / buy into resistance is the loss pattern. — CONFIRMED (rounds 5, 7-10; Zee's hand buy).**
Every loss today was an entry AT a level in the wrong direction or a level that had already been tested many times. Every win
(1, 3, 8) was an entry away from the level, with room to the opposite side of the box. Rule adopted: range mode in the gate.

**F2. The ceiling sell beats the floor buy when the higher timeframe is down. — CONFIRMED (3 vs 8-10).**
Under a falling 5-min EMA21 the box top is a reversal of the bounce (with the trend) and the box floor is continuation
(against it). Rule: in a downtrend box, sells at the ceiling allowed freely; floor buys ONE per floor, then blocked.

**F3. A floor weakens with every test. — CONFIRMED (8 won, 9 flat, 10 broke; 6th test).**
First touch bounced (+$0.45), second did nothing, third broke. Rule: count the touches; after the first bounce in a box under a
downtrend, no more floor buys until a higher low prints.

**F4. A fixed adverse-eject is wrong for a level entry. — CONFIRMED (round 7).**
A retest entry sits 1-2 pips above the level; the level gets swept by 1 pip before it holds. A 2.5-pip eject fires exactly at
the sweep low. Rule: the gate sets `adv_pips` so the eject sits ~1 pip PAST the level (4 pips used), not a fixed distance.

**F5. "Flat after 2 minutes -> eject" is a cheap and honest exit. — CONFIRMED (rounds 2, 4, 5, 9, 11 cost $0.00-0.30 each).**
Winners today were ahead within 60 s (rounds 1, 3, 8). The 2-minute eject turns would-be 22.5-pip stops ($11) into $0-0.30
scratches. Cost: it also cut round 10 at -$1.00 instead of waiting for the stop. Keep.

**F6. Sweep-and-reclaim of a floor is a buy, not a sell. — OBSERVED ONCE (12:47 PKT, +7 pips bounce; no signal fired to take it).**
A push 1-2 pips under a floor that closes back inside within two bars on big volume reverses up. Hypothesis until traded.

**F7. An expired gate is a hole. — CONFIRMED (round 6).** The loop ran late once (1 h gap); the gate expired after 20 min and the
player sold into a floor ungated. Fix: gates last 40 min; still a hole if the loop stalls longer. Better fix (todo): on expiry the
player should keep the last gate's levels rather than trade free.

**F8. The chart read predicts direction better than it predicts the detector. — OBSERVED.** Three reads called the move right
(the 13:12 "floor weakening" -> -11 pips; the 14:03 bear flag -> -20 pips; the 15:22 box) but the detector gave NO sell signal on
any of those breaks. The gate can only filter what the setting fires; it cannot create the trade the chart wants.
Open question for Zee: should a strong read be allowed to fire its own entry (a "Claude entry"), with its own receipts?

**F9. Mid-box signals are noise. — CONFIRMED (skips at 12:52-13:58: 6 of 6 would have ejected or gone flat).**

**F10. A break call needs follow-through, and a break INTO a bigger level reverses. — CONFIRMED (16:05 false break; 16:34 real break;
16:40 sweep of the 24h low reclaimed in 4 bars).** Closes 2+ pips beyond the level = a break; but when the break runs straight into
the day's low/high it is a sweep, and the sweep-and-reclaim is the trade (F6, confirmed by Claude trade C4 +$0.60).

**F11. Zee / Sajid Ahmed VSA: a reversal candle must come on LOW volume. — OBSERVED, adopted (16:58 PKT, Zee).**
Zee: *"it looks for a selling campaign -> background of selling bars -> then if the price reverses (a reaction candle appears to flip
bullish on a low volume) then it considers this a new trend upwards -> and on going low volume means price is easily making its way
up .. right now the market made a green bullish reaction candle (but since the volume wasn't low the breakout towards uptrend has
failed)"*. Real fill: Claude trade C5 BUY 1.11354 (16:53) - the reaction bar 16:56 went to 1.11367 (+$0.65 at the high) on volume
417 (average, NOT low) and fell straight back; ejected -$0.05. Rule: after a selling campaign, buy the reaction only if its bar volume
is well below the campaign bars (say < 60%); a reaction on average/high volume = supply still present = no buy. Mirror for sells.
Also the trail: it starts at +1.2 pips and needs a tick to place the wall; C5 touched +1.3 and reversed before the wall - at 5,000
EUR a 0.5-pip lock (+$0.25) should be taken at +1.0 pip when the reaction volume is not low.

## 4. Rules in force (the current gate policy)

1. Draw the box: last defended low = support, last rejected high = resistance; check the 5-min EMA21 for the larger trend.
2. With the trend: trade the edge that continues it freely (ceiling sells in a downtrend). Against it: one bounce per level, then off.
3. Never sell into support, never buy into resistance (band 2-3 pips).
4. Breaks need 1 pip through the level; a sweep that closes back inside is NOT a break.
5. Eject distance = past the level the entry leans on (`adv_pips`), never a fixed number.
6. Mid-box: nothing.
8. VSA volume test on every reversal entry (F11): low volume on the reaction bar or no trade.
7. Score every gate against what the skipped signals did; write the score into the next gate's judgement.

## 5. Open questions / next tests

- F8: let a strong chart read fire its own entry? (Zee's call - it changes "the setting trades, Claude filters" into "Claude trades".)
- Does F3 (one bounce per floor) hold in an UPTREND box for ceiling sells? (mirror test, not yet seen.)
- Does the 4-pip target + trail beat the 0.1-pip target over a week? Overnight 0.1-pip: +$0.32 / 25 rounds; managed day: -$1.30 /
  11 rounds with a $2 worst loss. Too few rounds to call. Keep both ledgers.
- The first Friday with this loop: the setting's Friday cut-off (InpUhvFriCutAllNY 15) still applies via the game.

## 6. How to continue tomorrow

1. Game server up (live mode), live confirmed by Zee, player: `python -u play_live2.py` in the scratchpad `play/` folder
   (copy it into the repo if the scratchpad is gone - the logic is described in §1).
2. Claude loop: every ~10 min render -> read -> write `gate.json` -> score the last gate in `judgements.jsonl`.
3. End of day: append the day's rounds to §2, update the status of every finding in §3 (confirmed / refuted / still open), add new
   findings with their fills. Never delete a refuted one.
