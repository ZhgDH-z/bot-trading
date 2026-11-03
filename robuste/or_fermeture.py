"""v1.09 (03/11/2026) : heure de fermeture de l'or.
Depuis fin mars 2026, l'or ferme a 23h00 serveur (derniere bougie 15 min a 22h45).
Le robot ferme a 23h00 serveur -> trop tard : la position passe la nuit.
3 facons de sortir en fin de journee, memes entrees :
  A  test d'origine : cloture de la derniere bougie du jour (~23h00 serveur)
  B  bug en demo     : ouverture du lendemain (nuit tenue)
  D  22h45 serveur (ouverture de la derniere bougie), entrees ORBREAK jusqu a 22h30
  C  22h30 serveur (ouverture de la bougie de 22h30), pas d'entree ORBREAK apres 22h15
Lignes : ORTEND, ORIB (sans la sortie de moitie), ORBREAK. 100 EUR par trade, cout 0,15 $."""
import sys, numpy as np, pandas as pd
COST = 0.15
df = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "../data_m15/XAUUSD_M15.csv")
df["t"] = pd.to_datetime(df.time, format="%Y.%m.%d %H:%M")
df["d"] = df.t.dt.normalize(); df["hm"] = df.t.dt.hour * 100 + df.t.dt.minute
D = df.groupby("d").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"), c=("close", "last"))
tr = pd.concat([D.h - D.l, (D.h - D.c.shift()).abs(), (D.l - D.c.shift()).abs()], axis=1).max(axis=1)
atr = tr.copy(); atr.iloc[:14] = np.nan; atr.iloc[14] = tr.iloc[1:15].mean()
for k in range(15, len(tr)): atr.iloc[k] = (atr.iloc[k-1] * 13 + tr.iloc[k]) / 14
D["atr1"] = atr.shift(); D["c1"] = D.c.shift(); D["sma1"] = D.c.rolling(20).mean().shift()
D["c6"] = D.c.shift(6); D["rel"] = D.atr1 / atr.shift(2).rolling(100).mean()
days = list(D.index); byday = {d: g.reset_index(drop=True) for d, g in df.groupby("d")}

def finish(b, k0, side, e, stop, tp, d, mode):
    """parcourt les bougies k0.. du jour ; renvoie (prix de sortie, heure)"""
    for k in range(k0, len(b)):
        r = b.iloc[k]
        if mode == "C" and r.hm >= 2230: return r.open, r.t
        if mode == "D" and r.hm >= 2245: return r.open, r.t
        if side > 0 and r.low <= stop: return stop, r.t
        if side < 0 and r.high >= stop: return stop, r.t
        if tp and ((side > 0 and r.high >= tp) or (side < 0 and r.low <= tp)): return tp, r.t
    if mode in ("A", "C", "D"): return b.close.iloc[-1], b.t.iloc[-1]
    i = days.index(d)
    if i + 1 >= len(days): return b.close.iloc[-1], b.t.iloc[-1]
    n = byday[days[i + 1]].iloc[0]
    px = n.open
    if (side > 0 and px < stop) or (side < 0 and px > stop): px = n.open  # trou par-dessus le stop : rempli a l'ouverture
    return px, n.t

out = []
for d in days:
    r = D.loc[d]; b = byday[d]
    if np.isnan(r.atr1) or np.isnan(r.sma1): continue
    trend = 1 if r.c1 > r.sma1 else -1
    # ORTEND
    k = b.index[b.hm == 1000]
    if len(k) and not (r.rel > 1.2):
        k = k[0]; e = b.open[k]; rk = 0.5 * r.atr1
        for m in "ABCD":
            x, t1 = finish(b, k, trend, e, e - trend * rk, 0, d, m)
            out.append(("ORTEND", m, d, trend, b.t[k], t1, (trend * (x - e) - COST) / rk * 100))
    # ORIB
    ib = b[b.hm.isin([1630, 1645, 1700, 1715])]
    if len(ib) >= 3:
        hi, lo, op = ib.high.max(), ib.low.min(), ib.open.iloc[0]; w = hi - lo
        if 0.003 <= w / op <= 0.015:
            side = 0
            for k in b.index[(b.hm >= 1730) & (b.hm <= 2145)]:
                if b.high[k] > hi: side = 1
                elif b.low[k] < lo: side = -1
                if side: break
            if side and side == trend and side * (r.c1 - r.c6) >= 0:
                e = hi - 0.25 * w if side > 0 else lo + 0.25 * w; sl = e - side * 0.6 * w; tp = hi + 0.5 * w if side > 0 else lo - 0.5 * w
                f = None
                for j in range(k + 1, len(b)):
                    if b.hm[j] > 2200: break
                    if (side > 0 and b.low[j] <= e) or (side < 0 and b.high[j] >= e): f = j; break
                if f is not None:
                    for m in "ABCD":
                        if (m == "C" and b.hm[f] >= 2230) or (m == "D" and b.hm[f] >= 2245): continue
                        x, t1 = finish(b, f + 1, side, e, sl, tp, d, m)
                        if (side > 0 and b.low[f] <= sl) or (side < 0 and b.high[f] >= sl): x, t1 = sl, b.t[f]
                        out.append(("ORIB", m, d, side, b.t[f], t1, (side * (x - e) - COST) / (0.6 * w) * 100))
# ORBREAK (canal 200 bougies, toutes heures)
c, h, l, o, hm, t, dd = df.close.values, df.high.values, df.low.values, df.open.values, df.hm.values, df.t.values, df.d.values
N = 200
hh = pd.Series(h).rolling(N).max().shift(1).values; ll = pd.Series(l).rolling(N).min().shift(1).values
mid = pd.Series(c).rolling(N).mean().shift(1).values
atr1 = D.atr1.reindex(df.d).values
for m in "ABCD":
    pos = None; last_entry = {"C": 2230, "D": 2245}.get(m, 2245)
    for i in range(N + 1, len(df) - 1):
        if pos:
            side, e, sl, t0, rk = pos
            # stop pendant la bougie i
            hit = (side > 0 and l[i] <= sl) or (side < 0 and h[i] >= sl)
            if dd[i] != dd[i - 1]:      # nouveau jour avec une position de la veille (mode B)
                x = o[i]; out.append(("ORBREAK", m, pd.Timestamp(dd[i - 1]), side, t0, t[i], (side * (x - e) - COST) / rk * 100)); pos = None
            elif (m == "C" and hm[i] >= 2230) or (m == "D" and hm[i] >= 2245):
                x = o[i]; out.append(("ORBREAK", m, pd.Timestamp(dd[i]), side, t0, t[i], (side * (x - e) - COST) / rk * 100)); pos = None
            elif hit:
                out.append(("ORBREAK", m, pd.Timestamp(dd[i]), side, t0, t[i], (side * (sl - e) - COST) / rk * 100)); pos = None
            elif (side > 0 and c[i] <= mid[i]) or (side < 0 and c[i] >= mid[i]):
                x = o[i + 1]; out.append(("ORBREAK", m, pd.Timestamp(dd[i]), side, t0, t[i + 1], (side * (x - e) - COST) / rk * 100)); pos = None
            elif m == "A" and dd[i + 1] != dd[i]:
                out.append(("ORBREAK", m, pd.Timestamp(dd[i]), side, t0, t[i], (side * (c[i] - e) - COST) / rk * 100)); pos = None
            continue
        if dd[i + 1] != dd[i] or hm[i] < 1000 or hm[i] >= last_entry or hm[i + 1] >= last_entry or np.isnan(atr1[i]): continue
        sig = 1 if c[i] > hh[i] else (-1 if c[i] < ll[i] else 0)
        if sig:
            e = o[i + 1]; rk = 0.6 * atr1[i]; pos = (sig, e, e - sig * rk, t[i + 1], rk)
T = pd.DataFrame(out, columns=["ligne", "mode", "jour", "sens", "entree", "sortie", "eur"])
T.to_pickle("or_fermeture_trades.pkl")
P = {"tout 2025-11 a 2026-11 (derniere annee)": ("2025-11-03", "2026-11-03"), "depuis la fermeture a 23h (avril-oct 2026)": ("2026-04-01", "2026-11-03")}
for nom, (a, z) in P.items():
    print("==", nom)
    S = T[(T.jour >= a) & (T.jour < z)]
    print(S.groupby(["mode", "ligne"]).eur.agg(trades="count", total="sum", gagnants=lambda x: (x > 0).sum(), perdants=lambda x: (x < 0).sum(), pire="min").round(0))
    print(S.groupby("mode").eur.agg(["count", "sum"]).round(0))
