# usage: cut_run.sh RIG ARMFILE  — Zee's 2026-10-13 loss-cutting list on Saad_cut, 1 lot, $25k, XAUUSD_TK real ticks
P=/c/Users/zeesh/AppData/Local/Programs/Python/Python312-arm64/python.exe
cd /c/Users/zeesh/turtle/monitor/strategy_lab
while read -r arm; do
  [ -z "$arm" ] && continue
  $P saad_v4.py --rig $1 --nocompile --ea Saad_cut --exec 200 --period M15 --symbol XAUUSD_TK --from 2026.01.06 --to 2026.10.08 --deposit 25000 --leverage 1:1000 --timeout 900 --out zee_cut.jsonl "$arm" 2>/dev/null
done < $2
echo DONE
