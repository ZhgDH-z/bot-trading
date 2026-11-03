"""Candidats supplementaires (regles publiques, parametres fixes d'avance)."""
import numpy as np, pandas as pd
from recherche import *

def imom(sym, df):
    """Momentum intraday (Gao, Han, Li, Zhou 2018, J. Fin. Econ.) : le rendement depuis la cloture de la veille
    jusqu'a 1 h apres l'ouverture US predit le sens de la derniere heure. Entree 22h serveur, sortie 23h."""
    da = atr(df, 14)
    out = []
    g = df.groupby(df.index.date)
    prev_close = None
    for day, x in g:
        x = x
        o17 = x[x.index.hour == 17]; b22 = x[x.index.hour == 22]
        if prev_close is not None and not o17.empty and not b22.empty:
            ret = o17.open.iloc[0] - prev_close  # du close de la veille a 17h00 serveur (= 10h00 New York)
            sd = 1 if ret > 0 else -1
            e, xx = b22.open.iloc[0], b22.close.iloc[0]
            r = da.loc[b22.index[0]] * 1.0
            out.append(mk(sym, sd, b22.index[0], b22.index[0] + pd.Timedelta(minutes=59), e, xx, r))
        last = x[x.index.hour <= 22]
        prev_close = last.close.iloc[-1] if not last.empty else prev_close
    return out

def tom(sym, df):
    """Effet tournant du mois (Ariel 1987, Lakonishok-Smidt 1988) : achat a l'ouverture de l'avant-dernier
    jour ouvre du mois, vente a la cloture du 3e jour ouvre du mois suivant."""
    d = daily(df); a = atr(d, 20)
    d["ym"] = d.index.to_period("M")
    out = []
    months = list(d.groupby("ym"))
    for (m0, g0), (m1, g1) in zip(months[:-1], months[1:]):
        if len(g0) < 3 or len(g1) < 3: continue
        t0 = g0.index[-2]; t1 = g1.index[2]
        e, x = g0.open.iloc[-2], g1.close.iloc[2]
        r = 3 * a.shift().loc[t0]
        seg = d.loc[t0:t1]
        sl = e - r
        if (seg.low <= sl).any():
            x = sl
        out.append(mk(sym, 1, t0, t1 + pd.Timedelta(hours=23), e, x, r))
    return out

def rsi2_large(sym, df):
    return rsi2(sym, df, long_only=True, lo=25)

S2 = {"IMOM": imom, "TOM": tom, "RSI2_25": rsi2_large}
M2 = {"IMOM": list(INDICES), "TOM": list(INDICES), "RSI2_25": list(INDICES)}

if __name__ == "__main__":
    allt = []
    for st, mk_ in M2.items():
        for s in mk_:
            t = pd.DataFrame(S2[st](s, load(s))); t["strat"] = st; allt.append(t)
    T = pd.concat(allt); T["periode"] = period(T.open_time)
    T.to_pickle(os.path.join(HERE, "tous_trades2.pkl"))
    g = T[T.periode != "gap"].groupby(["strat", "symbol", "periode"]).R.agg(["count", "mean"]).unstack()
    print(g.round(3).to_string())
