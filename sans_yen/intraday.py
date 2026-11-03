"""
Day trading SANS YEN : strategies intraday documentees, toutes fermees le jour meme.
Heures = heure serveur MT5 (GMT+2 / +3) : ouverture US = 16h30, ouverture Xetra (DAX) = 10h, Londres = 9-10h.
Meme protocole : conception 2012-17, validation 2018-21, test final 2022-03 -> 2026-10.
"""
import numpy as np, pandas as pd
from recherche import load, daily, atr, mk, period, INDICES, HERE, os

def range_breakout(sym, df, rng_h, entry_h, exit_h, stop="other", trend=False, both=True, min_r=0.15, max_r=1.5):
    """Cassure de range : range = bougies dont l'heure est dans rng_h ; ordres stop pendant entry_h ;
    stop de l'autre cote du range (ou au milieu) ; sortie a la cloture de la bougie exit_h. 1 trade/jour."""
    d = daily(df); da = atr(d, 14).shift(); ma = d.close.rolling(20).mean().shift()
    prevc = d.close.shift()
    out = []
    for day, g in df.groupby(df.index.date):
        D = pd.Timestamp(day); a = da.get(D, np.nan)
        if np.isnan(a): continue
        r = g[(g.index.hour >= rng_h[0]) & (g.index.hour <= rng_h[1])]
        if len(r) < (rng_h[1] - rng_h[0] + 1) * 0.6: continue
        hi, lo = r.high.max(), r.low.min()
        if not (min_r * a <= hi - lo <= max_r * a): continue
        allow_long = allow_short = True
        if trend:
            m = ma.get(D, np.nan)
            if np.isnan(m): continue
            allow_long, allow_short = prevc[D] > m, prevc[D] < m
        if not both: allow_short = False
        mid = (hi + lo) / 2
        pos = None
        for t, (o, h, l, c) in zip(g.index, g[["open", "high", "low", "close"]].values):
            hr = t.hour
            if pos is None:
                if hr < entry_h[0] or hr > entry_h[1]: continue
                hb, hs = allow_long and h >= hi, allow_short and l <= lo
                if hb and hs:
                    hb = abs(hi - o) <= abs(o - lo); hs = not hb
                if hb:
                    e = max(o, hi); sl = lo if stop == "other" else mid; pos = (1, e, sl, e - sl, t)
                elif hs:
                    e = min(o, lo); sl = hi if stop == "other" else mid; pos = (-1, e, sl, sl - e, t)
                else: continue
                if pos[3] <= 0: pos = None; continue
            sd, e, sl, rk, t0 = pos
            if (sd == 1 and l <= sl) or (sd == -1 and h >= sl):
                out.append(mk(sym, sd, t0, t, e, sl, rk)); pos = None; break
            if hr >= exit_h:
                out.append(mk(sym, sd, t0, t, e, c, rk)); pos = None; break
        if pos is not None:
            sd, e, sl, rk, t0 = pos
            out.append(mk(sym, sd, t0, g.index[-1], e, g.close.iloc[-1], rk))
    return out

def gap_fade(sym, df, k=0.2):
    """Contre-gap a l'ouverture US : si l'indice ouvre loin de la cloture de la veille (> k ATR), on joue
    le retour vers la cloture de la veille (objectif), stop = 1 gap au-dela, sortie 22h."""
    d = daily(df); da = atr(d, 14).shift()
    out = []; prev = None
    for day, g in df.groupby(df.index.date):
        D = pd.Timestamp(day); a = da.get(D, np.nan)
        b16 = g[g.index.hour == 16]
        if prev is not None and not np.isnan(a) and not b16.empty:
            o = b16.open.iloc[0]; gap = o - prev
            if abs(gap) > k * a:
                sd = -1 if gap > 0 else 1; rk = max(abs(gap), 0.2 * a); sl = o - sd * rk; tp = prev
                for t, (oo, h, l, c) in zip(g.index[g.index.hour >= 16], g[g.index.hour >= 16][["open", "high", "low", "close"]].values):
                    if (sd == 1 and l <= sl) or (sd == -1 and h >= sl):
                        out.append(mk(sym, sd, b16.index[0], t, o, sl, rk)); break
                    if (sd == 1 and h >= tp) or (sd == -1 and l <= tp):
                        out.append(mk(sym, sd, b16.index[0], t, o, tp, rk)); break
                    if t.hour >= 22:
                        out.append(mk(sym, sd, b16.index[0], t, o, c, rk)); break
        last = g[g.index.hour <= 22]
        if not last.empty: prev = last.close.iloc[-1]
    return out

US = ["US500", "US30", "USTECH100M"]
FXM = ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "EURGBP", "EURCHF", "XAUUSD", "XAGUSD"]
CANDS = {
    "ORB_US":        (US, lambda s, d: range_breakout(s, d, (16, 16), (17, 21), 22)),
    "ORB_US_mid":    (US, lambda s, d: range_breakout(s, d, (16, 16), (17, 21), 22, stop="mid")),
    "ORB_US_trend":  (US, lambda s, d: range_breakout(s, d, (16, 16), (17, 21), 22, trend=True)),
    "ORB_DAX":       (["DE40"], lambda s, d: range_breakout(s, d, (10, 10), (11, 17), 18)),
    "ORB_DAX_mid":   (["DE40"], lambda s, d: range_breakout(s, d, (10, 10), (11, 17), 18, stop="mid")),
    "ORB_DAX_trend": (["DE40"], lambda s, d: range_breakout(s, d, (10, 10), (11, 17), 18, trend=True)),
    "LONDON":        (FXM, lambda s, d: range_breakout(s, d, (0, 8), (9, 17), 22, max_r=1.2)),
    "LONDON_trend":  (FXM, lambda s, d: range_breakout(s, d, (0, 8), (9, 17), 22, trend=True, max_r=1.2)),
    "NY_BRK":        (FXM, lambda s, d: range_breakout(s, d, (9, 15), (16, 20), 22, max_r=1.2)),
    "GAP_FADE":      (US + ["DE40"], gap_fade),
}

if __name__ == "__main__":
    data = {}; allt = []
    for st, (mkts, fn) in CANDS.items():
        for s in mkts:
            if s not in data: data[s] = load(s)
            t = pd.DataFrame(fn(s, data[s]))
            if t.empty: continue
            t["strat"] = st; allt.append(t)
    T = pd.concat(allt); T["periode"] = period(T.open_time); T["ligne"] = T.strat + ":" + T.symbol
    T.to_pickle(os.path.join(HERE, "intraday_trades.pkl"))
    g = T[T.periode != "gap"].groupby(["ligne", "periode"]).R.agg(["count", "mean"]).unstack()
    pd.set_option("display.width", 250)
    print(g.round(3).to_string())
