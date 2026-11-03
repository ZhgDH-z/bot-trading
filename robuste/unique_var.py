import pandas as pd
from unique import run, rapport, SESS
pd.set_option("display.width", 250)
rows=[]
for sym in ["DE40","XAUUSD","USTECH100M","US500","US30"]:
    for s in (1,3):
        for vx in (True, False):
            rows.append(rapport(run(sym, seuil=s, vwap_exit=vx), f"{sym} seuil{s} vwap{int(vx)}"))
    rows.append(rapport(run(sym, seuil=1, vwap_exit=False, filtres=False), f"{sym} seuil1 sans filtres"))
print(pd.DataFrame(rows).to_string(index=False))
