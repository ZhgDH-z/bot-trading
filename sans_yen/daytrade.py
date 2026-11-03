"""
DAY TRADING sans yen, bougies 15 minutes (export MT5 d'aurele, 2022 -> oct. 2026).
Tout est ferme le jour meme. Heures serveur : ouverture US 16h30, Xetra 10h00, Londres 10h00 (9h GMT+1...).
Protocole : CONCEPTION = debut des donnees -> 30/06/2024, TEST FINAL = 01/07/2024 -> 30/10/2026 (jamais regarde).
"""
import os, sys
import numpy as np, pandas as pd
from recherche import mk, atr, daily, HERE, SPREAD, INDICES

M15 = os.path.join(HERE, "..", "data_m15")
SPLIT = pd.Timestamp("2024-07-01")

def load15(sym):
    d = pd.read_csv(os.path.join(M15, f"{sym}_M15.csv"))
    d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M")
    d = d.set_index("time")
    return d[d.index.dayofweek < 5]

def hm(t): return t.hour * 100 + t.minute

def session_breakout(sym, df, rng, entry, exit_, stop="other", one_dir=None, tgt=None, min_r=0.05, max_r=1.0):
    """rng=(debut,fin) en HHMM inclusifs des bougies du range ; entry=(debut,fin) ; sortie a la bougie exit_.
    one_dir='candle' : on ne prend que le sens de la bougie d'ouverture (Zarattini & Aziz 2023)."""
    d = daily(df); da = atr(d, 14).shift()
    out = []
    for day, g in df.groupby(df.index.date):
        a = da.get(pd.Timestamp(day), np.nan)
        if np.isnan(a): continue
        k = np.array([hm(t) for t in g.index])
        r = g[(k >= rng[0]) & (k <= rng[1])]
        if r.empty: continue
        hi, lo = r.high.max(), r.low.min()
        if not (min_r * a <= hi - lo <= max_r * a): continue
        okL = okS = True
        if one_dir == "candle":
            up = r.close.iloc[-1] > r.open.iloc[0]
            okL, okS = up, not up
        pos = None
        sub = g[k > rng[1]]
        for t, (o, h, l, c) in zip(sub.index, sub[["open", "high", "low", "close"]].values):
            x = hm(t)
            if pos is None:
                if x < entry[0] or x > entry[1]: continue
                if one_dir == "candle":   # entree directe au marche a la 1re bougie apres le range
                    sd = 1 if okL else -1; e = o
                    sl = lo if sd == 1 else hi
                else:
                    hb, hs = okL and h >= hi, okS and l <= lo
                    if hb and hs: hb = abs(hi - o) <= abs(o - lo); hs = not hb
                    if not (hb or hs): continue
                    sd = 1 if hb else -1; e = max(o, hi) if hb else min(o, lo)
                    sl = (lo if sd == 1 else hi) if stop == "other" else (hi + lo) / 2
                rk = sd * (e - sl)
                if rk <= 0.02 * a: break
                pos = (sd, e, sl, rk, t, e + sd * tgt * rk if tgt else None)
            sd, e, sl, rk, t0, tp = pos
            if (sd == 1 and l <= sl) or (sd == -1 and h >= sl):
                out.append(mk(sym, sd, t0, t, e, min(o, sl) if sd == 1 else max(o, sl), rk)); pos = None; break
            if tp is not None and ((sd == 1 and h >= tp) or (sd == -1 and l <= tp)):
                out.append(mk(sym, sd, t0, t, e, tp, rk)); pos = None; break
            if x >= exit_:
                out.append(mk(sym, sd, t0, t, e, c, rk)); pos = None; break
        if pos is not None:
            sd, e, sl, rk, t0, tp = pos
            out.append(mk(sym, sd, t0, sub.index[-1], e, sub.close.iloc[-1], rk))
    return out

def vwap_fade(sym, df, start, last_entry, exit_, k=1.0):
    """Retour a la VWAP (prix moyen pondere par le volume de ticks depuis l'ouverture de la seance) :
    si le prix s'ecarte de plus de k x ATR(M15,14)*4 de la VWAP, on joue le retour. Stop = meme ecart au-dela."""
    a15 = atr(df, 14)
    out = []
    for day, g in df.groupby(df.index.date):
        kk = np.array([hm(t) for t in g.index])
        s = g[kk >= start]
        if len(s) < 4: continue
        tp_ = (s.high + s.low + s.close) / 3
        vw = (tp_ * s.tick_volume).cumsum() / s.tick_volume.cumsum().replace(0, np.nan)
        pos = None
        idx = s.index
        for j in range(1, len(s)):
            t = idx[j]; x = hm(t); o, h, l, c = s.open.iloc[j], s.high.iloc[j], s.low.iloc[j], s.close.iloc[j]
            if pos is None:
                if x > last_entry: break
                dev = s.close.iloc[j-1] - vw.iloc[j-1]; band = k * 4 * a15.loc[idx[j-1]]
                if abs(dev) < band or np.isnan(band): continue
                sd = -1 if dev > 0 else 1; e = o; rk = abs(dev); sl = e - sd * rk
                pos = [sd, e, sl, rk, t]
            sd, e, sl, rk, t0 = pos
            if (sd == 1 and l <= sl) or (sd == -1 and h >= sl):
                out.append(mk(sym, sd, t0, t, e, sl, rk)); pos = None; break
            target = vw.iloc[j-1]
            if (sd == 1 and h >= target) or (sd == -1 and l <= target):
                out.append(mk(sym, sd, t0, t, e, max(target, o) if sd == 1 else min(target, o), rk)); pos = None; break
            if x >= exit_:
                out.append(mk(sym, sd, t0, t, e, c, rk)); pos = None; break
        if pos is not None:
            sd, e, sl, rk, t0 = pos
            out.append(mk(sym, sd, t0, s.index[-1], e, s.close.iloc[-1], rk))
    return out

US = ["US500", "US30", "USTECH100M"]
FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "EURGBP", "EURCHF", "XAUUSD", "XAGUSD"]
CANDS = {
    # Cassure de la 1re demi-heure US (ORB 30 min), stop de l'autre cote, sortie 22h45
    "ORB30_US":     (US, lambda s, d: session_breakout(s, d, (1630, 1645), (1700, 2000), 2245)),
    # ORB 15 min dans le sens de la 1re bougie (Zarattini & Aziz 2023, "Can Day Trading Really Be Profitable?")
    "ORB15dir_US":  (US, lambda s, d: session_breakout(s, d, (1630, 1630), (1645, 1645), 2245, one_dir="candle")),
    "ORB15dir_US_10R": (US, lambda s, d: session_breakout(s, d, (1630, 1630), (1645, 1645), 2245, one_dir="candle", tgt=10)),
    # DAX : cassure de la 1re demi-heure Xetra
    "ORB30_DAX":    (["DE40"], lambda s, d: session_breakout(s, d, (1000, 1015), (1030, 1400), 1815)),
    "ORB15dir_DAX": (["DE40"], lambda s, d: session_breakout(s, d, (1000, 1000), (1015, 1015), 1815, one_dir="candle")),
    # Londres : range asiatique 00h-09h45, cassure 10h-13h, sortie 22h45, objectif 1 R ou fin de journee
    "LONDON15":     (FX, lambda s, d: session_breakout(s, d, (0, 945), (1000, 1300), 2245, max_r=1.2)),
    "LONDON15_1R":  (FX, lambda s, d: session_breakout(s, d, (0, 945), (1000, 1300), 2245, max_r=1.2, tgt=1)),
    # Retour a la VWAP pendant la seance US / europeenne
    "VWAP_US":      (US, lambda s, d: vwap_fade(s, d, 1630, 2100, 2245)),
    "VWAP_DAX":     (["DE40"], lambda s, d: vwap_fade(s, d, 1000, 1630, 1815)),
    "VWAP_FX":      (FX, lambda s, d: vwap_fade(s, d, 1000, 1800, 2245)),
}

if __name__ == "__main__":
    data, allt = {}, []
    for st, (mkts, fn) in CANDS.items():
        for s in mkts:
            if s not in data: data[s] = load15(s)
            t = pd.DataFrame(fn(s, data[s]))
            if t.empty: continue
            t["strat"] = st; allt.append(t)
    T = pd.concat(allt); T["ligne"] = T.strat + ":" + T.symbol
    T["periode"] = np.where(T.open_time < SPLIT, "A_conception", "B_test")
    T.to_pickle(os.path.join(HERE, "daytrade_trades.pkl"))
    g = T.groupby(["ligne", "periode"]).R.agg(["count", "mean"]).unstack()
    pd.set_option("display.width", 250)
    print(g.round(3).to_string())
    for s, d in data.items(): print(s, d.index[0].date(), end=" | ")
