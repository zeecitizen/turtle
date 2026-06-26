import sys, json
from pathlib import Path
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor")
from whatsapp_alert import _send_single

ZEE   = "4915119175329@c.us"
SHANO = "923364863368@c.us"

ZEE_MSG = (
    "Jaan, setup labelling page is LIVE:\n\n"
    "https://setups.claudezeeshan.com/setups.html\n\n"
    "36 S1 setups from the last 2 days. Each chart has UHV marker + entry arrow. "
    "Below every chart there are TWO textboxes:\n"
    "- Zeeshan's analysis (Save Comment)\n"
    "- Shano baji's analysis (Save Comment)\n\n"
    "Type your thoughts on each, hit Save. I'll generate fix-tasks per label and "
    "iterate the EA toward 80%+ WR for Tuesday's proof.\n\n"
    "Open it on any device."
)

SHANO_MSG = (
    "Shano baji, Zeeshan ne ek page banaya hai aap ke liye setups verify karne ke liye:\n\n"
    "https://setups.claudezeeshan.com/setups.html\n\n"
    "Har chart ke neeche aap ke liye 'Shano baji's analysis' textbox hai. Aap ka "
    "analysis save karne se Claude EA ko theek karega — 80%+ winrate ka target.\n\n"
    "Phone par open kar lo, scroll karein, likhein, Save Comment. Shukriya baji!"
)

print("Zee:")
_send_single(ZEE_MSG, ZEE)
print("Shano:")
_send_single(SHANO_MSG, SHANO)
