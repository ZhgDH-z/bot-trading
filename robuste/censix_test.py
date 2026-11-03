"""Test de censix/INTRADAY-PartAB (03/11/2026). Chaine d'execution R pour Interactive Brokers (2015), avec 2 strategies
'dummy' (exemples, selon l'auteur), prevues sur bougies de 30-60 secondes, tout ferme a 22:04 :
 BBANDS   : Bollinger(10, 1,1 ecart-type) ; achat si cloture < bande basse, vente si > bande haute ; sortie a la moyenne.
 BREAKOUT : achat si cloture > plus haut des N bougies precedentes, vente si < plus bas ; sortie quand la cloture
            repasse la moyenne N (N = 20 dans userStrategyEvents.r, 200 dans le fichier exemple).
Pas de stop dans l'original. Adaptation : bougies M15, signal a la cloture, execution a l'ouverture suivante,
une position a la fois, tout ferme en fin de seance. 'R' : taille telle qu'un mouvement de 0,3 x ATR jour = 100 EUR
(meme echelle que nos autres tests). Variante '+stop' : stop a 0,3 x ATR jour.
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from base import load, cost, summary, daily_atr
SESS = {"DE40": (1000, 1815), "XAUUSD": (1000, 2245), "US500": (1630, 2245), "USTECH100M": (1630, 2245), "US30": (1630, 2245),
        "EURUSD": (1000, 2245), "GBPUSD": (1000, 2245)}

def run(sym, strat, N, use_stop=False, stop_k=1.0):
    d = load(sym).copy(); cst = cost(sym); s0, s1 = SESS[sym]
    c = d.close
    if strat == "bb":
        m = c.rolling(10).mean(); sd = c.rolling(10).std(ddof=0); up, dn, mid = m + 1.1 * sd, m - 1.1 * sd, m
    else:
        up = d.high.rolling(N).max().shift(); dn = d.low.rolling(N).min().shift(); mid = c.rolling(N).mean().shift()
    at = d.day.map(daily_atr(sym)).values
    o, h, l, cl, hm, day = d.open.values, d.high.values, d.low.values, c.values, d.hm.values, d.day.values
    up, dn, mid = up.values, dn.values, mid.values
    T = []; pos = 0; pend = 0; pexit = False
    for i in range(1, len(d)):
        if pos and (pexit or day[i] != day[ei] or hm[i] > s1):
            ex = o[i] if day[i] == day[ei] else cl[i - 1]
            g = (ex - ep) * pos / risk
            T.append(dict(day=pd.Timestamp(day[ei]), t=d.index[ei], tx=d.index[i], side=pos, R_gross=g, cost_R=cst / risk, R=g - cst / risk))
            pos = 0; pexit = False; pend = 0
            continue
        if pos and use_stop and ((pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl)):
            g = (sl - ep) * pos / risk   # = -1 R
            T.append(dict(day=pd.Timestamp(day[ei]), t=d.index[ei], tx=d.index[i], side=pos, R_gross=g, cost_R=cst / risk, R=g - cst / risk))
            pos = 0; pend = 0
            continue
        if not pos and pend and s0 <= hm[i] < s1 and day[i] == day[i - 1] and not np.isnan(at[i]):
            pos = pend; ep = o[i]; ei = i; risk = 0.3 * at[i] * (stop_k if use_stop else 1.0); sl = ep - pos * risk   # avec stop : 1 R = distance du stop
        pend = 0
        if np.isnan(mid[i]): continue
        if pos:
            if strat == "bb": pexit = (pos == 1 and cl[i] >= mid[i]) or (pos == -1 and cl[i] <= mid[i])
            else:             pexit = (pos == 1 and cl[i] <= mid[i]) or (pos == -1 and cl[i] >= mid[i])
        elif s0 <= hm[i] < s1:
            if strat == "bb": pend = 1 if cl[i] < dn[i] else -1 if cl[i] > up[i] else 0
            else:             pend = 1 if cl[i] > up[i] else -1 if cl[i] < dn[i] else 0
    T = pd.DataFrame(T); T["sym"] = sym
    return T

if __name__ == "__main__":
    rows, allt = [], []
    for name, strat, N, st in (("BBANDS", "bb", 10, False), ("BREAKOUT20", "bo", 20, False), ("BREAKOUT200", "bo", 200, False),
                               ("BBANDS+stop", "bb", 10, True), ("BREAKOUT20+stop", "bo", 20, True), ("BREAKOUT200+stop0,6ATR", "bo", 200, True)):
        for sym in SESS:
            T = run(sym, strat, N, st, 2.0 if N == 200 else 1.0); T["variante"] = name; allt.append(T); rows.append(summary(T, f"{sym} {name}"))
    pd.set_option("display.width", 200); print(pd.DataFrame(rows).to_string())
    A = pd.concat(allt); A["eur"] = (A.R * 100).round(0); A.to_pickle(os.path.join(HERE, "censix_trades.pkl"))
    A.assign(side=A.side.map({1: "achat", -1: "vente"}))[["variante", "sym", "t", "side", "eur"]].to_csv(os.path.join(HERE, "censix_tous_trades.csv"), index=False)
