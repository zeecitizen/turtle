# tasks.md — Zee's assigned tasks, numbered & tracked

Per Rule #10 (startup.bat). Append-only. Numbers are global across sessions.
A task is OPEN until Zee explicitly says it's complete.

| # | Status |
|---|---|
| (the rest is event log) | |


## TASK-001  opened 2026-06-04 00:30 PKT — Get live EA on Atmos producing real-money positive day (Rule #3 north star)

## TASK-002  opened 2026-06-04 00:30 PKT — Verify chat.claudezeeshan.com subdomain serves /chat-app over HTTPS

## TASK-003  opened 2026-06-04 00:30 PKT — Always display times to Zee in Pakistan Time (PKT) per Rule #9
- 2026-06-04 00:31 PKT — DNS CNAME added via cloudflared route, tunnel ingress updated, cert provisioned, HTTPS 200 verified from machine. Awaiting Zee's phone test.
- 2026-06-04 00:33 PKT — Rule #9 implemented in memory_hawk.py — entry headers now show PKT primary, UTC secondary. Latest hourly entry confirms: '## 2026-06-04 00:32 PKT (2026-06-03 19:32 UTC)'. All new chat messages to Zee also use PKT. Old entries left untouched (append-only).
- 2026-06-04 00:33 PKT — Infrastructure round done. EA paused on Atmos at -224.82 day P&L. Validated Python predicts +253 at 0.05 lots on June 3 ticks. Next test = tomorrow's Session1 at 06:30 PKT. Daemons all alive: dd_watch will alert on any fill within seconds.
