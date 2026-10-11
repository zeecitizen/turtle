"""Average the random-delay repeats per arm in saad_v4.jsonl: python saad_summ.py [since_line]"""
import json, sys, collections, statistics as st
rows=[json.loads(l) for l in open('saad_v4.jsonl')][int(sys.argv[1]) if len(sys.argv)>1 else 0:]
g=collections.OrderedDict()
for r in rows:
    if 'net' not in r or not r.get('day_stats',{}).get('days'): continue
    g.setdefault((r['arm'],r.get('frm'),r.get('exec',-1),r.get('rig','axi')),[]).append(r)
for (arm,frm,ex,rig),rs in g.items():
    f=lambda k: st.mean(float(str(x[k]).rstrip('%')) for x in rs)
    gd=st.mean(x['day_stats']['green']/max(1,x['day_stats']['days']) for x in rs)
    dd=st.mean(float(x['dd'].split('(')[1].rstrip('%)')) for x in rs)
    print(f"{arm:48s} n{len(rs)} net {f('net'):8.0f} (min {min(x['net'] for x in rs):7.0f}) tr {f('trades'):5.0f} WR {f('wr'):5.1f} PF {f('pf'):.2f} DD {dd:4.1f}% green {100*gd:4.1f}% worstday {st.mean(x['day_stats']['worst'] for x in rs):6.0f} lm {st.mean(sum(v<0 for v in x['months'].values()) for x in rs):.1f} {rig} {frm}")
