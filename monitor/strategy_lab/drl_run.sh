# usage: drl_run.sh RIG "ARM"   (Jul-Oct holdout, Saad_drl)
P=/c/Users/zeesh/AppData/Local/Programs/Python/Python312-arm64/python.exe
cd /c/Users/zeesh/turtle/monitor/strategy_lab
for try in 1 2; do
  out=$($P saad_v4.py --rig $1 --nocompile --ea Saad_drl --exec 200 --period M15 --symbol XAUUSD_TK --from ${3:-2026.07.01} --to ${4:-2026.10.08} --deposit 25000 --leverage 1:1000 --timeout 1200 --out zee_drl.jsonl "$2" 2>/dev/null)
  echo "$out"; echo "$out" | grep -q " tr    0 \|ERROR" || break
done
