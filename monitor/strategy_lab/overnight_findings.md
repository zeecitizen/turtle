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

## FINDINGS LOG

### Cycle 1 — loss categorisation (baseline map)
- 24 losers / −$122.34. Overnight(broker 0-6): 4 trades, −$33.57. Day: −$88.77.
- Two clusters = −$63 of it; both now guarded. S3 give-backs = −$20, now trailed.
- **Conclusion:** the live protections target the bulk. Remaining real question is
  S3's underlying weakness (worst engine today) — next cycles will dig into whether
  S3 needs a tighter entry filter / fewer-but-better trades, validated on aligned ticks.
- Status: foundation set. No deploy.
