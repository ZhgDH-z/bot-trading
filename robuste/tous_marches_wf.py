"""Version qui ÉVOLUE : chaque mois, pour chaque marché, le bot regarde les 12 mois passés et prend la stratégie
du menu qui a le mieux marché (conditions : >= 20 trades, gain moyen >= 0,03 R, les 2 semestres gagnants).
Rien de valable : il ne trade pas ce marché ce mois-là. Jamais de données futures."""
import os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
A = pd.read_pickle(os.path.join(HERE, "tous_marches_all.pkl"))
L0 = pd.Timestamp("2025-11-03")
def wf(look=12, nmin=20, moy=0.03):
    out = []
    for M in pd.date_range("2024-01-01", "2026-11-01", freq="MS"):
        a, mid, b = M - pd.DateOffset(months=look), M - pd.DateOffset(months=look // 2), M + pd.DateOffset(months=1)
        for sym, res in A.items():
            best, bs = None, 0
            for nom, t in res.items():
                h = t[(t.day >= a) & (t.day < M)]
                if len(h) < nmin or h.R.mean() < moy: continue
                if h[h.day < mid].R.sum() <= 0 or h[h.day >= mid].R.sum() <= 0: continue
                if h.R.sum() > bs: best, bs = nom, h.R.sum()
            if best:
                t = res[best]; f = t[(t.day >= M) & (t.day < b)].copy(); f["strat"] = best; out.append(f)
    T = pd.concat(out); T = T[T.day <= pd.Timestamp("2026-11-02")]; return T
if __name__ == "__main__":
    for look in (6, 12, 24):
        T = wf(look); P, L = T[T.day < L0], T[T.day >= L0]
        print(f"regard {look} mois : avant (01/2024-02/11/2025) {len(P)} trades {P.R.sum()*1000:+.0f} € | dernière année {len(L)} trades {L.R.sum()*1000:+.0f} €")
    T = wf(12); T.to_pickle(os.path.join(HERE, "tous_marches_wf.pkl")); L = T[T.day >= L0]
    print(L.groupby("symbol").R.agg(n="size", eur=lambda x: round(x.sum() * 1000)).sort_values("eur").to_string())
