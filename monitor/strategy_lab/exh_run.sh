P=/c/Users/zeesh/AppData/Local/Programs/Python/Python312-arm64/python.exe
cd /c/Users/zeesh/turtle/monitor/strategy_lab
while read -r arm; do [ -z "$arm" ] && continue
  for try in 1 2; do
    out=$($P saad_v4.py --rig axi3 --nocompile --ea Saad_exhaust --exec 200 --period M15 --symbol XAUUSD_TK --from 2026.07.01 --to 2026.10.08 --deposit 25000 --leverage 1:1000 --timeout 1200 --out zee_exhaust.jsonl "$arm" 2>/dev/null)
    echo "$out"; echo "$out" | grep -q " tr    0 \|ERROR" || break
  done
done < exh_arms.txt
echo DONE
