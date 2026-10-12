# wait for a batch log to say DONE, then run the next arm file on the same rig
until grep -q DONE "$1" 2>/dev/null; do sleep 60; done
bash /c/Users/zeesh/turtle/monitor/strategy_lab/cut_run.sh $2 $3
