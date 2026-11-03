"""Stratégies FAITES POUR LE FOREX (demande d'aurele, 03/11/2026 vers 2h40 Paris). 7 paires sans yen, bougies 15 min.
Heures serveur = New York + 7 h : Asie calme 01:00-08:00, Londres ouvre 10:00, New York 15:00, fixing de Londres (16h Londres) 18:00.
Familles (réglages voisins testés pour vérifier le plateau) :
 A. Cassure de la fourchette asiatique à l'ouverture de Londres (classique « London breakout »).
 B. Retour à la moyenne en séance asiatique (bandes de Bollinger, cible = moyenne) : la base des « scalpeurs de nuit » EURCHF/EURGBP.
 C. Retournement après le fixing WMR de 16h Londres (Melvin & Prins 2015 ; Evans 2018).
 D. Effet heure du jour (Breedon & Ranaldo 2013) : une monnaie a tendance à baisser pendant SES heures de bourse.
Coûts : 1,2 x le plus grand entre l'écart prudent de la table et l'écart réel de la bougie d'entrée.
Choix sur P (2023 -> 02/11/2025) : >= 60 trades, gain moyen >= 0,03 R, 2 moitiés de P gagnantes, et au moins 2/3 des réglages voisins gagnants.
Puis la dernière année L (03/11/2025 -> 02/11/2026), jamais utilisée pour choisir."""
import os, sys, itertools, numpy as np, pandas as pd
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "sans_yen"))
from recherche import SPREAD
from base import load
P0, PM, L0, L1 = pd.Timestamp("2023-01-01"), pd.Timestamp("2024-06-01"), pd.Timestamp("2025-11-03"), pd.Timestamp("2026-11-02")
FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "EURGBP", "EURCHF"]

def prep(sym):
    d = load(sym).copy()
    d = d[d.index >= pd.Timestamp("2022-09-01")]
    dec = max(len(str(x).split(".")[1]) if "." in str(x) else 0 for x in d.close.head(300))
    d["sp"] = np.maximum(d.spread_points.values * 10.0 ** (-dec), SPREAD[sym]) * 1.2
    pc = d.close.shift(); tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    g = d.groupby("day").agg(h=("high", "max"), l=("low", "min"), c=("close", "last")); pcd = g.c.shift()
    trd = pd.concat([g.h - g.l, (g.h - pcd).abs(), (g.l - pcd).abs()], axis=1).max(axis=1)
    d["datr"] = d.day.map(trd.ewm(alpha=1 / 14, adjust=False).mean().shift())
    return d

def sim(d, sigs):
    """sigs : liste (i, side, stop_dist, tgt_dist ou None, exit_hm). Entrée à l'ouverture de la bougie i+1."""
    o, h, l, c, hm, day, sp = d.open.values, d.high.values, d.low.values, d.close.values, d.hm.values, d.day.values, d.sp.values
    out = []; busy = -1
    for i, sd, sd_, tg, ex in sigs:
        j = i + 1
        if j <= busy or j >= len(d) or day[j] != day[i] or not sd_ > 0: continue
        e = o[j]; sl = e - sd * sd_; tp = e + sd * tg if tg else None; cs = sp[j]; x = None
        k = j
        while k < len(d):
            if day[k] != day[j]: x, k = c[k - 1], k - 1; break
            if (sd == 1 and l[k] <= sl) or (sd == -1 and h[k] >= sl): x = sl; break
            if tp is not None and ((sd == 1 and h[k] >= tp) or (sd == -1 and l[k] <= tp)): x = tp; break
            if hm[k] >= ex: x = c[k]; break
            k += 1
        if x is None: k = len(d) - 1; x = c[k]
        out.append((pd.Timestamp(day[j]), sd, d.index[j], d.index[k], (sd * (x - e) - cs) / sd_, cs / sd_)); busy = k
    return pd.DataFrame(out, columns=["day", "side", "t0", "t1", "R", "cR"])

def asie_cassure(d, k_tgt, stop_mid, last=1300, ex=1845):
    """Fourchette 02:00-09:45 ; cassure entre 10:00 et `last` ; stop autre bord (ou milieu) ; cible k x fourchette."""
    sig = []
    for D, g in d.groupby("day", sort=True):
        r = g[(g.hm >= 200) & (g.hm <= 945)]
        if len(r) < 20: continue
        hi, lo = r.high.max(), r.low.min(); w = hi - lo; a = g.datr.iloc[0]
        if not (np.isfinite(a) and 0.15 * a <= w <= 0.8 * a): continue
        s = g[(g.hm >= 1000) & (g.hm <= last)]
        for t, cl in zip(s.index, s.close.values):
            if cl > hi or cl < lo:
                sd = 1 if cl > hi else -1; i = d.index.get_loc(t)
                stop = (w / 2 if stop_mid else w) + abs(cl - (hi if sd == 1 else lo))
                sig.append((i, sd, stop, k_tgt * w, ex)); break
    return sig

def asie_retour(d, z, k_stop, t0=100, t1=700, ex=900):
    """Bollinger 20 sur 15 min pendant l'Asie : clôture hors bande -> retour vers la moyenne (cible) ; stop k x ATR 15 min."""
    c = d.close; m = c.rolling(20).mean(); s = c.rolling(20).std()
    zz = ((c - m) / s).values; hm = d.hm.values; a = d.atr.values; mv = m.values; cv = c.values
    sig = []
    for i in np.where((hm >= t0) & (hm <= t1) & (np.abs(zz) >= z))[0]:
        sd = -1 if zz[i] > 0 else 1
        sig.append((i, sd, k_stop * a[i], abs(cv[i] - mv[i]), ex))
    return sig

def fixing(d, seuil, ex):
    """Mouvement 17:00 -> 17:59 (l'heure avant le fixing de 16h Londres) ; à 18:00 on joue le retournement."""
    sig = []
    for D, g in d.groupby("day", sort=True):
        a = g.datr.iloc[0]; r = g[(g.hm >= 1700) & (g.hm <= 1745)]
        if len(r) < 4 or not np.isfinite(a): continue
        mvt = r.close.iloc[-1] - r.open.iloc[0]
        if abs(mvt) < seuil * a: continue
        sig.append((d.index.get_loc(r.index[-1]), -int(np.sign(mvt)), abs(mvt), None, ex))
    return sig

def heure(d, sym, leg):
    """EUR/GBP/CHF/AUD/CAD : la monnaie « locale » baisse pendant ses heures. leg = 'europe' (10:00-15:00) ou 'us' (15:00-22:45)."""
    base_eu = sym in ("EURUSD", "GBPUSD", "EURGBP", "EURCHF"); sig = []
    for D, g in d.groupby("day", sort=True):
        a = g.datr.iloc[0]
        if not np.isfinite(a): continue
        st, ex = (945, 1500) if leg == "europe" else (1445, 2245)
        r = g[g.hm == st]
        if r.empty: continue
        if sym in ("EURUSD", "GBPUSD", "AUDUSD"): sd = -1 if leg == "europe" else 1   # base européenne/aus. : baisse en Europe, monte pendant les heures US
        elif sym in ("USDCAD", "USDCHF"): sd = 1 if leg == "europe" else -1           # USD en 1er : le dollar monte pendant les heures européennes
        else: continue
        sig.append((d.index.get_loc(r.index[0]), sd, 0.5 * a, None, ex))
    return sig

def familles(sym, d):
    F = {}
    for k, mid in itertools.product([1.0, 1.5, 2.0], [False, True]): F[("A cassure Londres", f"cible {k} stop {'milieu' if mid else 'bord'}")] = lambda k=k, mid=mid: asie_cassure(d, k, mid)
    for z, ks in itertools.product([2.0, 2.5, 3.0], [2.0, 3.0, 4.0]): F[("B retour Asie", f"z {z} stop {ks} ATR")] = lambda z=z, ks=ks: asie_retour(d, z, ks)
    for s_, ex in itertools.product([0.1, 0.15, 0.2], [1900, 2000, 2200]): F[("C fixing 16h", f"seuil {s_} sortie {ex}")] = lambda s_=s_, ex=ex: fixing(d, s_, ex)
    for leg in ["europe", "us"]: F[("D heure du jour", leg)] = lambda leg=leg: heure(d, sym, leg)
    return F

def one(sym):
    d = prep(sym); rows = []; trades = {}
    for (fam, reg), f in familles(sym, d).items():
        t = sim(d, f()); t = t[(t.day >= P0) & (t.day <= L1)]
        P, L = t[t.day < L0], t[t.day >= L0]
        rows.append(dict(sym=sym, fam=fam, reg=reg, nP=len(P), P=P.R.sum(), moyP=P.R.mean() if len(P) else 0,
                         P1=P[P.day < PM].R.sum(), P2=P[P.day >= PM].R.sum(), nL=len(L), L=L.R.sum()))
        trades[(fam, reg)] = t
    print(sym, "fini", flush=True); return rows, {sym: trades}

if __name__ == "__main__":
    with Pool(7) as p: res = p.map(one, FX)
    R = pd.DataFrame([r for rr, _ in res for r in rr]); T = {k: v for _, tt in res for k, v in tt.items()}
    pd.to_pickle(dict(R=R, T=T), os.path.join(HERE, "fx_recherche.pkl"))
    R["okP"] = (R.nP >= 60) & (R.moyP >= 0.03) & (R.P1 > 0) & (R.P2 > 0)
    R["plateau"] = R.groupby(["sym", "fam"]).P.transform(lambda x: (x > 0).mean())
    pd.set_option("display.width", 220)
    g = R.groupby(["sym", "fam"]).agg(reglages=("P", "size"), P_pos=("P", lambda x: (x > 0).sum()), L_pos=("L", lambda x: (x > 0).sum()),
                                      P_moy=("P", lambda x: round(x.mean() * 1000)), L_moy=("L", lambda x: round(x.mean() * 1000)))
    print(g.to_string())
    ok = R[R.okP & (R.plateau >= 2 / 3)].sort_values("P", ascending=False).groupby("sym").head(1)
    ok = ok.assign(P_eur=(ok.P * 1000).round(), L_eur=(ok.L * 1000).round())
    print("\nCHOIX SUR P :\n", ok[["sym", "fam", "reg", "nP", "P_eur", "nL", "L_eur"]].to_string())
