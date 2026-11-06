"""run_selftune.py - run saad15_selftune.py with the compare page's 10-month auto re-run paused (both use rigs axi2-7), log to selftune.out."""
import json
import urllib.request

import saad15_selftune as st


def year_auto(on):
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8772/api/year", data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        print("page:", e, flush=True)


year_auto(False)
try:
    st.main(log=lambda s: print(s, flush=True))
finally:
    year_auto(True)
    print("SELFTUNE DONE", flush=True)
