# Overnight Profitability Research — for Zee's morning ☀️

**Loop:** every ~30 min while the session is alive. Each cycle tests ONE idea on
correctly-aligned data (bars-from-ticks or rev_eng_m1; NEVER latest_for_claude+ticks)
and records an honest ACCEPT/REJECT here.

---

## MORNING SUMMARY (read this first)

**27th-May day: −$70.51 realized, 61% WR (37W/24L).** Losers totalled −$122.34; the
damage is concentrated and — importantly — **mostly in things we already fixed today
but which weren't live yet during the day:**

| Loss bucket | $ | Now addressed by |
|---|---|---|
| **14:33 cluster** (S1 −15.69 + S1 −10.65 + S3 −10.74, all long, stopped same second) | **−37.08** | anti-cluster guard (LIVE, needs the reattach you did) |
| **01:46 overnight cluster** (S3 −9.56 + −9.17) + 01:38 S1 −7.34 | **−26.07** | overnight filter + anti-cluster guard (LIVE) |
| **S3 give-backs** (14:26 −7.85, 16:01 −6.04, 19:19 −6.38) | **−20.27** | trail (LIVE) — these went green first |
| S4 give-backs (00:18 −7.50, 23:07 −7.66) | −15.16 | trail REJECTED for S4 (scratches its winners) — open question |
| small scratches / Human | rest | noise |

So **~$83 of today's −$122 loser-gross is exactly what the now-live guard + trail target.**
Today traded *naked* (protections built mid-day). Tomorrow is the first clean test.

**Worst engine: S3 (−$50.44 in losers, −$43.88 net).** Main overnight research target.

---

## ⚠️ BIGGEST FINDING SO FAR (needs your eyes before next deploy)

**The trailing profit-lock may be a NET LOSER on correct data — it likely should be
reverted.** On tick-derived bars (aligned + real tick-volume = the trustworthy oracle),
S3 with its plain structural SL/TP did **−$139 (69% WR)**, but **with the trail it did
−$289 (51% WR)**. The trail scratches S3's winners on their retrace (same mechanism that
got it REJECTED on S4). The trail's original S1/S3/NSND "win" was measured on the
*misaligned* latest_for_claude data — so it can't be trusted.

**DO NOT panic / nothing auto-changes.** Action plan: next cycles re-test the trail on
S1 and NSND on aligned data. If it hurts them too, the recommendation is to set
`InpTrailActUsd=0` (revert to plain structural SL/TP, which preserves the engines'
natural high WR) — but that's a *morning* decision with you, and needs your reattach.
Note: baseline S3 itself was only −$139 over 19d (1st half +70, 2nd half −208) — softer
than the trail, but S3 is still the weakest engine; worth a fewer-but-better entry filter
study once the exit question is settled.

## FINDINGS LOG

### Cycle 1 — loss categorisation (baseline map)
- 24 losers / −$122.34. Overnight(broker 0-6): 4 trades, −$33.57. Day: −$88.77.
- Two clusters = −$63 of it; both now guarded. S3 give-backs = −$20, now trailed.
- **Conclusion:** the live protections target the bulk. Remaining real question is
  S3's underlying weakness (worst engine today) — next cycles will dig into whether
  S3 needs a tighter entry filter / fewer-but-better trades, validated on aligned ticks.
- Status: foundation set. No deploy.

### Cycle 2 — method unlock: bars-from-ticks gives CORRECT volume too
- Native MT5 `tick_volume` = count of ticks per bar. So building M1 bars from the tick
  files (counting ticks/min) yields volume that matches live `iVolume` AND is time-aligned.
  This dissolves the rev-eng-volume mismatch — `s3_aligned_test.py` is now a fully
  trustworthy S3 oracle (alignment + volume both correct).
- (S3 real-fill history is only 16 trades / 1 day → too thin for direct fill analysis.)

### Cycle 3 — TRAIL re-validated on correct data → HURTS S3 (see ⚠️ above)
- baseline 69% WR −$139  vs  trail 51% WR −$289 (both halves worse with trail). ACCEPT:
  trail is net-negative for S3. Pending S1/NSND check before recommending fleet revert.
- Script: `s3_aligned_test.py`. No deploy (morning decision + reattach).
