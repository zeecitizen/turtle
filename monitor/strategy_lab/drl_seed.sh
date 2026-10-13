# usage: drl_seed.sh RIG SEED CONST
P=/c/Users/zeesh/AppData/Local/Programs/Python/Python312-arm64/python.exe
cd /c/Users/zeesh/turtle/monitor/strategy_lab
$P -W ignore -c "
import axi_rig,shutil; axi_rig.use('$1')
for f in ['SaadRegimeModel.mqh','SaadMetaModel.mqh','SaadExhaustModel.mqh']: shutil.copy(rf'C:\Users\zeesh\turtle\mt5\{f}', axi_rig.RIG/'MQL5'/'Experts'/f)
shutil.copy(r'C:\Users\zeesh\turtle\mt5\SaadDrlPolicy_s$2.mqh', axi_rig.RIG/'MQL5'/'Experts'/'SaadDrlPolicy.mqh')
axi_rig.compile_ea('Saad_drl'); print('compiled seed $2 on $1')"
echo "SEED $2 PPO"; bash drl_run.sh $1 "InpLots=1,InpPartialPct=0.5,InpTp1Be=true,InpDrlMode=1"
echo "SEED $2 CONST $3"; bash drl_run.sh $1 "InpLots=1,InpPartialPct=0.5,InpTp1Be=true,InpDrlMode=2,InpDrlConst=$3"
echo DONE
