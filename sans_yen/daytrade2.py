"""
2e recherche day trading (strategies populaires / publiees), bougies 15 min, sans yen. Tout ferme le jour meme.
Heures serveur MT5 (New York + 7 h) : 16h30 serveur = 9h30 New York = ouverture US.
CONCEPTION : debut -> 30/06/2024. TEST FINAL : 01/07/2024 -> 30/10/2026.
"""
import numpy as np, pandas as pd, os
from recherche import mk, atr, daily, HERE
from daytrade import load15, hm, SPLIT

def vwap_series(s):
    tp = (s.high + s.low + s.close) / 3
    v = s.tick_volume.replace(0, 1)
    return (tp * v).cumsum() / v.cumsum()

def sessions(df, start, end):
    for day, g in df.groupby(df.index.date):
        k = np.array([hm(t) for t in g.index])
        yield pd.Timestamp(day), g, k

# ---------------------------------------------------------------- 1. Zone de bruit (Zarattini, Aziz, Barbon 2024)
def noise(sym, df, open_hm=1630, last_hm=2245, step=30):
    """Zone de bruit : moyenne sur 14 jours du mouvement absolu depuis l'ouverture a chaque heure.
    Achat si cloture > haut de la zone ET > VWAP, vente si < bas ET < VWAP, verifie toutes les 30 min.
    Stop suiveur = le plus serre entre le bord de la zone et la VWAP (verifie aux memes heures). Sortie fin de seance.
    Unite de risque (1 R) = la largeur de la zone a l'heure d'entree."""
    da = atr(daily(df), 14).shift()
    days = []
    for D, g, k in sessions(df, open_hm, last_hm):
        s = g[(k >= open_hm) & (k <= last_hm)]
        if len(s) < 20: continue
        days.append((D, s))
    moves = {}  # D -> dict(hhmm -> |close/open-1|)
    out = []
    prev_close = None
    hist = []
    for D, s in days:
        o = s.open.iloc[0]
        kk = np.array([hm(t) + 15 if (hm(t) % 100) < 45 else (hm(t) // 100 + 1) * 100 + (hm(t) % 100 + 15 - 60) for t in s.index])  # heure de fin de bougie
        mv = dict(zip(kk, np.abs(s.close.values / o - 1)))
        if prev_close is not None and len(hist) >= 14:
            vw = vwap_series(s).values
            pos = None
            for j, (t, end) in enumerate(zip(s.index, kk)):
                if (end % 100) % step != 0 and step == 30 and end % 100 not in (0, 30): continue
                vals = [h[end] for h in hist[-14:] if end in h]
                if len(vals) < 10: continue
                sig = float(np.mean(vals))
                up = max(o, prev_close) * (1 + sig); lo = min(o, prev_close) * (1 - sig)
                c = s.close.iloc[j]
                last = j == len(s) - 1 or end >= 2300 or hm(t) >= last_hm
                if pos is not None:
                    sd, e, rk, t0 = pos
                    stop = max(up, vw[j]) if sd == 1 else min(lo, vw[j])
                    if last or (sd == 1 and c < stop) or (sd == -1 and c > stop):
                        out.append(mk(sym, sd, t0, t, e, c, rk)); pos = None
                if last: break
                if pos is None:
                    rk = max(sig * o, 0.1 * da.get(D, sig * o * 10))
                    if c > up and c > vw[j]:
                        pos = (1, c, rk, t)
                    elif c < lo and c < vw[j]:
                        pos = (-1, c, rk, t)
            if pos is not None:
                sd, e, rk, t0 = pos
                out.append(mk(sym, sd, t0, s.index[-1], e, s.close.iloc[-1], rk))
        hist.append(mv)
        prev_close = s.close.iloc[-1]
    return out

# ---------------------------------------------------------------- 2. Initial Balance de l'or (TradeThatSwing 2026)
def initial_balance(sym, df, ib=(1630, 1715), last_entry=2200, exit_hm=2245, minp=0.003, maxp=0.015):
    """IB = 1re heure de la seance New York (9h30-10h30 NY). Apres la cassure, ordre limite 25 % a l'interieur de l'IB,
    stop = 60 % de l'IB, objectif = 50 % de l'IB au-dela du bord, sinon sortie en fin de seance."""
    out = []
    for D, g, k in sessions(df, 0, 0):
        r = g[(k >= ib[0]) & (k <= ib[1])]
        if len(r) < 3: continue
        hi, lo = r.high.max(), r.low.min(); w = hi - lo
        if not (minp <= w / r.open.iloc[0] <= maxp): continue
        after = g[k > ib[1]]
        side = 0; pos = None
        for t, (o, h, l, c) in zip(after.index, after[["open", "high", "low", "close"]].values):
            x = hm(t)
            if pos is None:
                if x > last_entry: break
                if side == 0:
                    if h > hi: side = 1
                    elif l < lo: side = -1
                    if side == 0: continue
                    # l'ordre limite est pose a la cloture de la bougie de cassure
                    continue
                e = hi - 0.25 * w if side == 1 else lo + 0.25 * w
                if (side == 1 and l <= e) or (side == -1 and h >= e):
                    ent = min(o, e) if side == 1 else max(o, e)
                    pos = (side, ent, ent - side * 0.6 * w, (hi + 0.5 * w) if side == 1 else (lo - 0.5 * w), 0.6 * w, t)
                else:
                    continue
            sd, e, sl, tp, rk, t0 = pos
            if (sd == 1 and l <= sl) or (sd == -1 and h >= sl):
                out.append(mk(sym, sd, t0, t, e, sl, rk)); pos = None; break
            if (sd == 1 and h >= tp) or (sd == -1 and l <= tp):
                out.append(mk(sym, sd, t0, t, e, tp, rk)); pos = None; break
            if x >= exit_hm:
                out.append(mk(sym, sd, t0, t, e, c, rk)); pos = None; break
        if pos is not None:
            sd, e, sl, tp, rk, t0 = pos
            out.append(mk(sym, sd, t0, after.index[-1], e, after.close.iloc[-1], rk))
    return out

# ---------------------------------------------------------------- 3. ICT Silver Bullet (version simplifiee, automatisable)
def silver_bullet(sym, df, win=(1700, 1745), exit_hm=2245, rr=2.0):
    """Fenetre 10h-11h New York (17h-18h serveur). Un 'fair value gap' (trou entre la bougie 1 et la bougie 3)
    se forme dans la fenetre, dans le sens qui suit une chasse de la liquidite de l'ouverture (16h30-17h) :
    si le plus bas de l'ouverture a ete pris puis FVG haussier -> achat au bord du FVG, stop sous la bougie 1,
    objectif 2 R, sinon fin de seance. Inverse pour la vente."""
    out = []
    for D, g, k in sessions(df, 0, 0):
        op = g[(k >= 1630) & (k < 1700)]
        if len(op) < 2: continue
        oh, ol = op.high.max(), op.low.min()
        s = g[k >= 1630]; ks = np.array([hm(t) for t in s.index])
        H, L, O, C = s.high.values, s.low.values, s.open.values, s.close.values
        swept_lo = swept_hi = False; pos = None; order = None
        for j in range(len(s)):
            x = ks[j]; t = s.index[j]
            if pos is None and order is not None:
                sd, e, sl = order
                if x > 1800: order = None
                elif (sd == 1 and L[j] <= e) or (sd == -1 and H[j] >= e):
                    ent = min(O[j], e) if sd == 1 else max(O[j], e); rk = abs(ent - sl)
                    if rk > 0: pos = (sd, ent, sl, ent + sd * rr * rk, rk, t)
                    order = None
            if pos is not None:
                sd, e, sl, tp, rk, t0 = pos
                if (sd == 1 and L[j] <= sl) or (sd == -1 and H[j] >= sl):
                    out.append(mk(sym, sd, t0, t, e, sl, rk)); pos = None; break
                if (sd == 1 and H[j] >= tp) or (sd == -1 and L[j] <= tp):
                    out.append(mk(sym, sd, t0, t, e, tp, rk)); pos = None; break
                if x >= exit_hm:
                    out.append(mk(sym, sd, t0, t, e, C[j], rk)); pos = None; break
                continue
            if x >= 1700 and x <= 1800:
                if L[j] < ol: swept_lo = True
                if H[j] > oh: swept_hi = True
            if order is None and j >= 2 and win[0] <= x <= win[1]:
                if swept_lo and L[j] > H[j - 2]:          # FVG haussier
                    order = (1, H[j - 2], L[j - 2])
                elif swept_hi and H[j] < L[j - 2]:        # FVG baissier
                    order = (-1, L[j - 2], H[j - 2])
        if pos is not None:
            sd, e, sl, tp, rk, t0 = pos
            out.append(mk(sym, sd, t0, s.index[-1], e, C[-1], rk))
    return out

# ---------------------------------------------------------------- 4. Chasse de liquidite (« Judas swing ») sur le range asiatique
def sweep(sym, df, rng=(0, 945), win=(1000, 1300), exit_hm=2245):
    """Londres depasse le plus haut (ou bas) asiatique puis une bougie 15 min referme DANS le range :
    on joue le retour (vente si le haut a ete chasse). Stop = extreme de la chasse, objectif = l'autre bord du range."""
    d = daily(df); da = atr(d, 14).shift()
    out = []
    for D, g, k in sessions(df, 0, 0):
        a = da.get(D, np.nan)
        r = g[(k >= rng[0]) & (k <= rng[1])]
        if len(r) < 20 or np.isnan(a): continue
        hi, lo = r.high.max(), r.low.min()
        if not (0.15 * a <= hi - lo <= 1.0 * a): continue
        s = g[k > rng[1]]; ks = np.array([hm(t) for t in s.index])
        ext_h, ext_l = hi, lo; pos = None; sig = None
        for j, t in enumerate(s.index):
            o, h, l, c = s.open.iloc[j], s.high.iloc[j], s.low.iloc[j], s.close.iloc[j]; x = ks[j]
            if pos is None and sig is not None:
                sd, sl, tp = sig
                rk = (sl - o) if sd == -1 else (o - sl)
                if rk > 0.02 * a: pos = (sd, o, sl, tp, rk, t)
                sig = None
                if pos is None: break
            if pos is not None:
                sd, e, sl, tp, rk, t0 = pos
                if (sd == 1 and l <= sl) or (sd == -1 and h >= sl):
                    out.append(mk(sym, sd, t0, t, e, sl, rk)); pos = None; break
                if (sd == 1 and h >= tp) or (sd == -1 and l <= tp):
                    out.append(mk(sym, sd, t0, t, e, tp, rk)); pos = None; break
                if x >= exit_hm:
                    out.append(mk(sym, sd, t0, t, e, c, rk)); pos = None; break
                continue
            if x > win[1]: break
            if x < win[0]: continue
            ext_h, ext_l = max(ext_h, h), min(ext_l, l)
            if ext_h > hi and c < hi and c > lo:
                sig = (-1, ext_h, lo)
            elif ext_l < lo and c > lo and c < hi:
                sig = (1, ext_l, hi)
        if pos is not None:
            sd, e, sl, tp, rk, t0 = pos
            out.append(mk(sym, sd, t0, s.index[-1], e, s.close.iloc[-1], rk))
    return out

# ---------------------------------------------------------------- 5. Tendance VWAP (Zarattini & Aziz 2023, QQQ)
def vwap_trend(sym, df, start=1630, end=2245):
    """Achat quand le prix cloture au-dessus de la VWAP, vente en dessous ; retournement a chaque croisement
    (verifie toutes les 15 min). Fin de seance : tout est ferme. 1 R = 0,25 x ATR journalier."""
    d = daily(df); da = atr(d, 14).shift()
    out = []
    for D, g, k in sessions(df, 0, 0):
        a = da.get(D, np.nan)
        s = g[(k >= start) & (k <= end)]
        if len(s) < 8 or np.isnan(a): continue
        vw = vwap_series(s).values; C = s.close.values; idx = s.index
        pos = None
        for j in range(len(s)):
            want = 1 if C[j] > vw[j] else -1
            last = j == len(s) - 1
            if pos is not None and (want != pos[0] or last):
                out.append(mk(sym, pos[0], pos[2], idx[j], pos[1], C[j], 0.25 * a)); pos = None
            if pos is None and not last:
                pos = (want, C[j], idx[j])
    return out

US = ["US500", "US30", "USTECH100M"]
CANDS = {
    "BRUIT_US":       (US, noise),
    "BRUIT_DAX":      (["DE40"], lambda s, d: noise(s, d, open_hm=1000, last_hm=1815)),
    "IB_OR":          (["XAUUSD"], initial_balance),
    "IB_INDICES":     (US, lambda s, d: initial_balance(s, d, minp=0.002)),
    "SILVER_BULLET":  (US + ["XAUUSD"], silver_bullet),
    "CHASSE_ASIE":    (["XAUUSD", "EURUSD", "GBPUSD", "XAGUSD", "AUDUSD", "USDCHF", "USDCAD", "EURGBP", "EURCHF"], sweep),
    "CHASSE_US":      (US, lambda s, d: sweep(s, d, rng=(0, 1615), win=(1630, 1800))),
    "VWAP_TENDANCE":  (US + ["DE40"], vwap_trend),
}

if __name__ == "__main__":
    data, allt = {}, []
    for st, (mkts, fn) in CANDS.items():
        for s in mkts:
            if s not in data: data[s] = load15(s)
            t = pd.DataFrame(fn(s, data[s]))
            if t.empty: print("aucun trade", st, s); continue
            t["strat"] = st; allt.append(t)
    T = pd.concat(allt); T["ligne"] = T.strat + ":" + T.symbol
    T["periode"] = np.where(T.open_time < SPLIT, "A_conception", "B_test")
    T.to_pickle(os.path.join(HERE, "daytrade2_trades.pkl"))
    g = T.groupby(["ligne", "periode"]).R.agg(["count", "mean"]).unstack()
    pd.set_option("display.width", 250)
    print(g.round(3).to_string())
