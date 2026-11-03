"""Supertrend DAX 15 min : réglage choisi sur P, vérifié sur L ; hasard ; chevauchement avec la v1.03 ; portefeuille."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fs_robuste as FR
L0 = FR.L0
res = {}
for m in [3.0, 3.5, 4.0]:
    s = FR.sig("supertrend", m)
    for k in [1.25, 1.5, 1.75]:
        o = FR.run(s, k); P, L = o[o.day < L0], o[o.day >= L0]
        res[(m, k)] = o
        print(f"mult {m} stop {k} ATR : P {len(P)} trades {P.R.sum()*1000:+8.0f} €  | L {len(L)} trades {L.R.sum()*1000:+8.0f} €, {100*(L.R>0).mean():.0f} % gagnants")
best = max(res, key=lambda x: res[x][res[x].day < L0].R.sum())
print("Choisi sur P :", best)
o = res[best]
# hasard : mêmes heures d'entrée et de sortie, sens tiré au hasard (approx. : R inversé si le sens change, sans stop)
rng = np.random.default_rng(7); Ls = o[o.day >= L0].R.values; Ps = o[o.day < L0].R.values
def rand(x):
    return np.array([(x * rng.choice([-1, 1], len(x))).sum() for _ in range(3000)]) * 1000
for nom, x in [("P", Ps), ("L", Ls)]:
    r = rand(x); print(f"hasard {nom} : réel {x.sum()*1000:+.0f} €, hasard moyen {r.mean():+.0f} €, part du hasard >= réel {np.mean(r >= x.sum()*1000):.3f}")
o.to_pickle(os.path.join(HERE, "supertrend_trades.pkl"))
# chevauchement et portefeuille avec la v1.03
V = pd.read_pickle(os.path.join(HERE, "v103_trades.pkl")); V["day"] = pd.to_datetime(V.day)
for per, a, b in [("P", V[V.per == "P"], o[o.day < L0]), ("L", V[V.per == "L"], o[o.day >= L0])]:
    da = a.groupby("day").R.sum() * 1000; db = b.groupby("day").R.sum() * 1000
    j = pd.concat([da, db], axis=1).fillna(0); j.columns = ["v103", "st"]
    print(per, "corrélation jour par jour avec la v1.03 :", round(j.corr().iloc[0, 1], 2))
    zb = a[a.ligne == "DAX zone de bruit"].groupby("day").R.sum(); jj = pd.concat([zb, b.groupby("day").R.sum()], axis=1).fillna(0)
    print(per, "corrélation avec DAX zone de bruit :", round(jj.corr().iloc[0, 1], 2))
    for nom, s in [("v1.03", j.v103), ("v1.03 + supertrend", j.v103 + j.st)]:
        cum = s.cumsum(); dd = (cum - cum.cummax()).min()
        mo = s.groupby(s.index.to_period("M")).sum()
        print(f"   {nom:20s} total {s.sum():+9.0f} €  pire baisse {dd:+8.0f} €  mois gagnants {(mo>0).sum()}/{len(mo)}  pire mois {mo.min():+.0f} €")
