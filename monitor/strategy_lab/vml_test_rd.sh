# usage: vml_test.sh RIG META_VARIANT DRL_VARIANT "ARM" ["ARM" ...]   (VSISA_ml, Jul 1 - Oct 8 holdout)
P=/c/Users/zeesh/AppData/Local/Programs/Python/Python312-arm64/python.exe
M=/c/Users/zeesh/turtle/mt5
cd /c/Users/zeesh/turtle/monitor/strategy_lab
RIG=$1; MV=$2; DV=$3; shift 3
RD=$($P -c "import axi_rig;print(axi_rig.RIGS['$RIG'])")
cp $M/VsisaMetaModel_$MV.mqh "$RD/MQL5/Experts/VsisaMetaModel.mqh"
cp $M/VsisaDrlPolicy_$DV.mqh "$RD/MQL5/Experts/VsisaDrlPolicy.mqh"
cp $M/VsisaRegimeModel.mqh $M/VsisaExhaustModel.mqh "$RD/MQL5/Experts/"
$P -W ignore -c "import axi_rig; axi_rig.use('$RIG'); axi_rig.compile_ea('VSISA_ml')" && echo "compiled meta=$MV drl=$DV on $RIG"
for arm in "$@"; do
  for try in 1 2; do
    out=$($P saad_v4.py --rig $RIG --nocompile --ea VSISA_ml --exec -1 --period M5 --symbol XAUUSD_TK --from 2026.07.01 --to 2026.10.08 --deposit 25000 --leverage 1:1000 --timeout 2500 --out zee_vsisa_ml.jsonl "InpVerbose=false,$arm" 2>/dev/null)
    echo "[$MV/$DV] $out"; echo "$out" | grep -q " tr    0 \|ERROR" || break
  done
done
