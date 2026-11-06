import re,sys,glob,os,datetime
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
def parse(p):
    raw=open(p,'rb').read()
    t=raw.decode('utf-16-le',errors='ignore')
    if t.count('Expert')==0: t=raw.decode('utf-8',errors='ignore')
    x=re.sub(r'<[^>]+>',' ',t); x=re.sub(r'\s+',' ',x)
    def g(k,pat=r'([-\d\s.]+)'):
        m=re.search(re.escape(k)+r':?\s*'+pat,x)
        return float(m.group(1).replace(' ','')) if m else None
    inp=dict(re.findall(r'(Inp\w+)=([\w.\-]+)',x))
    n=g('Total Trades')
    if n is None:
        m=re.search(r'Total Deals:?\s*(\d+)',x); n=float(m.group(1))/2 if m else 0
    wr=None
    m=re.search(r'Profit Trades \(% of total\):?\s*(\d+)\s*\(([\d.]+)%\)',x)
    if m: wr=float(m.group(2)); n=n or None
    return dict(inp=inp,net=g('Total Net Profit'),n=int(n or 0),wr=wr,
                dd=g('Equity Drawdown Maximal') or g('Equity Drawdown Absolute'),
                pf=g('Profit Factor'),f=os.path.basename(p))
cut=datetime.datetime(2026,9,17,5,55).timestamp()
fs=[f for f in sorted(glob.glob('mt5/_tester_runs/diamond/DIA_*.htm'),key=os.path.getmtime)
    if os.path.getmtime(f)>cut]
DAYS=7.0
print("%-34s | %8s | %6s | %7s | %6s | %5s | %8s | %5s"%('config (from its OWN inputs)','net','trades','$/day','tr/day','WR','maxDD','PF'))
print("-"*100)
rows=[]
for f in fs:
    r=parse(f); i=r['inp']
    tm=i.get('InpTrendMode'); tp=i.get('InpTargetPts'); tr=i.get('InpTargetR','0.0')
    sl=i.get('InpSlMode'); be=i.get('InpBreakEvenR','0.0')
    if float(tr)>0: name="mode%s struct(sl%s) %sR BE%s"%(tm,sl,tr,be)
    else: name="mode%s TP%s/SL%s"%(tm,tp,i.get('InpStopPts'))
    rows.append((name,r))
    print("%-34s | %+8.0f | %6d | %+7.1f | %6.1f | %4.0f%% | $%-7.0f | %5s"%(
        name,r['net'],r['n'],r['net']/DAYS,r['n']/DAYS,r['wr'] or 0,r['dd'] or 0,r['pf']))
