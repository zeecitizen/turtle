# ⚠️ READ `LATEST_REPORT.md` BEFORE TOUCHING ANY EA WORK

This folder always contains the **most recent daily report**. Overwrite
`LATEST_REPORT.md` here at the END of every session so the NEXT session's
Claude can read it in 30 seconds and continue, not restart.

**Pattern that must STOP:**
> progress → failure → abandon prior research + work → new progress → failure → abandon all research → new progress (ALL PREVIOUS LEARNING IS LOST. EVERY SINGLE TIME.)

**Pattern that must REPLACE it:**
> read LATEST_REPORT → see what's live, what was tried, what failed, what works → continue from there → at end of session, overwrite LATEST_REPORT with today's summary.

## Files in this folder

- `LATEST_REPORT.md` — always the most recent daily report. Copy of the dated report in `../YYYY-MM/`.
- `README.md` — this file.

## How to use

**At start of a new session**, before opening any tool or running any backtest:
1. Read `daily_reports/_LATEST/LATEST_REPORT.md` fully.
2. Check the "Live state" section — what's running NOW.
3. Check the "What failed today" section — what NOT to try again.
4. Check the "Foundational rules" section — what guards every decision.
5. Then continue work from where it ended.

**At end of session**, before stopping:
1. Write a new dated report in `daily_reports/YYYY-MM/report-YYYY-MM-DD.md`.
2. Copy it to `daily_reports/_LATEST/LATEST_REPORT.md` (overwrite).
3. Stop.

This convention is the only thing that breaks the rediscovery loop.
