# Shano Interview — Live Trading Strategy

## Session 1: 2026-04-25 (WhatsApp + Voice Call)
**Interviewer:** Claude (via Zeeshan)
**Subject:** Shano (sister) — Gold momentum scalper

### Q: Kya instrument trade karti ho?
**A:** Gold (XAUUSD) ONLY — she does NOT trade BTC/crypto

### Q: Buy ya sell?
**A:** SELL ONLY — BUY trades in her MT5 data are NOT from Shano's strategy. The buys LOST -$28 and dragged WR down to 69%.
Real SELL-only WR: **71.0%** (22W/31 trades, +$151.77)

### Q: Kaise pehchanti ho kab trade karna hai?
**A:** 1st big red candle → WATCH ONLY, do NOT trade. 2nd red candle → open 0.01 lot probe ("jab second red candle ati hai"). 3rd candle check: if RED → probe positive → GO BIG with main lot. If 3rd candle is GREEN → probe negative → SKIP, momentum died. "Mostly neeechay jari hoti hai 3rd candle" — usually 3rd continues down.

### Q: Exit kaise karti ho?
**A:** Machine gun style — each trade individually targets $10. Open, hit $10, close, next trade — all within seconds. Panic closes at $5-6 when profit starts dropping back from $10. "it was coming back from 10.. so i closed in a hurry". Each trade is independent, she doesn't wait for total.

### Q: Kitni trades ek saath?
**A:** Max 3 trades open at once. Varied lots: 0.01 + 0.40 + 0.06 (NOT 3x 0.40). Risk management: avoids 3x big lots → "-$200 drawdown x 3 = washout". The probe (0.01) counts as one of the 3.

### Q: Quiet market mein kya karti ho?
**A:** "wait karti hun" — she waits, doesn't force trades. Only trades when big candles appear.

### Q: Loss management?
**A:** Cut at -$10 per trade. After loss: retry same way, wait 8-10 min for next big red. Post-loss patience, no revenge trading with bigger size.

---

## Session 2: 2026-04-26 (Live In-Person Interview)
**Interviewer:** Claude (via Zeeshan typing answers)
**Subject:** Shano sitting in front of Zeeshan

### Q: To aap pehli bari red candle pe kuch nahi karti? Sirf dekhti ho? Aur jab doosri red candle aati hai TAB 0.01 lot lagati ho?
**A:** "sirf dekhti hun kuch ni karti pehli red candle pe. haan dusri red candle pe 0.01 lot lagati hu ji bilkul"

### Q: Aur jab 3rd candle bhi red hoti hai, tab kitni lot lagati ho? 0.08? 0.20? 0.40?
**A:** "agar 0.01 lot ki trade ka profit agar 0.58 USD se upar jata hai profit USD mein to mein 0.4 ki lot laga deti hun"

### Q: Capital ke hisaab se lot size?
**A:** Shano's exact words:
- "agar mera capital 300 hai mein 0.4 ki ni lungi 0.06 ki lungi kyunk mera capital enough ni hai drawdown k liay"
- "matlab agar 500 USD to kum hai to 0.06 ya 0.08 ki lungi matlab"
- **Capital → Lot Size Table:**
  - 300 se neechay: 0.01 se 0.06 tak koi bhi
  - 300 hai to: 0.06
  - 300-500 range: 0.08
  - 500-800 range: 0.40

### Q: Jab 0.01 ki probe lagayi aur 3rd candle GREEN aa gayi — kya aap 0.01 wali trade CLOSE karti ho ya rehne deti ho?
### Q: Jab 0.01 ka profit $0.58 se upar jata hai aur aap 0.40 lagati ho — kya 0.01 wali trade ABHI BHI open rehti hai ya pehle close karti ho?
**A:** "0.01 wali on rehti hai.. 0.4 ko close karti hun, phir 0.01 ko close karti hun kyunk 0.4 wali ko jaldi se in-time close karna zaruri hai.. beshak 0.01 ki loss mein chali jaey tab tak kyunk wo loss 0.01 wali ka to sirf 2 USD ka hota hai"

**Key insight:** 
- 0.01 probe STAYS OPEN alongside 0.40
- Close 0.40 FIRST (priority — big position)
- Close 0.01 AFTER (even if in loss — max ~$2 loss)
- 0.01 is essentially sacrificial

### Q: Jab 0.40 ki trade $10 ke qareeb hoti hai — kya aap EXACTLY $10 pe close karti ho ya jab profit DROP hone lagta hai tab close karti ho?
**A:** "jab drop honay lagta hai tab close karti hun.. wo 18 pe ja k 7.65 pe bhi close hosakta hai"

**Key insight:**
- NOT a fixed $10 target
- She watches profit, closes when it DROPS
- Can go as high as $18, close at $7.65 if dropping
- This is trailing-stop behavior, not fixed TP

### Q: Loss management — extreme case?
**A (from earlier):** "i wait for the loss to turn into profit again, which it does almost 80% of the times. For the rest... we close trade before it hits 50% of the initial capital lost. Example: 700 → 250 → 680"

### Q: Jab 0.01 ka profit $0.58 se UPAR jata hai — to KITNI candles ke andar 0.40 lagati ho? FORAN ya next candle ka wait?
**A:** "FORAN.. without watching next candle"

**Key insight:** IMMEDIATE — as soon as $0.58 crossed, open 0.40. No candle confirmation needed.

### Q: Agar 0.01 ka profit $0.58 tak KABHI nahi pohuncha — to kitni der wait karti ho before giving up?
**A:** "Minus 3 loss tak janay deti hun.. wait karun gi minus 3 loss tak on that 0.01 trade.. negative k baad bhi to positive pe ajati hai.. without watching candles.. mein bass usski value ko hee bass dekhti rehti hun"

**Key insights:**
- Probe fail threshold: **-$3 loss** on the 0.01 trade
- She does NOT watch candles for probe — purely watches dollar value
- Even if probe goes negative, she waits — it can come back positive
- Only gives up at -$3
- This means: probe confirm = +$0.58, probe fail = -$3.00

---

### Q: $10 profit pe close karti ho — kya EXACTLY $10 ya qareeb qareeb?
**A:** "8 pe bhi kar deti hun, 12 pe bhi kar deti hun"

**Key insight:** Flexible exit — anywhere from $8 to $12+, not fixed

### Q: Loss mein jab trade hai — KITNI der wait karti ho?
**A:** "jab tak wapis na ayay (0.4 lot wali ka)"

**Key insight:** She holds losing 0.40 trades indefinitely until they come back. No time limit.

### Q: Kitna profit ho jaye to us din BAND kar deti ho? Kitna loss ho jaye to BAND?
**A:** "500 USD hojaey profit khatam kar do"

**Key insight:** Daily profit cap = $500. No explicit daily loss cap mentioned (she holds losses).

### Q: Koi indicator lagaya hua hai chart pe? Ya sirf candles?
**A:** "no indicator"

### Q: Chart pe kaunsi timeframe dekhti ho?
**A:** "1 min"

### Q: Din mein kaunse waqt trade karti ho?
**A:** "anytime"

### Q: Ek din mein lagbhag kitni trades karti ho?
**A:** "70-80 in one day"

### Q: "Big red candle" — kya pichli candles se compare karti ho ya aankh se? WICK matter karti hai ya sirf BODY?
**A:** "sirf body matter karti hai pichli se dekh kar compare karti hun.. its a body moving upar neechay on a line.. jab wick minimum reh jaeygi aur body max hogi.. pichli 2 candle se bari visibly bari.. aur pichli candle se quarter bari (second candle se) phir trade leni hai 0.01 ki"

**Key insights:**
- BODY ONLY — wick doesn't matter
- Minimum wick + maximum body = ideal candle
- Must be VISIBLY bigger than previous 2 candles
- 2nd candle must be at least 1/4 (quarter) bigger than 1st candle
- Then open 0.01 probe

### Q: Ek trade close karke kitne second baad next trade?
**A:** "aik close kar di sab khatam hogaya.. taqreeban 7-8 mins lag jatay hain setup bantay bantay"

**Key insight:** NOT instant! Takes 7-8 minutes for next setup to form. "Machine gun" refers to rapid-fire within one setup, not back-to-back setups.

### Q: Ek burst mein kitni trades lagatar karti ho?
**A:** "If 0.01 is profitable then 3 consecutive trades.. unusual cases mein 5 tak bhi gayi hun.. aik long bar pe"

**Key insight:** 
- Normal burst: 3 trades (probe + 2 big)
- Unusual/long bar: up to 5 trades
- All within one setup/move

---

## Strategy Summary (COMPLETE — All Verified)

| Rule | Detail |
|------|--------|
| Instrument | XAUUSD (Gold) ONLY |
| Direction | SELL ONLY |
| Timeframe | 1 minute |
| Session | Anytime — no specific hours |
| Daily Volume | 70-80 trades per day |
| Indicators | NONE — pure candle reading |
| Detection | Body only (no wick). Visibly bigger than prev 2 candles. 2nd candle ≥ 1.25x 1st candle body |
| Probe | 0.01 lot on 2nd red candle, stays open throughout |
| Confirmation | Probe profit > $0.58 → IMMEDIATELY open big (no candle wait) |
| Probe Fail | Probe loss hits -$3.00 → give up (watches $ value, NOT candles) |
| Main Trade | 0.40 lots (if capital > $500), scaled by capital |
| Lot Scaling | <$300: 0.01-0.06, $300: 0.06, $300-500: 0.08, $500-800: 0.40 |
| Exit | Watch profit, close when dropping ($8-$12 range, not fixed) |
| Close Order | 0.40 first (priority), then 0.01 (sacrificial) |
| Burst Size | 3 trades normal, up to 5 on long bars |
| Setup Time | 7-8 min between setups |
| Max Open | 3 trades simultaneously |
| Loss Hold | Hold 0.40 indefinitely until it comes back |
| Daily Cap | $500 profit → stop trading |
| Extreme Loss | Hold for reversal (80% success), cut at 50% capital loss |
| Quiet Market | Wait, don't force |

---

## Session 3: 2026-04-27 (Live System Validation + Follow-ups)
**Context:** First end-to-end automated trade just executed (+$21.22 in 5 min), Shano sitting in front of Zeeshan reviewing system behavior. Her current MT5 also has 3 floating sell positions.

### Q: Machine gun cooldown — wait 8 min between bursts or continue immediately on strong move?
**A:** "on a strong move she continues the machine gun sometimes uptil 5"

**Key insight:**
- Burst max = **5** (not 3). Up to 5 trades back-to-back when momentum continues.
- NO fixed cooldown between bursts on strong moves.
- 7-8 min interval is the natural gap between FRESH setups (next big red), not an artificial timer.

### Q: Why did you cut the −$52, −$44, −$40 today instead of holding like the others?
**A:** "it was just fear, i took risk on some and couldnt on some, maybe they were larger lot size, so its my try to close at once because it can washout"

**Key insight:**
- The catastrophic cuts were **PANIC, NOT RULE**.
- She doesn't have a fixed loss threshold — it's emotional, often when lot size felt too risky.
- The system's robotic hold-until-reverse is *more disciplined than her own behavior*.
- Don't replicate panic cuts as code. Keep only the 50% capital catastrophic stop.

### Q: The system did −$30 floating → +$12.80 reversal in 4 min. Normal or unusually lucky?
**A:** "VERY NORMAL."

**Key insight:**
- Floating loss reversal is her bread and butter. Don't second-guess the EA when it's holding.
- Confirmed via her current open positions (was $-212 floating, ALL turned profit per her later answer).

### Q: Lot size — capital alone, or conviction-based?
**A:** "our lot size depends on Capital.. or to take more profit"

**Key insight:**
- Capital-driven base, conviction-driven upsize.
- EA's `InpMainLots=AUTO` (capital-based) is correct. Conviction-upsize is human judgment, hard to automate.

### Q: Trail close — $1, $2, $3 drop, or feel? Tick-by-tick or periodic?
**A:** "I LOOK AT EACH MILI SECOND, if it starts rolling down, i try to preserve the profit before it falls further, no its not fixed at 1,2,3 USD. its changing Very very fast at that moment"

**Key insight:**
- She watches **tick-by-tick (millisecond)**.
- Trail amount is NOT a fixed dollar drop — it's instinct ("rolling down").
- The EA's $2 fixed drop is an approximation. Could try $1.50 or even $1.00 for faster reaction in fast moves.
- True replication would need a velocity/derivative-based trigger (rate of profit change), not a fixed $ drop.

### Q: Plan for the 3 floating −$212 positions?
**A:** "THEY ALREADY TURNED INTO PROFIT, even after being in minus 100, we were showing u examples, u can see those candles using time of trade"

**Key insight:**
- −$100 floating reversals are routine.
- The previously-shown 3 floating losses (~$93, $66, $52) all recovered to profit — confirming hold rule is correct.
- We can verify this by checking MT5 history for those trade close prices.

### Q: 30 buys today — conscious green-candle setups, or reflexive panic flips?
**A:** "Yes ye reflexive thiy — sell loss me jaa rahi thi to panic me direction flip ki.. takay loss cover hota jaey"

**Key insight (CRITICAL):**
- Buys were **panic flips to cover losses**, not strategy.
- DO NOT enable buys in the system. Sell-only is the disciplined version of her method.
- This is the LESS profitable, less rational part of her trading. The system being sell-only outperforms her own bidirectional behavior on per-trade math (proven: SELL avg $2.13/trade vs BUY avg $0.99/trade on 2026-04-27).

### Q: Time-of-day rules?
**A:** "first 20 minutes after market open on Monday absolutely no trade, means until 3:20 AM pakistan time.. and before 2:00 AM pakistani time i dont trade at 1-2AM (1 hour before close) and at that time, IF IN CASE a position is open close it (but don't if its too much in minus, dont make so much loss by closing)"

**Key insights:**
- Pakistan timezone (UTC+5):
  - Monday market open: 3:00 AM PKT (= 22:00 UTC Sunday)
  - **Skip first 20 min**: no trade until 3:20 AM PKT
  - **Last hour buffer**: no NEW trades 1:00-2:00 AM PKT (1 hour before week close)
  - **In last hour**: close open positions IF in profit or small loss; HOLD if deeply in minus (don't realize big loss at week close)
- Maps to Pine inputs already (iSkipReopen=20, iStopBefore=60), but `iSessFilt` must be enabled to apply.
- Need session bounds: Monday 22:00 UTC → Friday 21:00 UTC (gold market week).

---

### Q: Lagatar 3-4 trades loss me jaen — kya karti hain?
**A:** "karti rehti hun jab tak capital recover na hojaey.. at day end there should be no loss, until then i trade like dheet ban jao"

**Key insight (CRITICAL):**
- She does NOT pause after losses. She trades **stubbornly ("dheet")** until capital recovers.
- **End-of-day = NO LOSS TOLERATED.** She'd rather over-trade than close the day red.
- This is a psychological recovery rule. Risky behavior — explains the −$52/−$44/−$40 panic cuts (chasing recovery with bigger lots).
- The system should NOT replicate this. Let the EA stop at session end with whatever P&L it has.

### Q: $500 daily cap — exactly what happens?
**A:** "mein ne 24 hours mein 500 bataya hai, kyunk aj market tough thi mein ne 200 bana kar rok dia tha keh kaheen ye bhi na loose kr du jo banaya hai. Wednesday is very profitable."

**Key insights:**
- $500 was a **24-hour figure**, not a strict per-day cap.
- On TOUGH market (like today 2026-04-27), she stops at much less ($200) to protect what's earned.
- **Wednesday is her highest-profit day.** Worth weighting expectations differently per day.
- Implication: daily cap should be DYNAMIC based on market conditions — not just a fixed $500. For now, keep $500 as ceiling but consider profit-protection cut at e.g. +$200 if subsequent trades start losing.

### Q: Probe — if profit oscillates 0.30 ↔ 0 without confirming or failing, how long do you wait?
**A:** "i wait 50 seconds, still if its in loss, close it, i close manually agar ni jari, -1 pe close karti hun, -3 pe bhi kar deti hun, kya hota hai, dobara profit ban jaeyga"

**Key insights:**
- **Probe timeout = 50 seconds** (not bar-based).
- If still in loss after 50s, close MANUALLY at −$1 or −$3 (her tolerance varies).
- Probe fail is not strict −$3 — could be −$1 if impatient.
- Pine `iProbeMaxB=2` (2 bars on 1m = ~120s) is too generous. **Should reduce to 1 bar (60s)** to match her 50s timeout.

### Q: Fear point on 0.40 main trade — at what floating $ does fear start?
**A:** "−60 pe, −92 pe fear max hota hai, kyunk ye bohot jaldi −135 pe chala jaeyga. Aaj aap ne −52 pe ek 0.40 cut ki thi (09:04 wali) — Kyunk tab zyada lots khuli v theen 3-4, to mein ne close kar dia fear mein keh ye to zada loss hojaeyga akatha. usually mein 0.4 wali −180 pe close kar deti hun kyunk else wo pura account wash kar degi. agar choti ho thori toh phir wo ahista ahista jati hai minus mein to hum wait kar saktay hain profit mein change karnay ka. 0.4 ki lot ko mein close kar deti hun meri jan nikal jati hai, issliay usspe hum wait forever ni kar saktay kyunk agar market kharab hoi toh? iss liay −70 pe ideal hota agar hum close kar detay 180 tak bhi na janay detay"

**Key insights (CRITICAL FOR EA TUNING):**
- **0.40 lot fear thresholds:**
  - Fear starts: **−$60**
  - Max fear: **−$92** (because price accelerates to −$135 quickly)
  - Hard close (washout prevention): **−$180** (her current de facto rule)
  - **IDEAL close (her own admission)**: **−$70** ← she'd rather follow this than wait until −$180
- **Smaller lots (0.10 etc.)**: can wait — they decrease slowly, easier to recover
- **0.40 lot is special** — she emotionally can't hold it forever. "Meri jaan nikal jati hai."
- **Close decision based on # of open lots simultaneously**: today's −$52 cut at 09:04 was because 3-4 lots were already open (compound risk).

### Q: When fear hits — close, hedge, or wait?
**A:** Implicit from above — she **closes** (no hedging). Buys-as-hedge were the panic flips earlier confirmed reflexive, not rule.

### Q: Lot-size threshold for "let it run" vs "close" (clarification follow-up)
**A:** "0.08 wali chalti rahay, 0.01 wali chalti rahay, 0.1 wali bhi chalti rahay, 0.1 se upar wali ko close kar dena behtar hai"

**Key insight (CRITICAL FOR EA LOGIC):**
- **Hold-forever lots:** 0.01, 0.08, 0.10 — let them run regardless of floating loss
- **Close-on-fear lots:** anything **above 0.10** (so 0.20, 0.30, 0.40) — close when fear thresholds hit
- This is a discrete cutoff, not a sliding scale.
- **EA implementation:** branching catastrophic stop logic by lot size:
  - if `lot <= 0.10` → no fear-based close, hold until reverse
  - if `lot > 0.10` → apply fear thresholds:
    - −$60 = soft warn
    - −$70 = ideal close (her preferred)
    - −$180 = hard washout-prevention close
- Combined with capital→lot scaling: tiny accounts (capital <$300) only use ≤0.06 lots, so they automatically benefit from hold-forever rule. Bigger accounts using 0.20+ get fear-based exits.

---

### Q: Wednesday kyun zyada profitable hai?
**A:** "apni observation hai. selling k liay wednesday ki market achi hoti hai. abi mein ye apko isska answer kal soch kar batau gi yad ni ara"

**Key insight:**
- Wednesday is empirically her best day for SELL setups (her observation, not statistically explained yet).
- She'll think and follow up tomorrow.
- TODO: pull historical data to correlate her per-day P&L and verify Wednesday outperformance.

### Q: "Tough market" kaisay identify karti hain?
**A:** "Direction quickly flip ho rahi — minus se plus anay mein ussn 2 2 hours laga diay usually 15 minute mein wapis ajati hai +10 pe"

**Key insight (CRITICAL — concrete signal):**
- **Normal market:** floating loss reverses to +$10 within ~15 minutes
- **Tough market:** same reversal takes 2+ hours
- This is a **time-to-recovery** metric. Codifiable:
  - Track: per trade, time from entering loss territory to first +$10 in profit
  - If avg time-to-recover > 60 min over last N trades → flag market as "tough"
  - When tough → cap daily profit at +$200 (today's pattern), reduce lot size, or pause new probes
- Direction flipping (sell wins → buy wins → sell wins) is the manifestation she watches for.

### Q: Multiple lots open — close order?
**A:** "IN ANY CASE SABSE BARA LOT SIZE PEHLAY CLOSE HOGA. Profit mein bhi sabse pehlay wohi close hota hai matlab largest lot size"

**Key insight:**
- **ALWAYS close largest lot first** — whether in loss or profit.
- Reason (implicit): largest lot has highest risk/reward, must be locked in or cut first.
- EA implementation: when multiple positions need closing, sort by lot size DESC, close largest first.

### Q: News events — CPI/NFP/FOMC?
**A:** "I DONT WATCH NEWS AT ALL, I DONT WATCH FOREX FACTORY AT ALL"

**Key insight:**
- No news filter in her method.
- Don't add news/economic calendar filtering to EA — it's not part of her strategy.
- (Note: this MAY be a gap in her method, but we should match her actual behavior, not "improve" it without her input.)

---

## Updated Strategy Summary (Session 3 corrections)

Changes from prior summary:
| Rule | Before | After (Session 3) |
|------|--------|--------|
| Burst max | 3-5 | **5** (no longer "rare") |
| Burst cooldown | 480s artificial | **0** — wait for natural new probe |
| Trail trigger | $2 fixed drop | **Tick-watch + rolling-down detection** (approximated by $1-$2 drop) |
| Catastrophic loss cut | At 50% capital | Keep — but the smaller cuts were emotional, NOT rule |
| Direction filter | "Sell only — buys not from strategy" | **CONFIRMED sell-only** — buys were panic loss-cover |
| Time filter | Anytime | **Skip first 20 min Mon open + 1 hr before week close** |

