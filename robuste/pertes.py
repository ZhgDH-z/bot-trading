"""Analyse des pertes (demande d'aurele, 03/11/2026) : bot v1.02 (= demo + 2 correctifs DAX + or tendance).
Derniere annee L = 03/11/2025 -> 02/11/2026 ; annee(s) d'avant P = 01/01/2023 -> 02/11/2025 pour VERIFIER chaque correctif.
Pour chaque trade : contexte (sens, jour, heure, volatilite, force de tendance, elan, mouvement deja fait) et
excursion (le trade a-t-il ete gagnant avant de finir perdant ?)."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "or"))
from base import load
L0, P0 = pd.Timestamp("2025-11-03"), pd.Timestamp("2023-01-01")
X = pd.read_pickle(os.path.join(HERE, "meta_preds.pkl"))
NOMS = {"ORB15dir_DAX:DE40": "DAX 1re bougie", "BRUIT_DAX:DE40": "DAX zone de bruit", "IB_OR:XAUUSD": "Or Initial Balance"}
b = X[X.ligne.isin(NOMS) & (X.tend > 0)].copy()
b = b[~((b.ligne == "ORB15dir_DAX:DE40") & ((b.risk_atr > 0.189) | (b.jour == 0)))]
b["ligne"] = b.ligne.map(NOMS)
b["sens_tend"] = 1  # filtre de tendance : toujours dans le sens
b = b[["symbol", "ligne", "side", "open_time", "close_time", "entry", "exit", "risk", "R", "day", "vol", "ecart_ma", "deja", "mom5", "risk_atr", "heure", "jour", "atr"]]
# or tendance du jour (bougies 1 h, cout 0,15)
os.environ["OR_COST"] = "0.15"
import or_sessions as O
rows = []
for day in O.G.index[O.G.index >= P0]:
    r = O.G.loc[day]
    if np.isnan(r.atr) or np.isnan(r.sma20): continue
    bb = O.bars(day, 10, 22)
    if len(bb) < 9 or bb.h.iloc[0] != 10: continue
    side = int(np.sign(r.pc - r.sma20)); e = bb.open.iloc[0]; rk = 0.5 * r.atr
    x, t1 = bb.close.iloc[-1], bb.index[-1] + pd.Timedelta(hours=1)
    for t, hh, ll in zip(bb.index, bb.high.values, bb.low.values):
        if side == 1 and ll <= e - rk: x, t1 = e - rk, t + pd.Timedelta(minutes=30); break
        if side == -1 and hh >= e + rk: x, t1 = e + rk, t + pd.Timedelta(minutes=30); break
    i = O.G.index.get_loc(day)
    c5 = O.G.c.iloc[i - 6] if i >= 6 else np.nan
    atr100 = O.G.atr.iloc[max(0, i - 100):i].mean()
    rows.append(dict(symbol="XAUUSD", ligne="Or tendance du jour", side=side, open_time=bb.index[0], close_time=t1, entry=e, exit=x,
                     risk=rk, R=(side * (x - e) - 0.15) / rk, day=day, vol=r.atr / atr100 if atr100 else np.nan,
                     ecart_ma=side * (r.pc - r.sma20) / r.atr, deja=side * (e - r.pc) / r.atr, mom5=side * (r.pc - c5) / r.atr,
                     risk_atr=0.5, heure=10, jour=day.dayofweek, atr=r.atr))
T = pd.concat([b, pd.DataFrame(rows)], ignore_index=True)
T = T[(T.day >= P0) & (T.day <= pd.Timestamp("2026-11-02"))].copy()
T["per"] = np.where(T.day >= L0, "L", "P")
# excursion : meilleur gain latent (MFE) avant la sortie, en R, sur bougies 15 min
mfe = []
for r in T.itertuples():
    d = load(r.symbol)
    w = d[(d.index >= r.open_time) & (d.index < r.close_time)]
    if len(w) == 0: mfe.append(np.nan); continue
    best = (w.high.max() - r.entry) if r.side == 1 else (r.entry - w.low.min())
    mfe.append(best / r.risk)
T["mfe"] = mfe
T["stop"] = T.R <= -0.95
T.to_pickle(os.path.join(HERE, "pertes_trades.pkl"))
print(T.groupby(["ligne", "per"]).R.agg(n="size", eur=lambda x: round(x.sum() * 100), gagn=lambda x: round(100 * (x > 0).mean())).unstack("per"))
