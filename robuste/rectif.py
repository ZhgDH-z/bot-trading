"""Correctifs de gestion du trade, testes sur la derniere annee (L) ET verifies sur 2023 -> 10/2025 (P).
Chemin du prix rejoue sur bougies 15 min. Prudence : un stop deplace ne s'active qu'a la bougie SUIVANTE."""
import numpy as np, pandas as pd
from base import load
T = pd.read_pickle("pertes_trades.pkl")
T["costR"] = (T.side * (T.exit - T.entry) - T.R * T.risk) / T.risk
paths = []
for r in T.itertuples():
    d = load(r.symbol); w = d[(d.index >= r.open_time) & (d.index < r.close_time)]
    paths.append(((w.high.values - r.entry) / r.risk * r.side, (w.low.values - r.entry) / r.risk * r.side) if r.side == 1 else
                 ((r.entry - w.low.values) / r.risk, (r.entry - w.high.values) / r.risk))
T["Rg"] = T.R + T.costR

def sim(r, fav, adv, be=None, part=None, lock=None):
    """be : apres +be R, stop au prix d'entree ; lock : (declencheur, niveau) stop remonte a +niveau R ;
    part : moitie fermee a +part R."""
    stop = -1.0; armed = None; half = None
    for i in range(len(fav)):
        if adv[i] <= stop and i > 0 and stop > -1.0:   # stop deplace touche
            out = stop; break
        if part is not None and half is None and fav[i] >= part: half = part
        if be is not None and fav[i] >= be: stop = max(stop, 0.0)
        if lock is not None and fav[i] >= lock[0]: stop = max(stop, lock[1])
    else:
        out = r.Rg
    if out == -1.0: out = r.Rg
    res = out if half is None else 0.5 * half + 0.5 * out
    return res - r.costR

VARS = {"actuel": {}, "seuil_0_5R_BE": dict(be=0.5), "BE_1R": dict(be=1.0), "BE_1_5R": dict(be=1.5),
        "moitie_1R": dict(part=1.0), "moitie_0_5R": dict(part=0.5), "moitie_1R+BE_1R": dict(part=1.0, be=1.0),
        "verrou_2R_a_1R": dict(lock=(2.0, 1.0)), "moitie_1R+verrou": dict(part=1.0, lock=(2.0, 1.0))}
res = {}
for k, kw in VARS.items():
    res[k] = [sim(r, f, a, **kw) if kw else r.R for r, (f, a) in zip(T.itertuples(), paths)]
for k in VARS: T["R_" + k] = res[k]
T.to_pickle("rectif_trades.pkl")
rows = []
for k in VARS:
    for lig in [None] + sorted(T.ligne.unique()):
        S = T if lig is None else T[T.ligne == lig]
        for per in ["L", "P"]:
            s = S[S.per == per]["R_" + k]
            rows.append(dict(variante=k, ligne=lig or "TOUT", per=per, n=len(s), gagn=round(100 * (s > 0).mean()), eur=round(s.sum() * 100)))
R = pd.DataFrame(rows).pivot_table(index=["ligne", "variante"], columns="per", values=["gagn", "eur"])
print(R.to_string())
