"""L'APPRENTI (demande d'aurele, 02/11/2026) : pas de trade force.
Le bot observe en continu 8 familles de setups sur 13 marches sans yen (bougies 15 min).
Chaque setup observe est garde en MEMOIRE avec son resultat (une fois le trade virtuel termine).
Quand un nouveau setup apparait, le bot cherche dans sa memoire les setups les plus ressemblants
(meme famille, contexte proche : tendance, volatilite, heure, distance VWAP, RSI...) en donnant plus de poids
aux souvenirs recents (le marche change). Il ne prend le trade que si :
   probabilite de gain estimee >= SEUIL_P  ET  gain moyen attendu (couts deduits) >= SEUIL_E.
Aucune donnee future : un setup n'entre en memoire qu'apres la fin de son trade virtuel.
Sortie identique pour tous : stop 0,3 x ATR jour, objectif 1 x stop (1:1), sinon fin de seance.
Couts prudents (SPREAD x 1,2). Memoire demarree en 03/2022, trades comptes a partir du 01/01/2023."""
import os, sys, numpy as np, pandas as pd
from multiprocessing import Pool
from base import load, cost, MKTS

HERE = os.path.dirname(os.path.abspath(__file__))
SESS = {"DE40": (1000, 1830), "US500": (1630, 2300), "USTECH100M": (1630, 2300), "US30": (1630, 2300),
        "XAUUSD": (1000, 2300), "XAGUSD": (1000, 2300)}
for s in ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "EURGBP", "EURCHF"]: SESS[s] = (1000, 1900)
FAM = ["CASSURE_OUVERTURE", "CASSURE_VEILLE", "REJET_VEILLE", "RETOUR_TENDANCE", "CROISE_VWAP",
       "BOUGIE_FORTE", "RSI_EXTREME", "COMPRESSION"]
NOM_FAM = {"CASSURE_OUVERTURE": "cassure du range d'ouverture", "CASSURE_VEILLE": "cassure du plus haut/bas d'hier",
           "REJET_VEILLE": "faux départ au-delà du haut/bas d'hier", "RETOUR_TENDANCE": "repli sur la moyenne dans la tendance",
           "CROISE_VWAP": "passage de la VWAP", "BOUGIE_FORTE": "bougie d'élan", "RSI_EXTREME": "sortie de zone extrême du RSI",
           "COMPRESSION": "cassure apres compression"}
STOP_ATR, TGT = 0.3, 1.0
START_TRADE = pd.Timestamp("2023-01-01")
FEATS = ["heure", "tend", "ecart_ma", "vol", "deja", "gap", "elan5", "vwap", "rsi", "taille", "ema", "pos_veille", "jour", "sens"]


def hm_add(hm, minutes):
    t = (hm // 100) * 60 + hm % 100 + minutes
    return (t // 60) * 100 + t % 60


def events(sym):
    d = load(sym).copy()
    op, cl = SESS[sym]
    # indicateurs 15 min (serie continue)
    d["ema20"] = d.close.ewm(span=20, adjust=False).mean()
    delta = d.close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    d["rng"] = d.high - d.low
    d["rng20"] = d.rng.rolling(20).mean().shift()
    # jour
    g = d.groupby("day").agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = g.c.shift()
    tr = pd.concat([g.h - g.l, (g.h - pc).abs(), (g.l - pc).abs()], axis=1).max(axis=1)
    D = pd.DataFrame(index=g.index)
    D["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean().shift()
    D["atr100"] = tr.ewm(alpha=1 / 100, adjust=False).mean().shift()
    D["pc"] = g.c.shift(); D["ph"] = g.h.shift(); D["pl"] = g.l.shift()
    D["sma20"] = g.c.rolling(20).mean().shift(); D["c5"] = g.c.shift(6)
    c_cost = cost(sym)
    last_entry = hm_add(cl, -60)
    out = []
    for day, b in d.groupby("day"):
        if day not in D.index: continue
        r = D.loc[day]
        if not np.isfinite([r.atr, r.atr100, r.sma20, r.c5, r.ph]).all() or r.atr <= 0: continue
        b = b[(b.hm >= op) & (b.hm < cl)]
        if len(b) < 8: continue
        O, H, L, C = b.open.values, b.high.values, b.low.values, b.close.values
        V = np.maximum(b.tick_volume.values, 1).astype(float)
        hmv = b.hm.values; idx = b.index
        tp = (H + L + C) / 3; vwap = np.cumsum(tp * V) / np.cumsum(V)
        ema = b.ema20.values; rsi = b.rsi.values; rng20 = b.rng20.values
        dopen = O[0]; atr = r.atr
        orh, orl = H[:2].max(), L[:2].min()
        seen = set()
        n = len(b)
        for i in range(2, n - 1):
            if hmv[i + 1] > last_entry: break
            sig = []
            if C[i] > orh and C[i - 1] <= orh: sig.append(("CASSURE_OUVERTURE", 1))
            if C[i] < orl and C[i - 1] >= orl: sig.append(("CASSURE_OUVERTURE", -1))
            if C[i] > r.ph and C[i - 1] <= r.ph: sig.append(("CASSURE_VEILLE", 1))
            if C[i] < r.pl and C[i - 1] >= r.pl: sig.append(("CASSURE_VEILLE", -1))
            if H[i] > r.ph and C[i] < r.ph: sig.append(("REJET_VEILLE", -1))
            if L[i] < r.pl and C[i] > r.pl: sig.append(("REJET_VEILLE", 1))
            if i >= 5:
                if r.pc > r.sma20 and L[i] <= ema[i] < C[i] and (L[i - 4:i] > ema[i - 4:i]).all(): sig.append(("RETOUR_TENDANCE", 1))
                if r.pc < r.sma20 and H[i] >= ema[i] > C[i] and (H[i - 4:i] < ema[i - 4:i]).all(): sig.append(("RETOUR_TENDANCE", -1))
            if C[i] > vwap[i] and C[i - 1] <= vwap[i - 1]: sig.append(("CROISE_VWAP", 1))
            if C[i] < vwap[i] and C[i - 1] >= vwap[i - 1]: sig.append(("CROISE_VWAP", -1))
            rg = H[i] - L[i]
            if np.isfinite(rng20[i]) and rg > 2.5 * rng20[i] and rg > 0:
                pos = (C[i] - L[i]) / rg
                if pos > 0.75: sig.append(("BOUGIE_FORTE", 1))
                if pos < 0.25: sig.append(("BOUGIE_FORTE", -1))
            if np.isfinite(rsi[i - 1]) and np.isfinite(rsi[i]):
                if rsi[i - 1] < 25 <= rsi[i]: sig.append(("RSI_EXTREME", 1))
                if rsi[i - 1] > 75 >= rsi[i]: sig.append(("RSI_EXTREME", -1))
            if i >= 9:
                w8 = H[i - 8:i].max() - L[i - 8:i].min()
                if np.isfinite(rng20[i]) and w8 < 3.0 * rng20[i]:
                    if C[i] > H[i - 8:i].max(): sig.append(("COMPRESSION", 1))
                    if C[i] < L[i - 8:i].min(): sig.append(("COMPRESSION", -1))
            for fam, s in sig:
                if (fam, s) in seen: continue
                seen.add((fam, s))
                e = O[i + 1]; sd = STOP_ATR * atr
                stop = e - s * sd; tgt = e + s * TGT * sd
                hs = (L[i + 1:] <= stop) if s == 1 else (H[i + 1:] >= stop)
                ht = (H[i + 1:] >= tgt) if s == 1 else (L[i + 1:] <= tgt)
                js = np.argmax(hs) if hs.any() else 10 ** 9
                jt = np.argmax(ht) if ht.any() else 10 ** 9
                if js == 10 ** 9 and jt == 10 ** 9:
                    j = n - 1 - (i + 1); Rg = s * (C[-1] - e) / sd
                elif js <= jt:
                    j = js; Rg = -1.0
                else:
                    j = jt; Rg = TGT
                xi = i + 1 + j
                cR = c_cost / sd
                rg_ = (r.ph - r.pl) if r.ph > r.pl else np.nan
                f = dict(heure=(hmv[i] - op) / max(1, cl - op), tend=s * np.sign(r.pc - r.sma20),
                         ecart_ma=s * (r.pc - r.sma20) / atr, vol=r.atr / r.atr100, deja=s * (C[i] - dopen) / atr,
                         gap=s * (dopen - r.pc) / atr, elan5=s * (r.pc - r.c5) / atr, vwap=s * (C[i] - vwap[i]) / atr,
                         rsi=s * (rsi[i] - 50) / 50 if np.isfinite(rsi[i]) else 0.0, taille=rg / atr,
                         ema=s * (C[i] - ema[i]) / atr, pos_veille=s * (((C[i] - r.pl) / rg_) - 0.5) if np.isfinite(rg_) else 0.0,
                         jour=day.dayofweek / 4, sens=float(s))
                out.append(dict(sym=sym, fam=fam, side=s, t_sig=idx[i] + pd.Timedelta(minutes=15), t_in=idx[i + 1],
                                t_out=idx[xi] + pd.Timedelta(minutes=15), day=day, R_gross=Rg, cost_R=cR, R=Rg - cR,
                                win=int(Rg - cR > 0), **f))
    return pd.DataFrame(out)


def knn_family(args):
    E, params = args
    k, hl, mismatch = params["k"], params["hl"], params["mismatch"]
    X = E[FEATS].values.astype(float)
    mu = X[E.t_sig < pd.Timestamp("2023-01-01")].mean(0); sdv = X[E.t_sig < pd.Timestamp("2023-01-01")].std(0) + 1e-9
    X = np.clip((X - mu) / sdv, -4, 4)
    ts = E.t_sig.values.astype("datetime64[m]").astype(np.int64); to = E.t_out.values.astype("datetime64[m]").astype(np.int64)
    sym = pd.factorize(E.sym)[0]
    win = E.win.values.astype(float); R = E.R.values
    P = np.full(len(E), np.nan); EX = np.full(len(E), np.nan); NE = np.zeros(len(E))
    tstart = np.datetime64(START_TRADE, "m").astype(np.int64)
    for q in range(len(E)):
        if ts[q] < tstart: continue
        m = to[:q] <= ts[q]
        if m.sum() < 200: continue
        ii = np.nonzero(m)[0]
        dist = np.sqrt(((X[ii] - X[q]) ** 2).sum(1)) + mismatch * (sym[ii] != sym[q])
        kk = min(k, len(ii))
        nn = np.argpartition(dist, kk - 1)[:kk]
        sel = ii[nn]
        age = (ts[q] - ts[sel]) / (60 * 24)
        w = (0.5 ** (age / hl) if hl else 1.0) / (1 + dist[nn])
        P[q] = (w * win[sel]).sum() / w.sum(); EX[q] = (w * R[sel]).sum() / w.sum()
        NE[q] = w.sum() ** 2 / (w ** 2).sum()
    return pd.DataFrame({"P": P, "EX": EX, "neff": NE}, index=E.index)


def predict(EV, params, procs=4):
    parts = [(EV[EV.fam == f].sort_values("t_sig"), params) for f in FAM]
    with Pool(procs) as p:
        res = p.map(knn_family, parts)
    out = EV.copy()
    pr = pd.concat(res)
    out[["P", "EX", "neff"]] = pr.reindex(out.index)
    return out


def portefeuille(T):
    """une seule position a la fois par marche (ordre chronologique)"""
    T = T.sort_values("t_in"); busy = {}; keep = []
    for r in T.itertuples():
        if busy.get(r.sym, pd.Timestamp(0)) > r.t_in: continue
        busy[r.sym] = r.t_out; keep.append(r.Index)
    return T.loc[keep]


def bilan(T, label):
    A = T[T.day < pd.Timestamp("2025-01-01")]; B = T[T.day >= pd.Timestamp("2025-01-01")]
    wk = T.groupby(T.day.dt.to_period("W-SUN")).R.sum() * 100
    return dict(version=label, trades=len(T), par_jour=round(len(T) / max(1, T.day.nunique()), 2),
                taux_gain=round(100 * (T.R > 0).mean(), 1) if len(T) else 0,
                eur_23_24=round(A.R.sum() * 100), eur_25_26=round(B.R.sum() * 100), eur_total=round(T.R.sum() * 100),
                eur_par_trade=round(T.R.mean() * 100, 1) if len(T) else 0,
                sem_gagnantes=round(100 * (wk > 0).mean()) if len(wk) else 0)


if __name__ == "__main__":
    cache = os.path.join(HERE, "apprenti_events.pkl")
    if os.path.exists(cache):
        EV = pd.read_pickle(cache)
    else:
        with Pool(4) as p:
            EV = pd.concat(p.map(events, MKTS), ignore_index=True)
        EV.to_pickle(cache)
    print("setups observes :", len(EV), EV.groupby("fam").size().to_dict())
    base = dict(k=60, hl=365, mismatch=1.5)
    PR = predict(EV, base)
    PR.to_pickle(os.path.join(HERE, "apprenti_preds.pkl"))
    TT = PR[PR.t_in >= START_TRADE]
    rows = [bilan(portefeuille(TT), "TOUS les setups (trades forces)")]
    for sp in [0.55, 0.60, 0.65, 0.70]:
        for se in [0.0, 0.10]:
            sel = TT[(TT.P >= sp) & (TT.EX >= se) & (TT.neff >= 15)]
            rows.append(bilan(portefeuille(sel), f"P>={sp:.2f} E>={se:.2f}"))
    print(pd.DataFrame(rows).to_string())
