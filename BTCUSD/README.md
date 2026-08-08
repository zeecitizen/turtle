# BTCUSD — the ghost, cloned for Bitcoin (2026-08-08)

Same laws, same exits, its own everything else. Built so the two machines can never
touch each other's orders.

## What is different from gold, and why

| | XAUUSD | BTCUSD |
|---|---|---|
| feed | TradingView CDP (OANDA) | **Binance public API** — see below |
| bars file | `oanda_m1.csv` | `btc_m1.csv` |
| signal / box | `case_signal.json` · `case_watch.json` | `btc_signal.json` · `btc_watch.json` |
| magic | 88020 | **88021** |
| EA | `CaseSignalExecutor.mq5` | `BTCCaseExecutor.mq5` |
| distances | gold points | **× 3.7** (measured, below) |

**Why not TradingView for BTC:** OANDA's BTCUSD is a *CFD* — it closes with forex on
Friday and its chart froze at 20:59 UTC. And the TradingView desktop, left unattended,
delivered half-empty bars. `binance_bridge.py` uses Binance's public klines endpoint:
no key, no browser, no window in focus, and real exchange volume — which is the whole
point of Zee's method. Volume is fractional BTC so it is stored ×1000 as an integer;
every rule is relative, so the unit never matters.

**The scale (measured, never guessed).** Bitcoin's minute is bigger than gold's, so
every distance in the rulebook had to be converted. Measured on Binance's live tape:
active-bar median range **$7.26** vs gold **$1.95** → **SCALE 3.7** (`btc_scale.txt`,
recomputed by `measure_scale.py`).

**Half of Bitcoin's minutes are dead** (median range $0.02; the tape is bimodal —
long flat stretches punctuated by $10–$85 bursts). The dead-tape gate matters far
more here than it ever did on gold.

## Running it
```
py BTCUSD/binance_bridge.py --loop 20     # feed
py BTCUSD/btc_matcher.py                  # the brain
```
Then attach **BTCCaseExecutor** to a BTCUSD M1 chart in MT5 (Algo Trading on).

## Honest expectation
On 8 hours of this tape the strategy produced 38 lawful setups, 79% WR, **+$1.39 net
at 0.20 lots**. Bitcoin moves ~0.01% per minute here versus gold's ~0.045%, so the
same rules earn far less per trade at safe size. It is a real edge on a quiet
instrument — not a replacement for gold, and every number above is simulation, which
this project has learned to distrust. Live fills decide.
