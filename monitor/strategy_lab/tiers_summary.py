import json, collections
rows=[json.loads(l) for l in open('zee_tiers_monthly.jsonl')]
g=collections.defaultdict(list)
for r in rows:
    g[(int(r['deposit']), r['arm'])].append(r)
for (dep, arm), rs in sorted(g.items()):
    fin=[]; err=0
    for r in rs:
        if 'net' not in r: err+=1; continue
        fin.append(dep + r['net'])
    if not fin: print(dep, arm, 'no results', err); continue
    lost50=sum(f < dep*0.5 for f in fin); down=sum(f < dep for f in fin)
    print(f"${dep:<4} {arm:36s} months {len(fin)} | end-of-month balance: worst {min(fin):8.2f} median {sorted(fin)[len(fin)//2]:8.2f} best {max(fin):8.2f} | losing months {down}/{len(fin)} | lost >50% {lost50}/{len(fin)} | errors {err}")
