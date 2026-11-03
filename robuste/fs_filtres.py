"""Idées du dépôt finance-skills (himself65), testées sur les trades v1.03 (03/11/2026).
F1 alignement multi-unités de temps (tradingview-mcp) ; F2 mouvement de nuit des indices US (futures overnight) ;
F3 modèle de tendance Minervini (sepa-strategy). Choix sur P, vérification sur L, 1 000 € par trade."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from base import load
T = pd.read_pickle(os.path.join(HERE, "v103_trades.pkl")).copy()
T["day"] = pd.to_datetime(T.day)

def tf_trend(sym, rule, n=20):
    d = load(sym)
    c = d.close.resample(rule, label="left", closed="left").last().dropna()
    e = c.ewm(span=n, adjust=False).mean()
    s = np.sign(c - e)
    s.index = s.index + pd.Timedelta(rule)       # connu à la fin de la bougie
    return s
def at(series, times):
    idx = series.index.searchsorted(times, side="right") - 1
    out = np.where(idx >= 0, series.values[np.clip(idx, 0, None)], np.nan)
    return out
rows = {}
for sym in T.symbol.unique():
    m = T.symbol == sym
    for rule in ["1h", "4h"]:
        T.loc[m, "t" + rule] = at(tf_trend(sym, rule), T.loc[m, "open_time"].values) * T.loc[m, "side"]
    # SEPA : clôture d'hier vs MM50, MM150, MM200
    d = load(sym); D = d.close.groupby(d.day).last()
    m50, m150, m200 = D.rolling(50).mean(), D.rolling(150).mean(), D.rolling(200).mean()
    up = ((D > m50) & (m50 > m150) & (m150 > m200)).shift(); dn = ((D < m50) & (m50 < m150) & (m150 < m200)).shift()
    up2 = ((D > m50) & (m50 > m200)).shift(); dn2 = ((D < m50) & (m50 < m200)).shift()
    dd = T.loc[m, "day"]; sd = T.loc[m, "side"]
    T.loc[m, "sepa"] = np.where(sd > 0, up.reindex(dd).values, dn.reindex(dd).values)
    T.loc[m, "sepa2"] = np.where(sd > 0, up2.reindex(dd).values, dn2.reindex(dd).values)
# F2 : nuit US = US500 de 23:00 serveur la veille à 09:45 serveur
u = load("US500")
def us_night(day):
    a = u[(u.index < day) & (u.hm <= 2245)].close
    b = u[(u.index >= day) & (u.index < day + pd.Timedelta("09:45:00"))].close
    if not len(a) or not len(b): return np.nan
    return np.sign(b.iloc[-1] - a.iloc[-1])
nights = {d: us_night(d) for d in T.day.unique()}
T["usn"] = T.day.map(nights) * T.side
base = {p: T[T.per == p].R.sum() * 1000 for p in "PL"}
print("Base v1.03 : P %+.0f €  L %+.0f €" % (base["P"], base["L"]))
tests = {
 "H1 dans le sens du trade": T.t1h > 0, "H4 dans le sens du trade": T.t4h > 0, "H1 ET H4 dans le sens": (T.t1h > 0) & (T.t4h > 0),
 "Nuit US dans le sens (DAX seulement)": (T.symbol != "DE40") | (T.usn > 0), "Nuit US dans le sens (tout)": T.usn > 0,
 "Minervini strict (MM50>150>200)": T.sepa == True, "Minervini simple (MM50>200)": T.sepa2 == True,
}
for nom, keep in tests.items():
    for scope, sm in [("tout", T.symbol.notna()), ("DAX", T.symbol == "DE40"), ("or", T.symbol == "XAUUSD")]:
        k = keep | ~sm
        r = {p: (T[(T.per == p) & k].R.sum() * 1000 - base[p], int(((T.per == p) & ~k).sum())) for p in "PL"}
        print(f"{nom:38s} {scope:5s} P {r['P'][0]:+8.0f} € ({r['P'][1]:3d} retirés)  L {r['L'][0]:+8.0f} € ({r['L'][1]:3d} retirés)")
