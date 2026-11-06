import json,re,glob,csv,collections
rows=[]
for f in sorted(glob.glob('saad_journal_v4/page*.json')):
    d=json.load(open(f,encoding='utf-8'))
    for s in d['studies']:
        for t in s['tables']:
            for r in t['rows']:
                if r.startswith('#'): rows.append(r)
pat=re.compile(r"#(\d+) \| (\S+ \S+) (LONG|SHORT) (.+?) on (EMA\d+)(\(([^)]*)\))? O=(\S+) H=(\S+) L=(\S+) C=(\S+) e9=(\S+) e50=(\S+) ER=(\S+) \|\| IN (\S+ \S+) (BUY|SELL) (\S+) SL (\S+) TP (.+?) \|\| OUT (\S+ \S+) (.+?) @ (\S+)( \[rode\])? moves (\d+) \|\| (\S+)")
out=[];bad=0
for r in rows:
    m=pat.match(r)
    if not m: bad+=1; print('NOMATCH',r[:120]); continue
    g=m.groups()
    out.append(dict(n=int(g[0]),setup=g[1],side=g[2],kind=g[3],ema=g[4],rule=g[6] or '',O=g[7],H=g[8],L=g[9],C=g[10],e9=g[11],e50=g[12],er=g[13],tin=g[14],entry=float(g[16]),sl=float(g[17]),tp=g[18],tout=g[19],why=g[20],exit=float(g[21]),rode=bool(g[22]),moves=int(g[23]),pnl=float(g[24])))
out.sort(key=lambda x:x['n'])
with open('saad_journal_v4.csv','w',newline='',encoding='utf-8') as fh:
    w=csv.DictWriter(fh,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print(len(out),'trades parsed',bad,'bad')
def summ(name,xs):
    if not xs: return
    w=sum(1 for x in xs if x['pnl']>0); n=len(xs); net=sum(x['pnl'] for x in xs)
    gp=sum(x['pnl'] for x in xs if x['pnl']>0); gl=-sum(x['pnl'] for x in xs if x['pnl']<0)
    print(f"{name:40s} n={n:4d} WR={100*w/n:5.1f}% net={net:9.2f} PF={gp/gl if gl else 0:5.2f} avg={net/n:7.2f}")
summ('ALL',out)
for k in ['side','kind','ema','rule','why','rode']:
    print('--',k)
    for v in sorted(set(str(x[k]) for x in out)): summ(f'{k}={v}',[x for x in out if str(x[k])==v])
print('-- TP none longs'); summ('tp none',[x for x in out if x['tp'].startswith('none')])
print('-- hour of entry (chart tz)')
for h in range(24): summ(f'h{h:02d}',[x for x in out if int(x['tin'][11:13])==h])
print('-- by day')
days=collections.defaultdict(list)
for x in out: days[x['tin'][:10]].append(x)
for d in sorted(days): summ(d,days[d])
print('-- ER buckets')
for lo,hi in [(0,.15),(.15,.2),(.2,.3),(.3,.4),(.4,1.1)]: summ(f'ER {lo}-{hi}',[x for x in out if lo<=float(x['er'])<hi])
print('-- risk $ buckets (entry-sl)')
for lo,hi in [(0,5),(5,7),(7,8),(8,9.1)]: summ(f'risk {lo}-{hi}',[x for x in out if lo<=abs(x['entry']-x['sl'])<hi])
print('-- same-candle in/out'); summ('same',[x for x in out if x['tin']==x['tout']])
