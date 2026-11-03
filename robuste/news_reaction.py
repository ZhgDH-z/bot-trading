"""Idée news-reaction-failure-analyzer (03/11/2026) : après CPI/NFP (15:30 serveur), suivre ou contrer
le mouvement des 30 premières minutes. Entrée 16:00 serveur, stop k x ATR jour, sortie fin de séance.
Choix des réglages sur P (avant 03/11/2025), vérification sur L."""
import os, sys, itertools
import pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from base import load, daily_atr, cost
from news_filtre import CPI, NFP
L0 = pd.Timestamp("2025-11-03")
days = sorted(pd.Timestamp(d) for d in CPI + NFP if pd.Timestamp(d) >= pd.Timestamp("2023-01-01"))
FIN = {"DE40": 1815, "XAUUSD": 2245}
res = []
for sym in ["DE40", "XAUUSD"]:
    d = load(sym); atr = daily_atr(sym)
    for mode, k, seuil, entree in itertools.product(["suivre", "contrer"], [0.15, 0.3, 0.5], [0.0, 0.1, 0.2], [1600, 1630]):
        out = []
        for day in days:
            x = d[d.day == day]
            if day not in atr.index or len(x) < 20: continue
            a = atr[day]
            p0 = x[x.hm == 1515]; pe = x[x.hm == entree - (15 if entree % 100 else 55)]
            if not len(p0) or not len(pe): continue
            ref, px = p0.close.iloc[0], pe.close.iloc[0]
            move = (px - ref) / a
            if abs(move) < seuil: continue
            side = np.sign(move) * (1 if mode == "suivre" else -1)
            if side == 0: continue
            stop = k * a
            after = x[(x.hm >= entree) & (x.hm <= FIN[sym])]
            R = None
            for _, b in after.iterrows():
                adverse = (px - b.low) if side > 0 else (b.high - px)
                if adverse >= stop: R = -1.0; break
            if R is None: R = side * (after.close.iloc[-1] - px) / stop
            R -= cost(sym) / stop
            out.append((day, R))
        if not out: continue
        o = pd.DataFrame(out, columns=["day", "R"])
        P, L = o[o.day < L0], o[o.day >= L0]
        res.append((sym, mode, k, seuil, entree, len(P), round(P.R.sum() * 1000), len(L), round(L.R.sum() * 1000)))
R = pd.DataFrame(res, columns=["sym", "mode", "stopATR", "seuil", "entree", "nP", "P_€", "nL", "L_€"])
pd.set_option("display.width", 200)
for sym in R.sym.unique():
    r = R[R.sym == sym].sort_values("P_€", ascending=False)
    print(r.head(8).to_string()); print("part des réglages positifs sur P :", round((r["P_€"] > 0).mean(), 2), " sur L :", round((r["L_€"] > 0).mean(), 2)); print()
R.to_pickle(os.path.join(HERE, "news_reaction.pkl"))
