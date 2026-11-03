"""Re-simule les memes setups avec plusieurs sorties (pour voir lesquelles ont un avantage)."""
import numpy as np, pandas as pd
from base import load, cost
from apprenti import SESS
EV = pd.read_pickle("apprenti_events.pkl")
VAR = {"S03_T05": (0.3, 0.5), "S03_T10": (0.3, 1.0), "S03_T20": (0.3, 2.0), "S03_FIN": (0.3, None),
       "S05_T05": (0.5, 0.5), "S05_FIN": (0.5, None), "S015_FIN": (0.15, None)}
res = {k: np.zeros(len(EV)) for k in VAR}; cst = {k: np.zeros(len(EV)) for k in VAR}
for sym, E in EV.groupby("sym"):
    d = load(sym); op, cl = SESS[sym]
    t = d.index.values; H = d.high.values; L = d.low.values; C = d.close.values; O = d.open.values
    hm = d.hm.values; day = d.day.values
    from apprenti import events  # noqa
    g = d.groupby("day")
    atr = None
    # ATR jour recalcule comme dans apprenti
    gg = g.agg(h=("high", "max"), l=("low", "min"), c=("close", "last")); pc = gg.c.shift()
    tr = pd.concat([gg.h - gg.l, (gg.h - pc).abs(), (gg.l - pc).abs()], axis=1).max(axis=1)
    A = tr.ewm(alpha=1 / 14, adjust=False).mean().shift()
    for q, r in zip(E.index, E.itertuples()):
        i0 = np.searchsorted(t, np.datetime64(r.t_in))
        i1 = i0
        while i1 + 1 < len(t) and day[i1 + 1] == day[i0] and hm[i1 + 1] < cl: i1 += 1
        e = O[i0]; s = r.side; a = A.loc[r.day]
        hh = H[i0:i1 + 1]; ll = L[i0:i1 + 1]
        for k, (sm, tm) in VAR.items():
            sd = sm * a; stop = e - s * sd
            hs = (ll <= stop) if s == 1 else (hh >= stop)
            js = np.argmax(hs) if hs.any() else 10 ** 9
            if tm is not None:
                tg = e + s * tm * sd; ht = (hh >= tg) if s == 1 else (ll <= tg)
                jt = np.argmax(ht) if ht.any() else 10 ** 9
            else: jt = 10 ** 9
            if js == 10 ** 9 and jt == 10 ** 9: R = s * (C[i1] - e) / sd
            elif js <= jt: R = -1.0
            else: R = tm
            res[k][EV.index.get_loc(q)] = R; cst[k][EV.index.get_loc(q)] = cost(sym) / sd
out = EV[["sym", "fam", "side", "day", "t_sig", "t_in", "tend"]].copy()
for k in VAR:
    out["Rg_" + k] = res[k]; out["R_" + k] = res[k] - cst[k]
out.to_pickle("apprenti_sorties.pkl")
P = out[out.day >= "2023-01-01"].copy(); P["per"] = np.where(P.day < "2025-01-01", "23-24", "25-26")
cols = ["R_" + k for k in VAR]
print("Moyenne R net par trade, tous marches :"); print(P.groupby("per")[cols].mean().round(3).to_string())
print("Taux de gain :"); print((P.groupby("per")[cols].agg(lambda x: (x > 0).mean())).round(3).to_string())
for m in ["DE40", "XAUUSD", "US500", "USTECH100M", "US30"]:
    print(m); print(P[P.sym == m].groupby(["fam", "per"])[cols].mean().unstack("per").round(3).to_string())
