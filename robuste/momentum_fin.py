"""Famille 1 : MOMENTUM DE FIN DE SEANCE (Gao, Han, Li, Zhou 2018, J. Financial Economics ;
Baltussen, Da, Lammers, Martens 2021, J. Financial Economics : couverture gamma des options).
Regle : le rendement depuis la cloture d'hier jusqu'a 'sig_end' donne le sens ; on entre a 'entry'
et on sort a la cloture de la seance. 1 trade par jour et par marche, achat ou vente.
Stop de secours a 1 R ; R = k x ATR journalier."""
import numpy as np, pandas as pd
from base import load, daily_atr, cost, summary, MKTS

SESS = {  # (ouverture, derniere bougie de la seance) en heure serveur
    "US": (1630, 2245), "DE40": (1000, 1815)}

def run(sym, sig_end, entry, last_bar, k=0.1, min_sig=0.0):
    d = load(sym); a = daily_atr(sym)
    out = []; prev_close = None
    for day, g in d.groupby("day"):
        hmv = g.hm.values
        if last_bar not in hmv or entry not in hmv or sig_end not in hmv:
            # memorise quand meme la cloture du jour si dispo
            if last_bar in hmv: prev_close = g.close.values[hmv == last_bar][0]
            continue
        cl = g.close.values[hmv == last_bar][0]
        if prev_close is None or np.isnan(a.get(day, np.nan)):
            prev_close = cl; continue
        ref = g.open.values[hmv == sig_end][0]          # prix au debut de la bougie sig_end = fin de la fenetre du signal
        sig = ref / prev_close - 1
        prev_close_today = cl
        if abs(sig) > min_sig:
            side = 1 if sig > 0 else -1
            win = g[(hmv >= entry) & (hmv <= last_bar)]
            e = win.open.values[0]; rk = k * a[day]
            x = win.close.values[-1]
            for h, l in zip(win.high.values, win.low.values):
                if side == 1 and l <= e - rk: x = e - rk; break
                if side == -1 and h >= e + rk: x = e + rk; break
            gross = side * (x - e) / rk; c = cost(sym) / rk
            out.append(dict(day=day, sym=sym, side=side, entry=e, exit=x, R_gross=gross, cost_R=c, R=gross - c))
        prev_close = prev_close_today
    return pd.DataFrame(out)

if __name__ == "__main__":
    rows = []
    for sym in MKTS:
        if sym == "DE40":
            o, lb = SESS["DE40"]; variants = [(1030, 1800), (1800, 1800), (1730, 1800), (1800, 1815)]
        else:
            o, lb = SESS["US"]; variants = [(1700, 2230), (2230, 2230), (2200, 2230), (2230, 2245)]
        for sig_end, entry in variants:
            for k in (0.1, 0.2):
                T = run(sym, sig_end, entry, lb, k)
                s = summary(T, f"{sym} sig<{sig_end} in{entry} k{k}")
                rows.append(s)
    R = pd.DataFrame(rows)
    pd.set_option("display.width", 200); pd.set_option("display.max_rows", 200)
    print(R.to_string(index=False))
    R.to_csv("momentum_fin.csv", index=False)
