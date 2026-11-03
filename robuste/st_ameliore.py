"""Réduire les pertes du supertrend DAX et des grosses lignes (03/11/2026).
Idées : filtre ADX (scanner-bullish de staskh/trading_skills), filtre tendance 20 jours, stop suiveur (ib-trailing-stop).
Choix sur P, vérification sur L. Prudence : dans une bougie, le stop suiveur d'avant est testé AVANT d'être remonté."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fs_robuste as FR
from base import load, cost
L0 = FR.L0; B = FR.B; cs = cost("DE40")
S = pd.read_pickle(os.path.join(HERE, "supertrend_trades.pkl")); s = FR.sig("supertrend", 4.0)
pos = B.index.get_indexer(S.t0) - 1; S["side"] = s[pos]; S["i0"] = pos + 1; S["i1"] = B.index.get_indexer(S.t1)
# ADX 14 sur 15 min, à la bougie du signal
h, l, c = B.high, B.low, B.close
up, dn = h.diff(), -l.diff()
pdm = np.where((up > dn) & (up > 0), up, 0.0); ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
atr = tr.ewm(alpha=1/14, adjust=False).mean()
pdi = 100 * pd.Series(pdm, index=B.index).ewm(alpha=1/14, adjust=False).mean() / atr
ndi = 100 * pd.Series(ndm, index=B.index).ewm(alpha=1/14, adjust=False).mean() / atr
adx = (100 * (pdi - ndi).abs() / (pdi + ndi)).ewm(alpha=1/14, adjust=False).mean()
S["adx"] = adx.values[pos]
d = load("DE40"); Dc = d.close.groupby(d.day).last(); trend = np.sign(Dc - Dc.rolling(20).mean()).shift()
S["tend"] = trend.reindex(S.day).values * S.side
def tot(df): return {p: round(df[(df.day >= L0) == (p == "L")].R.sum() * 1000) for p in "PL"}
base = tot(S); print("Supertrend DAX seul :", base, " trades", len(S))
for a in [15, 20, 25, 30]:
    r = tot(S[S.adx >= a]); print(f"ADX >= {a:2d} : P {r['P']-base['P']:+7d} €  L {r['L']-base['L']:+7d} €  ({(S.adx < a).sum()} retirés)")
r = tot(S[S.tend > 0]); print(f"sens de la tendance 20 j : P {r['P']-base['P']:+7d} €  L {r['L']-base['L']:+7d} €  ({(S.tend <= 0).sum()} retirés)")
# stop suiveur : dès +a R, le stop suit à b R sous le meilleur prix
H, Lo, O = B.high.values, B.low.values, B.open.values
def trail(r, a, b):
    e = O[r.i0]; rk = 1.5 * atr.values[r.i0 - 1]; best = 0.0; stop = None
    for i in range(r.i0, r.i1 + 1):
        adv = ((Lo[i] - e) if r.side > 0 else (e - H[i])) / rk     # pire point de la bougie, en R
        if stop is not None and adv <= stop:
            return stop - cs / rk
        fav = ((H[i] - e) if r.side > 0 else (e - Lo[i])) / rk
        best = max(best, fav)
        if best >= a: stop = max(stop if stop is not None else -1, best - b)
    return r.R
for a, b in [(1, 1), (2, 1), (2, 1.5), (3, 1.5), (3, 2), (4, 2)]:
    S2 = S.copy(); S2["R"] = [trail(r, a, b) for r in S.itertuples()]
    rr = tot(S2); print(f"stop suiveur dès +{a} R à {b} R : P {rr['P']-base['P']:+7d} €  L {rr['L']-base['L']:+7d} €")
S.to_pickle(os.path.join(HERE, "st_ameliore.pkl"))
