# usage: metareg_run.sh RIG MODELNAME "THR THR ..."  — compile mt5/SaadMetaModel_<MODEL>.mqh into the rig's Saad_meta, run Jul-Oct holdout
P=/c/Users/zeesh/AppData/Local/Programs/Python/Python312-arm64/python.exe
cd /c/Users/zeesh/turtle/monitor/strategy_lab
$P -c "
import axi_rig,shutil; axi_rig.use('$1')
shutil.copy(r'C:\Users\zeesh\turtle\mt5\SaadMetaModel_$2.mqh', axi_rig.RIG/'MQL5'/'Experts'/'SaadMetaModel.mqh')
shutil.copy(r'C:\Users\zeesh\turtle\mt5\Saad_meta.mq5', axi_rig.RIG/'MQL5'/'Experts'/'Saad_meta.mq5')
import subprocess,re
log=axi_rig.RIG/'compile.log'
subprocess.run([str(axi_rig.RIG/'MetaEditor64.exe'),'/portable',f'/compile:{axi_rig.RIG/\"MQL5\"/\"Experts\"/\"Saad_meta.mq5\"}',f'/log:{log}'])
t=log.read_text(encoding='utf-16',errors='ignore'); print('compile', 'OK' if re.search(r'Result: 0 errors',t) else 'FAILED')
"
echo "MODEL $2"
for thr in $3; do
  $P saad_v4.py --rig $1 --nocompile --ea Saad_meta --exec 200 --period M15 --symbol XAUUSD_TK --from 2026.07.01 --to 2026.10.08 --deposit 25000 --leverage 1:1000 --timeout 900 --out zee_metareg.jsonl "InpLots=1,InpPartialPct=0.5,InpTp1Be=true,InpMetaMode=1,InpMetaThr=$thr" 2>/dev/null
done
