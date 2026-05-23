"""Quick parse of Zee's Feb-11 report to extract summary stats."""
import re
from html.parser import HTMLParser

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = []
        self.current_cell = ''
        self.in_td = False
        self.in_table = False
    def handle_starttag(self, tag, attrs):
        if tag == 'table': self.in_table = True
        if tag == 'tr' and self.in_table: self.current_row = []
        if tag in ('td', 'th') and self.in_table:
            self.in_td = True
            self.current_cell = ''
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.in_td:
            self.current_row.append(self.current_cell.strip())
            self.in_td = False
        if tag == 'tr' and self.current_row:
            self.rows.append(self.current_row)
        if tag == 'table': self.in_table = False
    def handle_data(self, data):
        if self.in_td: self.current_cell += data

with open(r'C:\Users\zeesh\Downloads\ReportHistory-5118408.html', encoding='utf-16-le', errors='replace') as f:
    html = f.read()

p = TableParser()
p.feed(html)

# Find trade rows (have buy/sell)
trades = []
for r in p.rows:
    if len(r) >= 10 and any(c.lower() in ('buy','sell') for c in r):
        side = 'buy' if any(c.lower()=='buy' for c in r) else 'sell'
        try:
            lots = float(r[5])
            entry = float(r[6])
            exit_px = float(r[10])
            pnl_pts = (exit_px - entry) if side == 'buy' else (entry - exit_px)
            pnl_usd = pnl_pts * lots * 100
            trades.append({'side': side, 'lots': lots, 'entry': entry, 'exit': exit_px,
                           'pnl_pts': pnl_pts, 'pnl_usd': pnl_usd})
        except:
            pass

wins = [t for t in trades if t['pnl_usd'] > 0]
losses = [t for t in trades if t['pnl_usd'] <= 0]
total_pnl = sum(t['pnl_usd'] for t in trades)
gross_w = sum(t['pnl_usd'] for t in wins)
gross_l = sum(t['pnl_usd'] for t in losses)

print(f"=== ZEE'S FEB-11 REPORT (account 5118408) ===")
print(f"Total trades: {len(trades)}")
print(f"Wins: {len(wins)}  Losses: {len(losses)}")
print(f"Win Rate: {len(wins)/len(trades)*100:.1f}%")
print(f"Gross Profit: ${gross_w:.2f}")
print(f"Gross Loss: ${gross_l:.2f}")
print(f"Net Profit: ${total_pnl:.2f}")
print(f"Avg Win: ${gross_w/len(wins):.2f}" if wins else "")
print(f"Avg Loss: ${gross_l/len(losses):.2f}" if losses else "")
print(f"Lots per trade: {trades[0]['lots']:.2f}")
print(f"Avg win (pts): {sum(t['pnl_pts'] for t in wins)/len(wins):.2f}" if wins else "")
print(f"Avg loss (pts): {sum(t['pnl_pts'] for t in losses)/len(losses):.2f}" if losses else "")

print(f"\n--- All trades ---")
for i, t in enumerate(trades):
    flag = 'W' if t['pnl_usd'] > 0 else 'L'
    print(f"  {i+1:>3}. {t['side']:>4} {t['lots']:.2f}  {t['entry']:.2f} -> {t['exit']:.2f}  "
          f"{t['pnl_pts']:>+6.2f}pts  ${t['pnl_usd']:>+8.2f}  {flag}")
