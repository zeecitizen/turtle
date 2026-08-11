import re, os
log = r'C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260504.log'
with open(log, 'rb') as f:
    text = f.read().decode('utf-16-le', errors='ignore')

target = '50924704'
print(f'=== All log lines mentioning ticket {target} ===')
for line in text.split('\n'):
    if target in line:
        print(line.strip()[:250])

print()
print('=== Lines from 16:35 to 16:43 with ShanoEA / probe / main info ===')
for line in text.split('\n'):
    if '16:3' in line[:30] or '16:4' in line[:30]:
        if any(k in line for k in ['ShanoEA', 'OPEN', 'CLOSE', 'PROBE', 'MAIN', 'FEAR', 'TRAIL', 'profit']):
            print(line.strip()[:250])
