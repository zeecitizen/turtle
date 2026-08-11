import re, os, sys

logs = [
    r'C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260503.log',
    r'C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260504.log',
    r'C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\20260505.log',
]

dollar_re = re.compile(r'\$(-?\d+\.\d+)')

for log in logs:
    if not os.path.exists(log):
        continue
    print(f'=== {os.path.basename(log)} ===')
    with open(log, 'rb') as f:
        text = f.read().decode('utf-16-le', errors='ignore')

    big_losses = []
    main_events = []
    fear_events = []

    for line in text.split('\n'):
        # Find all dollar amounts in line
        amounts = dollar_re.findall(line)
        amounts = [float(a) for a in amounts]

        if any(a < -10 for a in amounts) and 'ShanoEA' in line:
            big_losses.append((min(amounts), line.strip()))

        if 'MAIN' in line and 'ShanoEA' in line:
            main_events.append(line.strip())

        if 'FEAR' in line.upper() or 'fearIdeal' in line:
            fear_events.append(line.strip())

    print(f'  Big losses (<-$10): {len(big_losses)}')
    for amt, line in sorted(big_losses)[:10]:
        print(f'    [{amt:.2f}] {line[:200]}')

    print(f'  MAIN events: {len(main_events)}')
    for line in main_events[:10]:
        print(f'    {line[:200]}')

    print(f'  FEAR events: {len(fear_events)}')
    for line in fear_events[:10]:
        print(f'    {line[:200]}')
    print()
