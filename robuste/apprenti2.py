"""Apprenti v2 : meme memoire, mais le bot connait plusieurs sorties et apprend laquelle marche pour chaque setup.
Pour chaque setup : la memoire estime le gain moyen de chaque sortie ; le bot prend la meilleure
si son gain attendu (couts deduits) depasse SEUIL. Toujours sans donnee future."""
import numpy as np, pandas as pd, sys
from multiprocessing import Pool
from apprenti import FEATS, FAM, knn_family, portefeuille, bilan, START_TRADE
EV = pd.read_pickle("apprenti_events.pkl"); S = pd.read_pickle("apprenti_sorties.pkl")
VARS = ["S03_T05", "S03_T10", "S03_FIN", "S05_T05", "S05_FIN", "S015_FIN"]
MK = sys.argv[1].split(",") if len(sys.argv) > 1 else None
if MK: keep = EV.sym.isin(MK); EV = EV[keep]; S = S[keep]
preds = {}
for v in VARS:
    E = EV.copy(); E["R"] = S["R_" + v]; E["win"] = (E.R > 0).astype(int)
    with Pool(4) as p:
        res = p.map(knn_family, [(E[E.fam == f].sort_values("t_sig"), dict(k=80, hl=365, mismatch=1.5)) for f in FAM])
    preds[v] = pd.concat(res).reindex(EV.index)
EXm = pd.concat({v: preds[v].EX for v in VARS}, axis=1).dropna(how="all")
EV = EV.loc[EXm.index]
best = EXm.idxmax(axis=1); bestEX = EXm.max(axis=1)
T = EV[["sym", "fam", "side", "day", "t_sig", "t_in"]].copy()
T["sortie"] = best; T["EX"] = bestEX
T["P"] = [preds[b].P.loc[i] if isinstance(b, str) else np.nan for i, b in zip(T.index, best)]
T["R"] = [S.loc[i, "R_" + b] if isinstance(b, str) else np.nan for i, b in zip(T.index, best)]
T["t_out"] = T.day + pd.Timedelta(days=1)   # regle simple : 1 trade par marche et par jour
T = T[T.t_in >= START_TRADE]
tag = "_".join(MK) if MK else "tous"
T.to_pickle(f"apprenti2_{tag}.pkl")
rows = []
for se in [0.0, 0.05, 0.10, 0.15, 0.20]:
    sel = portefeuille(T[T.EX >= se]); rows.append(bilan(sel, f"attendu >= {se:.2f} R"))
print(tag); print(pd.DataFrame(rows).to_string())
print(T[T.EX >= 0.10].groupby("sortie").R.agg(["size", "mean"]).round(3))
