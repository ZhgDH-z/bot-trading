"""Base commune de la recherche 'strategie robuste' (02/11/2026).
Regles fixees AVANT de regarder les resultats :
 - periode A = 2022 -> 31/12/2024, periode B = 01/01/2025 -> 02/11/2026 : il faut gagner sur les DEUX ;
 - couts prudents : table SPREAD x 1,2 (plus large que les spreads de la demo) ;
 - 100 EUR de risque par trade (gain = R x 100 EUR) ;
 - comparaison au hasard : memes trades, sens tire au hasard (5 000 tirages) ;
 - variantes voisines testees aussi : une regle qui ne marche que pour un reglage precis est rejetee.
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sans_yen"))
from recherche import SPREAD, INDICES  # noqa
M15 = os.path.join(HERE, "..", "data_m15")
A_END = pd.Timestamp("2025-01-01")
MKTS = ["US500", "USTECH100M", "US30", "DE40", "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "EURGBP", "EURCHF"]

_cache = {}
def load(sym):
    if sym not in _cache:
        d = pd.read_csv(os.path.join(M15, f"{sym}_M15.csv"))
        d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M")
        d = d.set_index("time")
        d = d[d.index.dayofweek < 5]
        d["hm"] = d.index.hour * 100 + d.index.minute
        d["day"] = d.index.normalize()
        _cache[sym] = d
    return _cache[sym]

def daily_atr(sym, n=14):
    d = load(sym)
    g = d.groupby("day").agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = g.c.shift()
    tr = pd.concat([g.h - g.l, (g.h - pc).abs(), (g.l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean().shift()   # connu la veille

def cost(sym): return SPREAD[sym] * 1.2

def summary(T, label=""):
    """T : DataFrame avec colonnes day, side, R. Retourne un dict de stats."""
    if len(T) == 0:
        return dict(label=label, n=0)
    A, B = T[T.day < A_END], T[T.day >= A_END]
    rng = np.random.default_rng(1)
    absR = T.R_gross.abs().values if "R_gross" in T else None
    out = dict(label=label, n=len(T), parjour=round(len(T) / T.day.nunique(), 2) if len(T) else 0,
               eurA=round(A.R.sum() * 100), eurB=round(B.R.sum() * 100), eur=round(T.R.sum() * 100),
               moyR=round(T.R.mean(), 3), gagn=round((T.R > 0).mean() * 100))
    # hasard : on garde les memes trades mais on tire le sens au hasard
    if "R_gross" in T:
        g = T.R_gross.values; c = T.cost_R.values
        sims = np.array([(g * rng.choice([-1, 1], len(g)) - c).sum() for _ in range(5000)])
        out["p_hasard"] = round(float((sims >= T.R.sum()).mean()), 4)
    eq = T.sort_values("day").R.cumsum() * 100
    out["pire_baisse"] = round(float((eq - eq.cummax()).min()))
    return out
