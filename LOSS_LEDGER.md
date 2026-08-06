# 🩸 LOSS LEDGER — every loss explained, or flagged

One entry per losing trade, written automatically by monitor/loss_ledger.py.
KNOWN SPECIES = a shipped fix covers this pattern (the loss is residue or toll).
NEW SPECIES ⚠ = unexplained — Claude investigates before anything else is built.

---

## 2026.08.04 22:13:16 (broker) — BUY 0.10 · **-13.80** (-1.38pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785870731 BUY lamp 4084.26 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit with 0.38pt SLIPPAGE beyond design (fast tape/thin book)
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- bar context no longer in the rolling OANDA window — partial autopsy

---

## 2026.08.04 22:20:35 (broker) — BUY 0.30 · **-30.00** (-1.00pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785870923 BUY raid 2/3 lamp 4083.88 lots=0.30 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.00pt vs 1.0 cap) — bounded toll
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- repeat raid — must have followed a WINNING raid (v1.62) and a lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG
- burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — cured by RISK_CAP 0.10
- bar context no longer in the rolling OANDA window — partial autopsy

---

## 2026.08.04 22:32:05 (broker) — BUY 0.10 · **-11.10** (-1.11pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785871864 BUY raid 1/1 lamp 4080.39 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.11pt vs 1.0 cap) — bounded toll
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- bar context no longer in the rolling OANDA window — partial autopsy

---

## 2026.08.04 22:47:07 (broker) — BUY 0.30 · **-30.00** (-1.00pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785872711 BUY raid 1/3 lamp 4082.15 lots=0.30 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.00pt vs 1.0 cap) — bounded toll
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — cured by RISK_CAP 0.10
- bar context no longer in the rolling OANDA window — partial autopsy

---

## 2026.08.04 23:11:29 (broker) — SELL 0.10 · **-11.40** (-1.14pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785874277 SELL raid 1/6 lamp 4078.90 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.14pt vs 1.0 cap) — bounded toll
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- bar context no longer in the rolling OANDA window — partial autopsy

---

## 2026.08.04 23:13:39 (broker) — SELL 0.60 · **-32.40** (-0.54pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785874277 SELL raid 2/6 lamp 4078.90 lots=0.60 chase=1.0 ghost=0.50pt`
- ghost exit at design distance (-0.54pt vs 0.5 cap) — bounded toll
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- repeat raid — must have followed a WINNING raid (v1.62) and a lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG
- burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — cured by RISK_CAP 0.10
- bar context no longer in the rolling OANDA window — partial autopsy

---

## 2026.08.04 23:52:40 (broker) — BUY 0.30 · **-37.50** (-1.25pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785876374 BUY raid 1/6 lamp 4077.70 lots=0.30 chase=1.0 ghost=1.00pt`
- ghost exit with 0.25pt SLIPPAGE beyond design (fast tape/thin book)
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — cured by RISK_CAP 0.10
- bar context no longer in the rolling OANDA window — partial autopsy

---

## 2026.08.05 01:24:59 (broker) — SELL 0.10 · **-16.10** (-1.61pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785882189 SELL raid 1/6 lamp 4076.38 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.61pt SLIPPAGE beyond design (fast tape/thin book)
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- bar context no longer in the rolling OANDA window — partial autopsy

---

## 2026.08.05 08:03:40 (broker) — SELL 0.10 · **-12.30** (-1.23pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785906189 SELL raid 1/1 lamp 4135.44 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.23pt SLIPPAGE beyond design (fast tape/thin book)
- slope -0.02 aligned; AUTO said RANGE — entry direction was legitimate

---

## 2026.08.05 08:18:46 (broker) — BUY 0.10 · **-10.30** (-1.03pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785907036 BUY raid 1/6 lamp 4137.46 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.03pt vs 1.0 cap) — bounded toll
- slope +0.13 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 08:30:12 (broker) — BUY 0.10 · **-10.50** (-1.05pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785907808 BUY lots=0.10 ghost=1.00pt stackable parachute=4141.28`
- ghost exit at design distance (-1.05pt vs 1.0 cap) — bounded toll
- slope +0.16 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 08:52:15 (broker) — BUY 0.10 · **-9.60** (-0.96pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785909131 BUY lots=0.10 ghost=1.00pt stackable parachute=4169.42`
- ghost exit at design distance (-0.96pt vs 1.0 cap) — bounded toll
- slope +1.16 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 09:37:11 (broker) — BUY 0.10 · **-10.50** (-1.05pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785911712 BUY lots=0.10 ghost=1.00pt stackable parachute=4175.03`
- ghost exit at design distance (-1.05pt vs 1.0 cap) — bounded toll
- slope +0.07 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 10:00:14 (broker) — BUY 0.10 · **-12.10** (-1.21pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785913206 BUY raid 1/1 lamp 4178.49 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.21pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.15 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 11:40:51 (broker) — SELL 0.10 · **-9.40** (-0.94pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785919037 SELL raid 2/6 lamp 4164.27 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.94pt vs 1.0 cap) — bounded toll
- repeat raid — must have followed a WINNING raid (v1.62) and a lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG
- slope -0.12 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.05 11:46:11 (broker) — SELL 0.10 · **-9.90** (-0.99pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785919538 SELL lots=0.10 ghost=1.00pt stackable parachute=4166.40`
- ghost exit at design distance (-0.99pt vs 1.0 cap) — bounded toll
- slope -0.04 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.05 12:02:55 (broker) — SELL 0.10 · **-10.10** (-1.01pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785920526 SELL raid 1/1 lamp 4162.40 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.01pt vs 1.0 cap) — bounded toll
- slope -0.16 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.05 14:47:16 (broker) — BUY 0.10 · **-13.90** (-1.39pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1785930429 BUY lots=0.10 ghost=1.00pt stackable parachute=4182.47`
- ghost exit with 0.39pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.66 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 15:04:44 (broker) — BUY 0.10 · **-13.30** (-1.33pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1785931468 BUY lots=0.10 ghost=1.00pt stackable parachute=4192.10`
- ghost exit with 0.33pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.30 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 15:15:25 (broker) — BUY 0.10 · **-1.90** (-0.19pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785931468 BUY lots=0.10 ghost=1.00pt stackable parachute=4192.10`
- ghost exit at design distance (-0.19pt vs 1.0 cap) — bounded toll
- slope +0.53 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 15:15:28 (broker) — BUY 0.10 · **-9.30** (-0.93pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785931468 BUY lots=0.10 ghost=1.00pt stackable parachute=4192.10`
- ghost exit at design distance (-0.93pt vs 1.0 cap) — bounded toll
- slope +0.53 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 15:36:02 (broker) — BUY 0.10 · **-11.20** (-1.12pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785933344 BUY lots=0.10 ghost=1.00pt stackable parachute=4198.03`
- ghost exit at design distance (-1.12pt vs 1.0 cap) — bounded toll
- slope +0.16 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 15:52:17 (broker) — SELL 0.10 · **-7.40** (-0.74pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785934262 SELL raid 1/6 lamp 4191.06 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.74pt vs 1.0 cap) — bounded toll
- slope -0.69 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.05 17:57:47 (broker) — BUY 0.30 · **-30.90** (-1.03pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785853899 BUY lamp 4083.91 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.03pt vs 1.0 cap) — bounded toll
- slope +0.30 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 18:19:27 (broker) — BUY 0.10 · **-9.90** (-0.99pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785943155 BUY raid 1/1 lamp 4254.55 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.99pt vs 1.0 cap) — bounded toll
- slope +0.71 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 18:40:35 (broker) — SELL 0.10 · **-9.90** (-0.99pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785944409 SELL raid 1/1 lamp 4256.13 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.99pt vs 1.0 cap) — bounded toll
- slope -0.03 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.05 19:35:21 (broker) — BUY 0.10 · **-0.40** (-0.04pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785947542 BUY raid 1/3 lamp 4241.03 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.04pt vs 1.0 cap) — bounded toll
- slope +0.33 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 20:49:35 (broker) — BUY 0.10 · **-15.80** (-1.58pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785951738 BUY raid 1/6 lamp 4250.61 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.58pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.45 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 20:57:40 (broker) — BUY 0.10 · **-11.70** (-1.17pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1785952628 BUY lots=0.10 ghost=1.00pt stackable parachute=4249.37`
- ghost exit with 0.17pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.22 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.05 21:53:33 (broker) — BUY 0.60 · **-39.00** (-0.65pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785956003 BUY raid 1/6 lamp 4262.31 lots=0.60 chase=3.0 ghost=0.50pt`
- ghost exit at design distance (-0.65pt vs 0.5 cap) — bounded toll
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — cured by RISK_CAP 0.10
- slope -0.05 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.05 22:07:42 (broker) — SELL 0.30 · **-30.30** (-1.01pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1785956847 SELL lots=0.30 ghost=1.00pt stackable parachute=4262.31`
- ghost exit at design distance (-1.01pt vs 1.0 cap) — bounded toll
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — cured by RISK_CAP 0.10
- slope +0.09 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 01:11:34 (broker) — BUY 0.30 · **-29.10** (-0.97pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785967815 BUY raid 1/6 lamp 4248.19 lots=0.30 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.97pt vs 1.0 cap) — bounded toll
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — cured by RISK_CAP 0.10
- slope +0.07 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 01:30:05 (broker) — BUY 0.30 · **-12.90** (-0.43pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785968830 BUY raid 1/6 lamp 4248.44 lots=0.30 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.43pt vs 1.0 cap) — bounded toll
- night window (22:00-01:00 broker): chop + 2-6x slippage era — hour study says the edge lives elsewhere
- burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — cured by RISK_CAP 0.10
- slope +0.03 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 02:39:58 (broker) — BUY 0.10 · **-13.60** (-1.36pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1785972904 BUY lots=0.10 ghost=1.00pt stackable parachute=4262.65`
- ghost exit with 0.36pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.71 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 02:40:55 (broker) — BUY 0.10 · **-2.50** (-0.25pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785973145 BUY raid 1/1 lamp 4279.94 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit at design distance (-0.25pt vs 1.0 cap) — bounded toll
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope +0.75 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 02:41:14 (broker) — BUY 0.10 · **-20.20** (-2.02pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785973229 BUY raid 2/3 lamp 4279.94 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit with 1.02pt SLIPPAGE beyond design (fast tape/thin book)
- repeat raid — must have followed a WINNING raid (v1.62) and a lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope +0.77 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 02:44:14 (broker) — BUY 0.10 · **-10.70** (-1.07pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785973385 BUY lots=0.10 ghost=1.00pt stackable parachute=4278.58`
- ghost exit at design distance (-1.07pt vs 1.0 cap) — bounded toll
- slope +0.88 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 02:49:50 (broker) — BUY 0.10 · **-9.30** (-0.93pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785973385 BUY lots=0.10 ghost=1.00pt stackable parachute=4278.58`
- ghost exit at design distance (-0.93pt vs 1.0 cap) — bounded toll
- slope +0.79 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 02:52:25 (broker) — BUY 0.10 · **-0.40** (-0.04pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785973937 BUY lots=0.10 ghost=1.00pt stackable parachute=4273.40`
- ghost exit at design distance (-0.04pt vs 1.0 cap) — bounded toll
- slope +0.67 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 03:19:56 (broker) — SELL 0.10 · **-14.90** (-1.49pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1785975555 SELL lots=0.10 ghost=1.00pt stackable parachute=4276.19`
- ghost exit with 0.49pt SLIPPAGE beyond design (fast tape/thin book)
- slope -0.17 aligned; AUTO said RANGE — entry direction was legitimate

---

## 2026.08.06 03:21:30 (broker) — SELL 0.10 · **-23.70** (-2.37pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785975676 SELL raid 1/1 lamp 4274.53 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 1.37pt SLIPPAGE beyond design (fast tape/thin book)
- slope -0.07 aligned; AUTO said RANGE — entry direction was legitimate

---

## 2026.08.06 03:48:01 (broker) — BUY 0.10 · **-10.70** (-1.07pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785976444 BUY lots=0.10 ghost=1.00pt stackable parachute=4282.77`
- ghost exit at design distance (-1.07pt vs 1.0 cap) — bounded toll
- slope +0.52 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 03:51:34 (broker) — BUY 0.10 · **-33.50** (-3.35pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1785977460 BUY lots=0.10 ghost=1.00pt stackable parachute=4291.39`
- ghost exit with 2.35pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.50 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 04:01:49 (broker) — BUY 0.10 · **-5.00** (-0.50pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785977580 BUY raid 1/6 lamp 4295.23 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit at design distance (-0.50pt vs 1.0 cap) — bounded toll
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope +0.53 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 04:29:10 (broker) — SELL 0.10 · **-15.50** (-1.55pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785979746 SELL raid 1/6 lamp 4274.25 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.55pt SLIPPAGE beyond design (fast tape/thin book)
- slope -0.73 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 04:49:20 (broker) — BUY 0.10 · **-1.20** (-0.12pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785980952 BUY lots=0.10 ghost=1.00pt stackable parachute=4291.53`
- ghost exit at design distance (-0.12pt vs 1.0 cap) — bounded toll
- slope +0.53 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 05:05:27 (broker) — BUY 0.10 · **-9.80** (-0.98pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785981917 BUY lots=0.10 ghost=1.00pt stackable parachute=4295.89`
- ghost exit at design distance (-0.98pt vs 1.0 cap) — bounded toll
- slope +0.12 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 05:17:42 (broker) — BUY 0.10 · **-11.60** (-1.16pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785982399 BUY raid 1/1 lamp 4300.02 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit with 0.16pt SLIPPAGE beyond design (fast tape/thin book)
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope +0.32 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 05:32:19 (broker) — SELL 0.10 · **-11.70** (-1.17pt) — **KNOWN SPECIES**

- ghost exit with 0.17pt SLIPPAGE beyond design (fast tape/thin book)
- slope -0.43 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 05:33:05 (broker) — SELL 0.10 · **-10.10** (-1.01pt) — **DESIGN TOLL**

- ghost exit at design distance (-1.01pt vs 1.0 cap) — bounded toll
- slope -0.43 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 05:40:42 (broker) — SELL 0.10 · **-10.20** (-1.02pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785983581 SELL lots=0.10 ghost=1.00pt stackable parachute=4286.89`
- ghost exit at design distance (-1.02pt vs 1.0 cap) — bounded toll
- slope -0.52 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 05:46:47 (broker) — SELL 0.10 · **-12.00** (-1.20pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1785984063 SELL lots=0.10 ghost=1.00pt stackable parachute=4284.69`
- ghost exit with 0.20pt SLIPPAGE beyond design (fast tape/thin book)
- slope -0.54 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 07:09:43 (broker) — BUY 0.10 · **-10.00** (-1.00pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785988956 BUY raid 1/6 lamp 4266.73 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit at design distance (-1.00pt vs 1.0 cap) — bounded toll
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope +0.11 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 07:09:46 (broker) — BUY 0.10 · **-10.30** (-1.03pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785988956 BUY raid 1/6 lamp 4266.73 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit at design distance (-1.03pt vs 1.0 cap) — bounded toll
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope +0.11 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 07:10:45 (broker) — BUY 0.10 · **-10.80** (-1.08pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785988956 BUY raid 2/3 lamp 4266.73 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.08pt vs 1.0 cap) — bounded toll
- repeat raid — must have followed a WINNING raid (v1.62) and a lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG
- slope +0.12 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 07:10:45 (broker) — BUY 0.10 · **-9.30** (-0.93pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785988956 BUY raid 2/3 lamp 4266.73 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.93pt vs 1.0 cap) — bounded toll
- repeat raid — must have followed a WINNING raid (v1.62) and a lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG
- slope +0.12 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 07:23:54 (broker) — SELL 0.10 · **-12.50** (-1.25pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1785990189 SELL raid 1/1 lamp 4262.11 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.25pt SLIPPAGE beyond design (fast tape/thin book)
- slope -0.08 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 07:55:18 (broker) — BUY 0.10 · **-8.90** (-0.89pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785992065 BUY raid 1/1 lamp 4261.31 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.89pt vs 1.0 cap) — bounded toll
- slope +0.12 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 08:02:27 (broker) — BUY 0.10 · **-10.80** (-1.08pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785992523 BUY raid 1/1 lamp 4263.30 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.08pt vs 1.0 cap) — bounded toll
- slope +0.15 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 08:34:47 (broker) — SELL 0.10 · **-6.40** (-0.64pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785994485 SELL lots=0.10 ghost=1.00pt stackable parachute=4259.27`
- ghost exit at design distance (-0.64pt vs 1.0 cap) — bounded toll
- slope -0.30 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 08:58:54 (broker) — BUY 0.10 · **-10.50** (-1.05pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785995778 BUY raid 1/6 lamp 4267.06 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.05pt vs 1.0 cap) — bounded toll
- slope +0.52 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 09:06:58 (broker) — BUY 0.10 · **-10.50** (-1.05pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785996069 BUY raid 1/3 lamp 4267.75 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.05pt vs 1.0 cap) — bounded toll
- slope +0.21 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 09:32:13 (broker) — SELL 0.10 · **-9.90** (-0.99pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785997272 SELL raid 1/6 lamp 4254.74 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.99pt vs 1.0 cap) — bounded toll
- slope -0.41 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 09:32:14 (broker) — SELL 0.10 · **-9.40** (-0.94pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785997272 SELL raid 1/6 lamp 4254.74 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.94pt vs 1.0 cap) — bounded toll
- slope -0.41 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 09:32:17 (broker) — SELL 0.10 · **-10.20** (-1.02pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1785997272 SELL raid 1/6 lamp 4254.74 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.02pt vs 1.0 cap) — bounded toll
- slope -0.40 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 10:20:10 (broker) — BUY 0.10 · **-11.30** (-1.13pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786000781 BUY raid 1/6 lamp 4263.31 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.13pt vs 1.0 cap) — bounded toll
- slope +0.44 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 10:20:29 (broker) — BUY 0.10 · **-10.80** (-1.08pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786000781 BUY raid 1/6 lamp 4263.31 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.08pt vs 1.0 cap) — bounded toll
- slope +0.42 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 10:20:30 (broker) — BUY 0.10 · **-11.20** (-1.12pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786000781 BUY raid 1/6 lamp 4263.31 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.12pt vs 1.0 cap) — bounded toll
- slope +0.42 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 10:51:32 (broker) — SELL 0.10 · **-10.40** (-1.04pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786002662 SELL lots=0.10 ghost=1.00pt stackable parachute=4257.82`
- ghost exit at design distance (-1.04pt vs 1.0 cap) — bounded toll
- slope -0.29 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 10:52:55 (broker) — SELL 0.10 · **-10.30** (-1.03pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786002742 SELL raid 1/1 lamp 4254.43 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.03pt vs 1.0 cap) — bounded toll
- slope -0.31 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 11:19:31 (broker) — BUY 0.10 · **-0.30** (-0.03pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786004285 BUY raid 1/3 lamp 4270.07 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.03pt vs 1.0 cap) — bounded toll
- slope +0.49 aligned; AUTO said RANGE — entry direction was legitimate

---

## 2026.08.06 11:20:14 (broker) — BUY 0.10 · **-17.20** (-1.72pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1786004380 BUY lots=0.10 ghost=1.00pt stackable parachute=4266.61`
- ghost exit with 0.72pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.47 aligned; AUTO said RANGE — entry direction was legitimate

---

## 2026.08.06 11:25:13 (broker) — BUY 0.10 · **-10.40** (-1.04pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786004696 BUY lots=0.10 ghost=1.00pt stackable parachute=4263.25`
- ghost exit at design distance (-1.04pt vs 1.0 cap) — bounded toll
- slope +0.29 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 11:33:45 (broker) — BUY 0.10 · **-10.50** (-1.05pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1786005202 BUY raid 1/3 lamp 4273.82 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit at design distance (-1.05pt vs 1.0 cap) — bounded toll
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope +0.23 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 11:36:27 (broker) — BUY 0.10 · **-10.50** (-1.05pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786005322 BUY lots=0.10 ghost=1.00pt stackable parachute=4271.61`
- ghost exit at design distance (-1.05pt vs 1.0 cap) — bounded toll
- slope +0.25 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 11:40:50 (broker) — BUY 0.10 · **-12.00** (-1.20pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] signal #1786005322 BUY lots=0.10 ghost=1.00pt stackable parachute=4271.61`
- ghost exit with 0.20pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.21 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 11:50:42 (broker) — BUY 0.10 · **-8.50** (-0.85pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786006139 BUY raid 1/6 lamp 4274.79 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.85pt vs 1.0 cap) — bounded toll
- slope +0.28 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 11:50:50 (broker) — BUY 0.10 · **-10.50** (-1.05pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786006139 BUY raid 1/6 lamp 4274.79 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.05pt vs 1.0 cap) — bounded toll
- slope +0.28 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 11:50:58 (broker) — BUY 0.10 · **-10.90** (-1.09pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786006139 BUY raid 1/6 lamp 4274.79 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.09pt vs 1.0 cap) — bounded toll
- slope +0.28 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 12:55:11 (broker) — SELL 0.10 · **-8.50** (-0.85pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786009271 SELL lots=0.10 ghost=1.00pt stackable parachute=4278.58`
- ghost exit at design distance (-0.85pt vs 1.0 cap) — bounded toll
- slope -0.33 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 12:55:18 (broker) — SELL 0.10 · **-10.00** (-1.00pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786009948 SELL raid 1/6 lamp 4271.96 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.00pt vs 1.0 cap) — bounded toll
- slope -0.33 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 12:55:25 (broker) — SELL 0.10 · **-9.60** (-0.96pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786009948 SELL raid 1/6 lamp 4271.96 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.96pt vs 1.0 cap) — bounded toll
- slope -0.33 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 12:55:26 (broker) — SELL 0.10 · **-10.30** (-1.03pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786009948 SELL raid 1/6 lamp 4271.96 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.03pt vs 1.0 cap) — bounded toll
- slope -0.33 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 12:55:26 (broker) — SELL 0.10 · **-10.20** (-1.02pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786009948 SELL raid 1/6 lamp 4271.96 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.02pt vs 1.0 cap) — bounded toll
- slope -0.33 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 12:55:27 (broker) — SELL 0.10 · **-10.40** (-1.04pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786009948 SELL raid 1/6 lamp 4271.96 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.04pt vs 1.0 cap) — bounded toll
- slope -0.33 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 13:01:37 (broker) — SELL 0.10 · **-9.50** (-0.95pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786010479 SELL lots=0.10 ghost=1.00pt stackable parachute=4273.80`
- ghost exit at design distance (-0.95pt vs 1.0 cap) — bounded toll
- slope -0.24 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 13:04:30 (broker) — SELL 0.10 · **-9.70** (-0.97pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786010624 SELL raid 2/6 lamp 4271.58 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.97pt vs 1.0 cap) — bounded toll
- repeat raid — must have followed a WINNING raid (v1.62) and a lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG
- slope -0.20 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 13:12:34 (broker) — SELL 0.10 · **-12.50** (-1.25pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1786011127 SELL raid 1/1 lamp 4268.90 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.25pt SLIPPAGE beyond design (fast tape/thin book)
- slope -0.18 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 13:21:49 (broker) — SELL 0.10 · **-7.80** (-0.78pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786011685 SELL raid 1/1 lamp 4268.16 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.78pt vs 1.0 cap) — bounded toll
- slope -0.18 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 13:23:47 (broker) — SELL 0.10 · **-9.50** (-0.95pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786011805 SELL lots=0.10 ghost=1.00pt stackable parachute=4271.06`
- ghost exit at design distance (-0.95pt vs 1.0 cap) — bounded toll
- slope -0.16 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 13:58:45 (broker) — BUY 0.10 · **-9.90** (-0.99pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786013859 BUY raid 1/3 lamp 4271.17 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.99pt vs 1.0 cap) — bounded toll
- slope +0.07 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 14:03:26 (broker) — BUY 0.10 · **-10.40** (-1.04pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1786014140 BUY raid 1/1 lamp 4273.12 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit at design distance (-1.04pt vs 1.0 cap) — bounded toll
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope +0.17 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 14:18:56 (broker) — SELL 0.10 · **-0.10** (-0.01pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786014743 SELL raid 1/6 lamp 4266.68 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.01pt vs 1.0 cap) — bounded toll
- slope -0.09 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 14:41:26 (broker) — SELL 0.10 · **-0.70** (-0.07pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1786015513 SELL raid 1/6 lamp 4260.35 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit at design distance (-0.07pt vs 1.0 cap) — bounded toll
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope -0.21 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 14:44:05 (broker) — SELL 0.10 · **-10.10** (-1.01pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #1786015513 SELL raid 2/6 lamp 4260.35 lots=0.10 chase=3.0 ghost=1.00pt`
- ghost exit at design distance (-1.01pt vs 1.0 cap) — bounded toll
- repeat raid — must have followed a WINNING raid (v1.62) and a lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG
- dying-lamp chase entry — stretched-run risk (stretch-guard not yet shipped; candidate fix on 2+ receipts)
- slope -0.21 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 15:10:25 (broker) — BUY 0.10 · **-10.80** (-1.08pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #1786018214 BUY raid 1/1 lamp 4259.51 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.08pt vs 1.0 cap) — bounded toll
- slope +0.11 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 16:05:44 (broker) — SELL 0.10 · **-11.10** (-1.11pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1785934383 SELL lots=0.10 ghost=1.00pt stackable parachute=4192.53`
- ghost exit at design distance (-1.11pt vs 1.0 cap) — bounded toll
- slope -0.82 aligned; AUTO said DOWNTREND — entry direction was legitimate

---

## 2026.08.06 17:08:01 (broker) — BUY 0.10 · **-9.50** (-0.95pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786023641 BUY lots=0.10 ghost=1.00pt stackable parachute=4261.93`
- ghost exit at design distance (-0.95pt vs 1.0 cap) — bounded toll
- slope +0.07 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 17:11:47 (broker) — BUY 0.10 · **-10.60** (-1.06pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786025498 BUY lots=0.10 ghost=1.00pt stackable parachute=4271.98`
- ghost exit at design distance (-1.06pt vs 1.0 cap) — bounded toll
- slope +0.01 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 17:19:26 (broker) — BUY 0.10 · **-10.20** (-1.02pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #-1962809378 BUY raid 1/3 lamp 4266.23 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-1.02pt vs 1.0 cap) — bounded toll
- slope +0.02 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 17:19:27 (broker) — BUY 0.10 · **-11.60** (-1.16pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #-1962809378 BUY raid 1/3 lamp 4266.23 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.16pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.02 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 17:43:58 (broker) — BUY 0.10 · **-8.60** (-0.86pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] GHOST-DOOR #-1624780216 BUY raid 1/3 lamp 4274.74 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit at design distance (-0.86pt vs 1.0 cap) — bounded toll
- slope +0.38 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 17:43:58 (broker) — BUY 0.10 · **-11.60** (-1.16pt) — **KNOWN SPECIES**

- EA fire: `[CaseExec] GHOST-DOOR #-1624780216 BUY raid 1/3 lamp 4274.74 lots=0.10 chase=1.0 ghost=1.00pt`
- ghost exit with 0.16pt SLIPPAGE beyond design (fast tape/thin book)
- slope +0.38 aligned; AUTO said UPTREND — entry direction was legitimate

---

## 2026.08.06 18:33:37 (broker) — SELL 0.10 · **-1.40** (-0.14pt) — **DESIGN TOLL**

- EA fire: `[CaseExec] signal #1786030408 SELL lots=0.10 ghost=1.00pt stackable parachute=4256.31`
- ghost exit at design distance (-0.14pt vs 1.0 cap) — bounded toll
- slope -0.65 aligned; AUTO said DOWNTREND — entry direction was legitimate
