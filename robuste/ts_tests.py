"""Règles du dépôt trade-skills (pièges 4, 27, 30, 31) testées sur la v1.05 (03/11/2026). P puis L, 1 000 €/trade."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from base import load, daily_atr, cost
L0 = pd.Timestamp("2025-11-03")
V = pd.read_pickle(os.path.join(HERE, "v103_trades.pkl")); V["day"] = pd.to_datetime(V.day)
# garde-fou v1.04
keep = []
for sym, g in V.groupby("symbol"):
    d = load(sym); med = d.spread_points.rolling(1920, min_periods=96).median(); bar = g.open_time - pd.Timedelta(minutes=15)
    sp, md = d.spread_points.reindex(bar).values, med.reindex(bar).values
    keep.append(pd.Series(~((md > 0) & (sp > 2 * md)), index=g.index))
V = V[pd.concat(keep).reindex(V.index).values]
S = pd.read_pickle(os.path.join(HERE, "supertrend_trades.pkl")).rename(columns={"t0": "open_time", "t1": "close_time"})
S["ligne"] = "DAX supertrend"; S["symbol"] = "DE40"; S["per"] = np.where(S.day >= L0, "L", "P")
T = pd.concat([V[["ligne", "symbol", "side", "open_time", "close_time", "day", "R", "per", "risk", "entry", "risk_atr", "atr"]], S[["ligne", "symbol", "open_time", "close_time", "day", "R", "per"]]], ignore_index=True)
T = T.sort_values("close_time").reset_index(drop=True)
def tot(df): return {p: round(df[df.per == p].R.sum() * 1000) for p in "PL"}
base = tot(T); print("Base v1.05 :", base, "trades", T.groupby("per").size().to_dict())
def show(nom, df):
    r = tot(df); print(f"{nom:58s} P {r['P']-base['P']:+8d} €   L {r['L']-base['L']:+8d} €   ({len(T)-len(df)} trades retirés)")
# --- Piège 31 : limite de perte du jour (en R), arrêt après N pertes de suite dans la journée, réduction selon la baisse
for lim in [2, 3, 4]:
    out = []
    for day, g in T.sort_values("open_time").groupby("day"):
        cum = 0.0
        for r in g.itertuples():
            if cum <= -lim: continue        # plus d'entrée
            out.append(r.Index); cum += r.R   # (approx. : le cumul compte les trades fermés dans l'ordre d'entrée)
    show(f"Limite de perte du jour {lim} R", T.loc[out])
for n in [2, 3]:
    out = []
    for day, g in T.sort_values("open_time").groupby("day"):
        streak = 0
        for r in g.itertuples():
            if streak >= n: continue
            out.append(r.Index); streak = streak + 1 if r.R < 0 else 0
    show(f"Arrêt pour la journée après {n} pertes de suite", T.loc[out])
# réduction de taille selon la baisse depuis le plus haut (capital 100 000 €, 1 000 € = 1 %)
for per in "PL":
    pass
def degear(df, tiers):
    eq = 100000.0; hi = eq; tot_ = 0.0
    for r in df.sort_values("close_time").itertuples():
        dd = (hi - eq) / hi; f = 1.0
        for lvl, fac in tiers:
            if dd >= lvl: f = fac
        g = r.R * 1000 * f; eq += g; hi = max(hi, eq); tot_ += g
    return round(tot_)
for per in "PL":
    df = T[T.per == per]
    print(f"Réduction de taille (-5 % : x0,75 ; -10 % : x0,5) sur {per} : {degear(df, [(0.05, 0.75), (0.10, 0.5)]) - base[per]:+d} €")
