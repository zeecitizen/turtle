# TIME-EXIT STUDY — is the harvest dimension time, not distance?

Setups: 106 (tick-verified breakout moments) · Feb-11 benchmark: median hold 65s, mean 275s, median win +1.01pt

| hold | mean pts | median | WR>0 | EV Raw | EV Std | ghost-EV Raw |
|---|---|---|---|---|---|---|
| 1 tick | +0.019 | +0.010 | 52% | -0.051 | -0.181 | -0.051 |
| 5s | +0.220 | +0.148 | 58% | +0.150 | +0.020 | +0.148 |
| 10s | +0.483 | +0.368 | 71% | +0.413 | +0.283 | +0.377 |
| 20s | +0.944 | +0.845 | 80% | +0.874 | +0.744 | +0.777 |
| 30s | +1.337 | +1.163 | 92% | +1.267 | +1.137 | +1.098 |
| 45s | +1.966 | +1.635 | 95% | +1.896 | +1.766 | +1.600 |
| 65s* | +2.576 | +2.318 | 95% | +2.506 | +2.376 | +2.094 |
| 2min | +2.903 | +2.330 | 90% | +2.833 | +2.703 | +2.421 |
| 3min | +2.922 | +2.398 | 90% | +2.852 | +2.722 | +2.448 |
| 5min | +2.758 | +2.570 | 78% | +2.688 | +2.558 | +2.376 |
| 10min | +2.914 | +2.085 | 69% | +2.844 | +2.714 | +2.486 |

**Best time-exit (ghost-protected, Raw costs): 10min (EV +2.486 pt/click)**

*65s = the Feb-11 median hold. Ghost-EV = bail at −1.0pt if hit first (the realistic ghost), else exit at the time mark.*