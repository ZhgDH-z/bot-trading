"""STRATEGIE UNIQUE (demande d'aurele, 02/11/2026) : toutes les analyses fusionnees en UN score.
A l'ouverture d'un marche (DAX 10h00 serveur, or et indices US 16h30), apres la 1re bougie de 15 min :
 votes (+1 achat / -1 vente) :
   1. sens de la 1re bougie de 15 min           (etude 1re bougie, Zarattini & Aziz)
   2. tendance 20 jours (cloture d'hier vs moyenne 20 j)   (correctif tendance)
   3. ouverture vs cloture d'hier (gap)          ('prix deja parti dans le sens du trade')
   4. elan sur 5 jours                            (diagnostic des pertes)
   5. position vs la zone de bruit / VWAP a 10h15 (zone de bruit, Zarattini, Aziz, Barbon)
 filtres : 1re bougie entre 0,05 et 0,19 x ATR jour, pas le lundi (les 2 correctifs valides).
 entree si le score atteint le seuil ; stop de l'autre cote de la 1re bougie ; sortie en fin de seance,
 ou plus tot si le prix repasse sous la VWAP de seance (sortie de la zone de bruit), verifie toutes les 30 min.
 100 EUR par achat, 50 EUR par vente, couts prudents."""
import numpy as np, pandas as pd
from base import load, cost, A_END

SESS = {"DE40": (1000, 1815), "XAUUSD": (1630, 2245), "US500": (1630, 2245), "USTECH100M": (1630, 2245), "US30": (1630, 2245), "XAGUSD": (1630, 2245)}

def daily_info(sym, close_bar):
    d = load(sym)
    g = d.groupby("day").agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = g.c.shift()
    tr = pd.concat([g.h - g.l, (g.h - pc).abs(), (g.l - pc).abs()], axis=1).max(axis=1)
    f = pd.DataFrame(index=g.index)
    f["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean().shift()
    f["prevc_d"] = g.c.shift(); f["sma20"] = g.c.rolling(20).mean().shift(); f["c6"] = g.c.shift(6)
    sc = d[d.hm == close_bar].groupby("day").close.last()             # cloture de la seance cash
    f["sess_close_prev"] = sc.reindex(f.index).ffill().shift()
    return f

def run(sym, seuil=3, vwap_exit=True, filtres=True, votes_on=(1, 2, 3, 4, 5)):
    op, cl = SESS[sym]; d = load(sym); f = daily_info(sym, cl)
    out = []
    for day, g in d.groupby("day"):
        if day not in f.index: continue
        r = f.loc[day]
        if np.isnan(r.atr) or np.isnan(r.sma20) or np.isnan(r.sess_close_prev) or np.isnan(r.c6): continue
        hmv = g.hm.values
        if op not in hmv or cl not in hmv: continue
        b0 = g[hmv == op].iloc[0]
        o, c, hi, lo = b0.open, b0.close, b0.high, b0.low
        rng_ = hi - lo
        if filtres and (rng_ < 0.05 * r.atr or rng_ > 0.19 * r.atr or day.dayofweek == 0): continue
        if not filtres and (rng_ < 0.05 * r.atr or rng_ > 1.0 * r.atr): continue
        v = {}
        v[1] = 1 if c > o else -1
        v[2] = 1 if r.prevc_d > r.sma20 else -1
        v[3] = 1 if o > r.sess_close_prev else -1
        v[4] = 1 if r.prevc_d > r.c6 else -1
        tp = (hi + lo + c) / 3
        v[5] = 1 if c > tp else -1          # cloture de la 1re bougie au-dessus/au-dessous de sa VWAP
        score = sum(v[k] for k in votes_on)
        side = 1 if score > 0 else -1
        if abs(score) < seuil or v[1] != side: continue    # la 1re bougie doit toujours etre d'accord
        rest = g[(hmv > op) & (hmv <= cl)]
        if rest.empty: continue
        e = rest.open.values[0]; sl = lo if side == 1 else hi
        rk = side * (e - sl)
        if rk <= 0.02 * r.atr: continue
        pv = (b0.high + b0.low + b0.close) / 3 * max(1, b0.tick_volume); vv = max(1, b0.tick_volume)
        x = None; t1 = None
        for t, (oo, hh, ll, cc, tv, m) in zip(rest.index, rest[["open", "high", "low", "close", "tick_volume", "hm"]].values):
            if (side == 1 and ll <= sl) or (side == -1 and hh >= sl):
                x = min(oo, sl) if side == 1 else max(oo, sl); t1 = t; break
            pv += (hh + ll + cc) / 3 * max(1, tv); vv += max(1, tv); vw = pv / vv
            endm = (int(m) // 100 * 60 + int(m) % 100 + 15)
            if vwap_exit and endm % 30 == 0 and endm >= (op // 100 * 60 + op % 100) + 120:
                if (side == 1 and cc < vw) or (side == -1 and cc > vw):
                    x = cc; t1 = t; break
            if m >= cl:
                x = cc; t1 = t; break
        if x is None: x = rest.close.values[-1]; t1 = rest.index[-1]
        gross = side * (x - e) / rk; cR = cost(sym) / rk
        mise = 100 if side == 1 else 50
        out.append(dict(day=day, sym=sym, side=side, score=score, e=e, x=x, t1=t1, R=gross - cR, R_gross=gross, cost_R=cR, eur=(gross - cR) * mise))
    return pd.DataFrame(out)

def rapport(T, lab):
    T = T.sort_values("day"); eq = T.eur.cumsum()
    by = T.groupby(T.day.dt.year).eur.sum().round().astype(int).to_dict()
    nd = pd.bdate_range("2022-06-06", "2026-11-02").size
    rng = np.random.default_rng(2)
    mise = np.where(T.side > 0, 100, 50)
    sims = np.array([((T.R_gross.values * rng.choice([-1, 1], len(T)) - T.cost_R.values) * mise).sum() for _ in range(3000)])
    return dict(version=lab, trades=len(T), par_jour=round(len(T) / nd, 2), total=round(T.eur.sum()), **{str(k): v for k, v in by.items()},
                pire_baisse=round(float((eq - eq.cummax()).min())), gagnants=round((T.R > 0).mean() * 100),
                p_hasard=round(float((sims >= T.eur.sum()).mean()), 3))

if __name__ == "__main__":
    pd.set_option("display.width", 250)
    rows = []
    for sym in SESS:
        for s in (3, 5):
            rows.append(rapport(run(sym, seuil=s), f"{sym} seuil {s}"))
    print(pd.DataFrame(rows).to_string(index=False))
