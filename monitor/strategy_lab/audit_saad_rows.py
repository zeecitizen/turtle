import csv
from datetime import datetime as D
rows=list(csv.DictReader(open('saad_journal_v4.csv',encoding='utf-8')))
iss={}
def flag(r,msg): iss.setdefault(msg,[]).append(int(r['n']))
for r in rows:
    O,H,L,C=(float(r[k]) for k in 'OHLC'); e9=float(r['e9']); e50=float(r['e50'])
    rng=H-L; body=abs(C-O); up=H-max(O,C); dn=min(O,C)-L
    e=float(r['entry']); sl=float(r['sl']); x=float(r['exit']); p=float(r['pnl'])
    long=r['side']=='LONG'; k=r['kind']
    # shape
    if k=='PIN BAR':
        lw=max(up,dn); sw=min(up,dn)
        if not (lw>=0.35*rng-1e-9 and body<=0.6*rng+1e-9 and sw<=0.2*rng+1e-9): flag(r,'pin shape fails thresholds')
    if k=='MARUBOZU' and body<0.7*rng-1e-9: flag(r,'marubozu body<0.7')
    if k=='HAMMER':
        if not (dn>=3*body-1e-9 and up<=0.5*rng+1e-9): flag(r,'hammer shape fails')
    if k=='SHOOTING STAR':
        if not (up>=3*body-1e-9 and dn<=0.5*rng+1e-9): flag(r,'star shape fails')
    if k=='HAMMER' and not long: flag(r,'hammer on short')
    if k=='SHOOTING STAR' and long: flag(r,'star on long')
    # touch
    ev=e9 if r['ema']=='EMA9' else e50
    if not (L<=ev+1e-6 and H>=ev-1e-6): flag(r,'setup candle does not touch its EMA')
    # entry
    if long and e < H-0.011: flag(r,'long entry below setup high')
    if not long and e > L+0.011: flag(r,'short entry above setup low')
    if long and abs(e-H)>0.5: flag(r,'long entry gapped >$0.5 past high')
    if not long and abs(e-L)>0.5: flag(r,'short entry gapped >$0.5 past low')
    # SL
    exp= L-3.4 if long else H+3.4
    if abs(sl-exp)>0.02: flag(r,'SL not 34 pips beyond candle')
    if abs(e-sl)>9.0+0.01: flag(r,'risk > $9 cap')
    # TP side
    tp=r['tp']
    if tp[0].isdigit():
        t=float(tp)
        if long and t<=e: flag(r,'long TP below entry')
        if not long and t>=e: flag(r,'short TP above entry')
    # timing
    dt=(D.fromisoformat(r['tin'])-D.fromisoformat(r['setup'])).total_seconds()/60
    if dt>10: flag(r,f'entry >2 candles after setup')
    # rode losers with real TP
    if r['rode']=='True' and tp[0].isdigit() and p<0: flag(r,'rode past TP but lost')
    if r['rode']=='True' and tp.startswith('none') : pass
    # pnl consistency 0.1 lot, spread 0.2*0.1*100=2
    gross=(x-e if long else e-x)*10
    if abs(gross-2-p)>0.06: flag(r,f'pnl mismatch')
    if r['why']=='stop loss hit' and abs(x-sl)>0.01: flag(r,'SL exit not at SL price')
for m,v in iss.items(): print(f'{m}: {len(v)} -> {v[:30]}')
