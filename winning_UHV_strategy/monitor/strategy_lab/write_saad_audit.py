import csv,collections
rows=list(csv.DictReader(open('saad_journal_v4.csv',encoding='utf-8')))
def rule(r):
    if r['side']=='SHORT':
        base='SHORT entry rule (setup on the '+('50 EMA = written rule' if r['ema']=='EMA50' else '9 EMA = your "Either EMA" extension')+'; break of the low within 2 candles; TP = last support)'
    elif 'inverse' in r['rule']:
        base='LONG inverse rule (your addition: setup on the 50 EMA, exit on the 9 EMA)'
    else:
        base='LONG written rule (setup on the 9 EMA, break of the high within 2 candles, exit at the 50 EMA)'
    k=r['kind']
    extra={'HAMMER':' · candle = hammer (your ⑨ addition)','SHOOTING STAR':' · candle = shooting star (your ⑨ addition)','MARUBOZU':' · candle = marubozu','PIN BAR':' · candle = pin bar'}[k]
    return base+extra
L=[]
w=L.append
n=len(rows); wins=sum(float(r['pnl'])>0 for r in rows); net=sum(float(r['pnl']) for r in rows)
w('# Saad Strategy — every setup the TradingView indicator took\n')
w('*Generated 2026-10-11 from the indicator\'s own trade journal (v4 engine) on OANDA:XAUUSD 5-minute, Zee\'s saved settings ([optimal_settings_saad_strategy.md](optimal_settings_saad_strategy.md)). Prices in $, P&L at 0.1 lots after a $0.20 spread. Chart times are UTC (Pakistan = +5).*\n')
w('> These are the indicator\'s figures, worked out on the chart; they are not MT5 results. MT5 has the final say — see the EA section of [SAAD_INDICATOR_AUDIT.md](SAAD_INDICATOR_AUDIT.md).\n')
w(f'**{n} trades · win rate {100*wins/n:.1f}% · net {net:+.2f}$**\n')
w('Rules come from [mt5/RULES_EMA_SAAD.md](mt5/RULES_EMA_SAAD.md): LONG = setup on the 9 EMA, break the high within 2 candles, TP when a candle reaches the 50 EMA. SHORT = setup on the 50 EMA, break the low within 2 candles, TP at the last support. SL beyond the candle (rules: 20 pips; your setting: 34). Your settings add "Either EMA", hammers, the inverse long rule, and trailing after the TP ("rode").\n')
w('| # | Setup (UTC) | Side | Candle on | Rule followed | Entry | SL | TP | Exit (UTC) | How it ended | P&L $ |')
w('|---|---|---|---|---|---|---|---|---|---|---|')
for r in rows:
    tp=r['tp']; tp='none — trail from entry (exit EMA below / too close)' if tp.startswith('none') else ('when a candle closes at the '+tp.replace('EMA','')+' EMA' if tp.startswith('EMA') else tp)
    why=r['why']
    if r['rode']=='True' and why=='trailing stop hit':
        why='TP reached → trailed → trailing stop' if not r['tp'].startswith('none') else 'trailing stop (no TP)'
    w(f"| {r['n']} | {r['setup']} | {r['side']} | {r['kind'].lower()} on {r['ema']} | {rule(r)} | {r['entry']} | {r['sl']} | {tp} | {r['tout']} | {why} @ {r['exit']} | {float(r['pnl']):+.2f} |")
open('../../SAAD_SETUPS.md','w',encoding='utf-8').write('\n'.join(L)+'\n')
print('ok',len(rows))
