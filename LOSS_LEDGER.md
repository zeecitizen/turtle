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
