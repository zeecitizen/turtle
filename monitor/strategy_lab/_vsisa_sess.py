"""The session filter - the one lever that REMOVES trades, and so should shrink drawdown.

Found while scanning the pullback population for something that clears the haircut. It
did not, but the strongest split in the whole scan was not about pullbacks at all:

    broker hour  0-8   n=28  reach2R 21%   <- Asian
                 8-13  n=21  reach2R 52%   <- London
                13-17  n=18  reach2R 27%
                17-24  n=41  reach2R 51%   <- NY

VSISA's InpSessFrom/InpSessTo have sat at 0-24 since the EA was written. Every other
frequency lever tonight ADDED trades and inflated drawdown past the funded limit; this one
removes them, and is the only untried direction that should move drawdown the right way.
Permitted by the revoked trash-hides-gems rule, which allows evidence-based time filters
with their own receipts. Broker clock = UTC+3.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
V={"InpBigAvg":"1.10","InpBigPct":"0.70"}
res=[evaluate('v1.24 SHIPPED (0-24)',dict(V))]
for a,b,lab in ((8,24,'drop Asian (8-24)'),(7,24,'7-24'),(9,24,'9-24'),(10,24,'10-24'),
                (8,23,'8-23'),(8,17,'London only (8-17)'),(13,24,'NY only (13-24)')):
    res.append(evaluate(lab,dict(V,InpSessFrom=str(a),InpSessTo=str(b))))
rep('VSISA session filter - does dropping the Asian session help?', res)
