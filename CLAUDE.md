# Claude Go Hawking

When Zeeshan says **"Claude go hawking"**, run the full startup sequence below. No questions, no confirmations. Just do it.

## Startup Sequence

### Step 1: Run startup.bat
```
powershell -ExecutionPolicy Bypass -File "c:\Users\zeesh\Documents\GitHub\turtle\startup.bat"
```
This launches: dashboard, sniper daemon, Silver Hawk learner, Intern Hawks, Sheriff Hawk.

### Step 2: Register the trading cron
Read `crons/jobs/claude_trader.md` then:
```
CronCreate(cron="* * * * *", recurring=true, durable=true, prompt=<contents of claude_trader.md>)
```

### Step 3: Verify everything is alive
```
powershell -Command "C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe C:\Users\zeesh\Documents\GitHub\turtle\monitor\sheriff_hawk.py"
```
Check the Sheriff output — all components should show ALIVE.

### Step 4: Confirm to user
Tell Zee: "All hawks are flying. Sniper watching, Silver Hawk learning, Interns researching, Sheriff patrolling."

---

## What Each Hawk Does

| Hawk | File | Schedule | Purpose |
|------|------|----------|---------|
| **Sniper Daemon** | `monitor/claude_sniper_daemon.py` | Always on | Watches price via CDP, fires trades via PineConnector, manages P&L with bid/ask spread |
| **Claude Trader Cron** | `crons/jobs/claude_trader.md` | Every minute | Detects new UHV labels, writes sniper target for daemon |
| **Silver Hawk Learner** | `monitor/silver_hawk_learner.py` | Every 15 min | Takes chart screenshots, learns visual patterns, VSA research |
| **Intern Hawks** | `monitor/intern_hawks.py` | Daily | 3 interns browse internet for trading theories, write journal |
| **Meeting Room** | `monitor/meeting_hawks.py --loop` | 9am + 9pm PKT | Full team standup — every engine presents with personality, Secretary delivers summary |
| **Sexy Hawk** | `monitor/sexy_hawk.py --loop` | Every 2h | Secretary — WhatsApp reports to Zee with sass and attitude |
| **Sheriff Hawk** | `monitor/sheriff_hawk.py --loop` | Every hour | Angry old man QA — BP tracks with losses, dies at 0% hourly WR, revive with `--revive` |

## Critical Settings (DO NOT CHANGE without testing)
- **mTS = 25** (input 72) — minimum tick size filter, blocks Sydney garbage
- **sFilt = true** (input 74) — session filter, blocks Sydney/maintenance
- **Lots = 0.40** — current position size
- **TP = 52 pips, SL = 15 pips** — PineConnector values
- **Spread tracking**: hawk uses BID for sell entry, ASK for buy entry (NEVER last_price)

## Known Mistakes (Sheriff monitors these)
1. **spread_hallucination** — hawk P&L MUST use bid/ask, not chart price
2. **restart_refire** — daemon reads `.last_uhv_id` on startup to avoid duplicate trades
3. **sydney_session** — 0% WR in Sydney, mTS+sFilt filters mandatory
4. **stale_breakout** — don't fire when price is 2+ points past UHV
5. **false_breakout_filter** — candle-close confirmation required before firing

## File Locations
- Python: `C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe`
- Project: `C:\Users\zeesh\Documents\GitHub\turtle\`
- Monitor scripts: `monitor/`
- Cron jobs: `crons/jobs/`
- API key: `monitor/.claude_api_key`
- WhatsApp config: `monitor/.whatsapp_config.json`
- Trade history: `monitor/reflections.json`
- Theories: `monitor/theories.json`
- Patterns: `monitor/silver_hawk_patterns.json`
- Intern journals: `monitor/intern_journal/`

## WhatsApp Contacts
- **Shano (sister)**: 923364863368@c.us — trade alerts in Urdu
- **Zeeshan**: 4915119175329@c.us — Sheriff emergency alerts
