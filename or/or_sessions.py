"""OR (XAUUSD) : strategies publiees / connues, testees sur 14 ans de bougies 1 h (2012 -> 30/10/2026).
Heures = heure serveur MT5 (Paris + 1 h). Asie ~ 01h-10h, Londres 10h-16h, New York 16h-23h, fixing PM de Londres = bougie 17h.
Sources : anomalie 'l'or monte en Asie, baisse a Londres/New York' (D. Speck ; Wei, SSRN 2026 : 77 % du gain de l'or en Asie,
momentum d'une session a la suivante) ; cassure du range asiatique a Londres ; 'chasse' du range asiatique (SMC) ;
continuation Londres -> New York ; cassure du plus haut/bas de la veille avec tendance.
Couts prudents : 0,36 $ par trade. 100 EUR par achat, 50 EUR par vente. Stop de secours = 1 R."""
import numpy as np, pandas as pd, os
HERE = os.path.dirname(os.path.abspath(__file__))
COST = float(os.environ.get("OR_COST", "0.36"))
PER = [("2012-2017", "2012", "2018"), ("2018-2021", "2018", "2022"), ("2022-2024", "2022", "2025"), ("2025-2026", "2025", "2027")]

def load():
    d = pd.read_csv(os.path.join(HERE, "..", "data_export", "XAUUSD_H1.csv"))
    d["time"] = pd.to_datetime(d.time, format="%Y.%m.%d %H:%M"); d = d.set_index("time")
    d = d[d.index.dayofweek < 5]; d["h"] = d.index.hour; d["day"] = d.index.normalize()
    return d

D = load()
G = D.groupby("day").agg(o=("open", "first"), hi=("high", "max"), lo=("low", "min"), c=("close", "last"))
pc = G.c.shift()
TR = pd.concat([G.hi - G.lo, (G.hi - pc).abs(), (G.lo - pc).abs()], axis=1).max(axis=1)
G["atr"] = TR.ewm(alpha=1 / 14, adjust=False).mean().shift()
G["sma20"] = G.c.rolling(20).mean().shift(); G["pc"] = pc; G["ph"] = G.hi.shift(); G["pl"] = G.lo.shift()
G["trend"] = np.sign(G.pc - G.sma20)
DAYS = {k: v for k, v in D.groupby("day")}

def bars(day, h0, h1):
    g = DAYS[day]; return g[(g.h >= h0) & (g.h <= h1)]

def timed(day, side, h0, h1, k=0.25):
    """entree a l'ouverture de la bougie h0, sortie a la cloture de h1, stop de secours a k x ATR."""
    b = bars(day, h0, h1)
    if len(b) < (h1 - h0 + 1) * 0.7 or b.h.iloc[0] != h0: return None
    a = G.atr[day]; e = b.open.iloc[0]; rk = k * a; x = b.close.iloc[-1]
    for hh, ll in zip(b.high.values, b.low.values):
        if side == 1 and ll <= e - rk: x = e - rk; break
        if side == -1 and hh >= e + rk: x = e + rk; break
    return (side * (x - e), COST, rk, side)

def breakout(day, lvl_hi, lvl_lo, h0, h1, mode="cassure", tgt=2.0, allow=(1, -1)):
    b = bars(day, h0, h1)
    if len(b) < 3: return None
    for i, (o, hh, ll, cc) in enumerate(b[["open", "high", "low", "close"]].values):
        if mode == "cassure":
            up, dn = hh > lvl_hi, ll < lvl_lo
            if up and dn: return None
            if up or dn:
                side = 1 if up else -1
                if side not in allow: return None
                e = max(o, lvl_hi) if up else min(o, lvl_lo); sl = (lvl_hi + lvl_lo) / 2
                break
        else:  # chasse : depasse le niveau puis cloture a l'interieur -> sens inverse, entree a la cloture
            if hh > lvl_hi and cc < lvl_hi: side, e, sl = -1, cc, hh
            elif ll < lvl_lo and cc > lvl_lo: side, e, sl = 1, cc, ll
            else: continue
            if side not in allow: return None
            break
    else:
        return None
    rk = side * (e - sl)
    if rk <= 0.03 * G.atr[day]: return None
    rest = b.iloc[i + (0 if mode == "cassure" else 1):]
    tp = e + side * tgt * rk; x = rest.close.iloc[-1] if len(rest) else e
    for j, (o, hh, ll, cc) in enumerate(rest[["open", "high", "low", "close"]].values):
        if j == 0 and mode == "cassure":
            # sur la bougie d'entree on ne regarde que le stop si la bougie l'atteint apres (prudent : stop d'abord)
            pass
        if (side == 1 and ll <= sl) or (side == -1 and hh >= sl): x = sl; break
        if (side == 1 and hh >= tp) or (side == -1 and ll <= tp): x = tp; break
    return (side * (x - e), COST, rk, side)

def strategies(day):
    r = G.loc[day]; out = {}
    if np.isnan(r.atr) or np.isnan(r.sma20): return out
    prev = G.index[G.index.get_loc(day) - 1] if G.index.get_loc(day) > 0 else None
    out["ASIE_ACHAT (or monte en Asie)"] = timed(day, 1, 1, 9)
    if prev is not None:
        us = bars(prev, 16, 22)
        if len(us) >= 5:
            s = 1 if us.close.iloc[-1] > us.open.iloc[0] else -1
            out["MOMENTUM_SESSION (sens de New York hier -> Asie)"] = timed(day, s, 1, 9)
    out["FIXING_VENTE (vente 16h-18h)"] = timed(day, -1, 16, 17)
    out["NY_VENTE (vente 16h-23h)"] = timed(day, -1, 16, 22)
    asia = bars(day, 1, 9)
    if len(asia) >= 7:
        ah, al = asia.high.max(), asia.low.min()
        out["CASSURE_ASIE a Londres"] = breakout(day, ah, al, 10, 18)
        out["CASSURE_ASIE + tendance"] = breakout(day, ah, al, 10, 18, allow=(int(r.trend),))
        out["CHASSE_ASIE (fausse cassure) a Londres"] = breakout(day, ah, al, 10, 18, mode="chasse")
        out["CHASSE_ASIE + tendance"] = breakout(day, ah, al, 10, 18, mode="chasse", allow=(int(r.trend),))
    ld = bars(day, 10, 15)
    if len(ld) >= 5:
        s = 1 if ld.close.iloc[-1] > ld.open.iloc[0] else -1
        out["LONDRES -> NEW YORK (continuation)"] = timed(day, s, 16, 18)
        out["LONDRES -> NEW YORK (retournement)"] = timed(day, -s, 16, 18)
    out["CASSURE_VEILLE + tendance"] = breakout(day, r.ph, r.pl, 10, 22, allow=(int(r.trend),), tgt=2.0)
    out["TENDANCE_JOUR (sens 20 j, 10h-23h)"] = timed(day, int(r.trend), 10, 22, k=0.5)
    return out

def main():
    recs = []
    for day in G.index:
        for name, v in strategies(day).items():
            if v is None: continue
            g, c, rk, side = v
            mise = 100 if side == 1 else 50
            recs.append(dict(day=day, strat=name, side=side, R_gross=g / rk, cost_R=c / rk, R=(g - c) / rk, eur=(g - c) / rk * mise))
    T = pd.DataFrame(recs); T.to_pickle(os.path.join(HERE, "or_sessions_trades.pkl"))
    rng = np.random.default_rng(1); rows = []
    for s, X in T.groupby("strat"):
        row = dict(strategie=s, trades=len(X))
        for lab, a, b in PER:
            row[lab] = round(X[(X.day >= a) & (X.day < b)].eur.sum())
        mise = np.where(X.side > 0, 100, 50)
        sims = np.array([((X.R_gross.values * rng.choice([-1, 1], len(X)) - X.cost_R.values) * mise).sum() for _ in range(2000)])
        row["total"] = round(X.eur.sum()); row["R_moy"] = round(X.R.mean(), 3)
        row["p_hasard"] = round(float((sims >= X.eur.sum()).mean()), 3)
        row["periodes_gagnantes"] = sum(row[l] > 0 for l, _, _ in PER)
        rows.append(row)
    R = pd.DataFrame(rows).sort_values("total", ascending=False)
    pd.set_option("display.width", 250); print(R.to_string(index=False)); R.to_csv(os.path.join(HERE, "or_sessions.csv"), index=False)

if __name__ == "__main__":
    main()
