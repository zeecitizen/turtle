# START HERE ON THE NEW LAPTOP

**Written 2026-10-07 for Claude, on the machine being migrated FROM.**
Read this before touching anything. It is the setup checklist; `RESUME_HERE_2026-10-07.md` is
the project state. Do this one first.

---

## 0. THE TWO THINGS THAT DO NOT TRAVEL WITH GIT

If these were missed on the old machine, they are gone. Check them before anything else.

### a) The push may never have happened

The old session **could not push** — the sandbox blocked it as a data-exfiltration risk. Zee
was asked to run it by hand:

```bash
cd <repo>
git push -u origin feature/optimise-for-expectancy
```

**104 commits were unpushed at handover time.** On the new laptop:

```bash
git log --oneline -3
```

Expect to see `ce014474 📦 Save everything else before the laptop move` and
`04a1e406 🛡️ RiskGuardButtons v1.14 + TickSpeedGauge v1.53`.
**If those are missing, the clone predates the handover — stop and tell Zee the push never
landed.** Everything below assumes they are present.

### b) The memory folder is NOT in the repo

```
OLD:  C:\Users\zeesh\.claude\projects\c--Users-zeesh-Documents-GitHub-turtle\memory\
NEW:  C:\Users\<user>\.claude\projects\c--Users-<user>-Documents-GitHub-turtle\memory\
```

The folder name encodes the repo path, so **it changes if the username or repo location
changes.** It holds `MEMORY.md` plus ~60 memory files and `memory_soul.md.enc`.

If the folder is empty or missing, say so immediately rather than working without it — it
contains Zee's verbatim words, the laws, and the doctrine that stops old mistakes repeating.

---

## 1. SECRETS — gitignored, so none of them transferred

All of these are in `.gitignore` and must be recreated. Nothing that reads them will work until
they exist:

```
monitor/.claude_api_key          monitor/.openai_api_key
monitor/.whatsapp_config.json    monitor/.dashboard_password
monitor/.tv_credentials.json     monitor/.brain_key
monitor/.claude_brain.db         (encrypted bundle IS in brain_vault/ — restore from there)
```

**None of these are needed for the two EAs below.** They matter for the dashboard, WhatsApp
reporting and the hawk daemons. Do not block the trading work on them.

---

## 2. PYTHON

Old machine ran **two** interpreters. `py` resolved to 3.14.4; `CLAUDE.md` names an ARM64 3.13
at `C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe`.

Everything in this repo was run with plain **`py`**. Use that. Check:

```bash
py -V
py -c "import csv, statistics; print('ok')"
```

The analysis scripts use only the standard library — no pip installs required.

---

## 3. MT5 TERMINALS — the thing that always breaks first

**Every terminal GUID will be different on a new machine.** `monitor/deploy_ea.py` maps a name
to a data folder and a MetaEditor path, and all six values are machine-specific.

Old values, for shape only — **do not reuse them**:

| name | data folder GUID | MetaEditor |
|---|---|---|
| `blueberry` | `DBE9B8B347D025DD139E103EE3B63FD8` | `C:/Program Files/Blueberry Markets MetaTrader 5/metaeditor64.exe` |
| `pxbt` | `BCB580088311575081ABF4FB040CCFF8` | `C:/Program Files/PXBT Trading MT5 Terminal/MetaEditor64.exe` |
| `exness` | `53785E099C927DB68A545C249CDBCE06` | `C:/Program Files/MetaTrader 5 EXNESS/MetaEditor64.exe` |

**⚠ The editor filename differs by broker.** `MetaEditor64.exe` with capitals on PXBT and
Exness; lowercase `metaeditor64.exe` on Blueberry. Windows is case-insensitive so this is
invisible locally and then fails elsewhere — copy the exact name off disk, do not type it.

### Finding the new GUIDs

In each terminal: **File → Open Data Folder**. The path ends in the GUID. Or:

```bash
ls "/c/Users/<user>/AppData/Roaming/MetaQuotes/Terminal/" | grep -E '^[0-9A-F]{32}$'
```

Identify which is which by looking for the broker's name inside
`<GUID>/MQL5/Profiles/` or by checking `origin.txt` / the logs folder.

Then edit `TERMINALS{}` in `monitor/deploy_ea.py` (near line 31) and verify:

```bash
py monitor/deploy_ea.py --terminal pxbt TickSpeedGauge
```

A wrong path fails loudly with `MetaEditor missing for 'pxbt' at ...` — that check already
exists, so a bad edit cannot pass silently.

---

## 4. DEPLOY THE TWO EAs

```bash
py monitor/deploy_ea.py --terminal pxbt RiskGuardButtons
py monitor/deploy_ea.py --terminal pxbt TickSpeedGauge
```

Expect `OK — 0 errors, 0 warnings` on both. Repeat per terminal as needed.

| EA | role |
|---|---|
| `RiskGuardButtons` v1.14 | **the live one.** Manual buttons, risk enforced in code |
| `TickSpeedGauge` v1.53 | **research only, never trades.** Keep it attached to keep logging |

---

## 5. FIRST-RUN CHECK — do not skip this

Attach `RiskGuardButtons` to **PXBT `XAUUSDp`** and read the Experts tab. It must say:

```
[RG] XAUUSDp: 1 pip = 0.10000 in price (2 digits, point 0.01000). Spread 0.17 = 1.7 pips.
[RG] stop 5.0 pips = 0.50 in PRICE   target 30.0 pips = 3.00   breakeven 19.1%
```

**If `1 pip` is not `0.10000` on gold, STOP.** That was a real bug: `PipSize()` returned the
point (0.01) instead of gold's 0.10 pip, making every pip input ten times too small — a 5-pip
stop landed 0.05 from entry against a 0.17 spread, i.e. **inside** it. Scalp mode bypasses the
noise floor, so nothing downstream catches it. Every trade would stop out instantly.

It is fixed, but a new broker or a different gold symbol could present different digits.
**`InpPipOverride` sets the pip in price if auto-detection is ever wrong.**

Second check — the panel should be readable. It derives text colour from
`CHART_COLOR_BACKGROUND`, so it works on a white or dark chart. Six separate label objects,
because `OBJ_LABEL` ignores `\n`.

---

## 6. THE DATA

`data/tickspeed_logs/*.csv.gz` — 34 MB gzipped to 6 MB. **This is the only copy**; the
originals are in MT5's `Common\Files`, which does not move.

To analyse, gunzip into a working folder — do **not** put them back into `Common\Files`, where
a running EA would append to them and mix schemas.

```bash
py monitor/strategy_lab/tickspeed_calibrate.py <path to a .csv>
```

**Schemas differ between files.** v2 = 45 columns; v3 adds iceberg columns; v4 fixes the
`speed` column, which previously logged tick count while `speed_base`/`z` described volume.
**Never append across schemas.** Order rows by `local_ms`, never `server_time` — it freezes
between ticks and repeats.

---

## 7. THEN READ

1. **`RESUME_HERE_2026-10-07.md`** — project state, what is settled, what reversed, what is next
2. `TICK_SPEED.md` §53–57 — the broker comparison and the out-of-sample failure
3. `VERSION_HISTORY.md` — the last entry covers both EAs
4. `LAWS.md` — **read it, never edit it.** It is Zee's alone

---

## 8. CONTEXT BEFORE YOU SPEAK TO HIM

**On 2026-10-06 Zee liquidated a $200 PXBT account of borrowed money** — raised size from 0.01
to 0.1 lots, held a loser, flipped at the extreme. At 0.1 lots a $200 account has 20 points of
room on a market whose 15-minute range is a median 6.8 points. **His read was not the problem;
the size left no room to be wrong once.**

He lost his job. This is his only income. He is on roughly $80.

**Four findings reversed in three days** (SPRING, SWEEP, GET READY, the ranging block) — all
fitted on a feed whose price moved in 5% of seconds, all dead on gold which moves in 85%.
Permutation and mirror tests passed on every one of them and none survived a change of
instrument.

**So: no encouraging percentage travels without its caveat, and no signal is believed without
an out-of-sample test on a different instrument.** Confident numbers from this project have
already cost him real money.

---

## 9. THE ONE-LINE STATE

**The measurement apparatus is correct and there is no validated edge yet.** Instrument,
horizon and geometry are settled; the entry is not. `RiskGuardButtons` exists to make being
wrong survivable while that question is answered.
