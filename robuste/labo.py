"""LABORATOIRE : le bot invente SES PROPRES regles a partir de son analyse du marche (02/11/2026).
1. Chaque jour, sur chaque marche, il note 10 analyses (sens de la 1re bougie / 1re heure, tendance 20 j,
   gap, elan 5 j, position vs VWAP, volatilite, taille du range, jour, veille, cassure du haut/bas de la veille).
2. Il imagine des milliers de regles au hasard : 'si analyse A = x et analyse B = y, alors achat/vente,
   stop ..., sortie ...'.
3. Il garde celles qui ont le mieux marche sur le PASSE seulement, puis il les joue sur l'annee suivante
   qu'il n'a jamais vue (2024, puis 2025-2026).
4. Controle : le meme processus avec des regles choisies au hasard."""
import numpy as np, pandas as pd, itertools, pickle, os
from base import load, cost

SESS = {"DE40": (1000, 1815), "US500": (1630, 2245), "USTECH100M": (1630, 2245), "US30": (1630, 2245),
        "XAUUSD": (1630, 2245), "XAGUSD": (1630, 2245), "EURUSD": (1000, 1815), "GBPUSD": (1000, 1815)}
DT = {"15min": 1, "1h": 4}     # nombre de bougies de 15 min observees avant de decider
FEATS = ["bougie", "tendance", "gap", "elan5", "vwap", "vol", "range", "jour", "veille", "cassure"]
OUTS = [(st, ex) for st in ("range", "atr25") for ex in ("fin", "2R")]

def tm(h): return h // 100 * 60 + h % 100

def build(sym):
    op, cl = SESS[sym]; d = load(sym)
    g = d.groupby("day").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = g.c.shift()
    tr = pd.concat([g.h - g.l, (g.h - pc).abs(), (g.l - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean().shift(); atr100 = tr.ewm(alpha=1 / 100, adjust=False).mean().shift()
    sma = g.c.rolling(20).mean().shift(); c6 = g.c.shift(6); pc1 = g.c.shift(); po1 = g.o.shift()
    ph, pl = g.h.shift(), g.l.shift()
    sclose = d[d.hm == cl].groupby("day").close.last().reindex(g.index).ffill().shift()
    rows = []
    for day, gg in d.groupby("day"):
        a = atr.get(day, np.nan)
        if np.isnan(a) or np.isnan(sma.get(day, np.nan)) or np.isnan(sclose.get(day, np.nan)) or np.isnan(c6.get(day, np.nan)): continue
        hmv = gg.hm.values
        sess = gg[(hmv >= op) & (hmv <= cl)]
        if len(sess) < 8 or sess.hm.values[0] != op or sess.hm.values[-1] != cl: continue
        O, H, L, C, V = (sess[k].values.astype(float) for k in ("open", "high", "low", "close", "tick_volume"))
        V = np.maximum(V, 1)
        for dtn, nb in DT.items():
            wo, wh, wl, wc = O[0], H[:nb].max(), L[:nb].min(), C[nb - 1]
            vw = ((H[:nb] + L[:nb] + C[:nb]) / 3 * V[:nb]).sum() / V[:nb].sum()
            f = dict(sym=sym, day=day, dt=dtn,
                     bougie=1 if wc > wo else -1, tendance=1 if pc1[day] > sma[day] else -1,
                     gap=1 if wo > sclose[day] else -1, elan5=1 if pc1[day] > c6[day] else -1,
                     vwap=1 if wc > vw else -1, vol=a / atr100[day], range=(wh - wl) / a,
                     jour=day.dayofweek, veille=1 if pc1[day] > po1[day] else -1,
                     cassure=1 if wc > ph[day] else (-1 if wc < pl[day] else 0))
            e = O[nb]
            for side in (1, -1):
                for st, ex in OUTS:
                    sl = (wl if side == 1 else wh) if st == "range" else e - side * 0.25 * a
                    rk = side * (e - sl)
                    if rk <= 0.03 * a: f[f"R_{side}_{st}_{ex}"] = np.nan; continue
                    tp = e + side * 2 * rk if ex == "2R" else None
                    x = C[-1]
                    for k in range(nb, len(C)):
                        if (side == 1 and L[k] <= sl) or (side == -1 and H[k] >= sl):
                            x = min(O[k], sl) if side == 1 else max(O[k], sl); break
                        if tp is not None and ((side == 1 and H[k] >= tp) or (side == -1 and L[k] <= tp)):
                            x = tp; break
                    f[f"R_{side}_{st}_{ex}"] = (side * (x - e) - cost(sym)) / rk
            rows.append(f)
    return pd.DataFrame(rows)

def get_table():
    p = "labo_table.pkl"
    if os.path.exists(p): return pd.read_pickle(p)
    T = pd.concat([build(s) for s in SESS], ignore_index=True)
    # terciles fixes (calcules sur 2022-2023, avant tout test)
    for c in ("vol", "range"):
        q = T[T.day < "2024-01-01"].groupby(["sym", "dt"])[c].quantile([1 / 3, 2 / 3]).unstack()
        lo = T.set_index(["sym", "dt"]).index.map(q[1 / 3]); hi = T.set_index(["sym", "dt"]).index.map(q[2 / 3])
        T[c] = np.where(T[c].values <= lo, 0, np.where(T[c].values >= hi, 2, 1))
    T.to_pickle(p); return T

VALS = {"bougie": [1, -1], "tendance": [1, -1], "gap": [1, -1], "elan5": [1, -1], "vwap": [1, -1], "vol": [0, 1, 2],
        "range": [0, 1, 2], "jour": [0, 1, 2, 3, 4], "veille": [1, -1], "cassure": [1, 0, -1]}
SIDE_MODES = ["achat", "vente", "suit_bougie", "contre_bougie"]

def random_rule(rng, syms):
    k = rng.integers(1, 4)
    fs = rng.choice(FEATS, size=k, replace=False)
    return dict(sym=rng.choice(syms), dt=rng.choice(list(DT)), side=rng.choice(SIDE_MODES),
                conds=tuple((f, rng.choice(VALS[f])) for f in fs), out=OUTS[rng.integers(len(OUTS))])

def apply_rule(T, r):
    m = (T.sym.values == r["sym"]) & (T.dt.values == r["dt"])
    for f, v in r["conds"]: m &= T[f].values == v
    sub = T[m]
    if r["side"] == "achat": side = np.ones(len(sub), int)
    elif r["side"] == "vente": side = -np.ones(len(sub), int)
    elif r["side"] == "suit_bougie": side = sub.bougie.values
    else: side = -sub.bougie.values
    st, ex = r["out"]
    R = np.where(side == 1, sub[f"R_1_{st}_{ex}"].values, sub[f"R_-1_{st}_{ex}"].values)
    eur = R * np.where(side == 1, 100, 50)
    return pd.DataFrame({"day": sub.day.values, "sym": r["sym"], "side": side, "R": R, "eur": eur}).dropna()

def describe(r):
    c = " et ".join(f"{f}={v}" for f, v in r["conds"])
    return f"{r['sym']} apres {r['dt']} | si {c} -> {r['side']} | stop {r['out'][0]}, sortie {r['out'][1]}"

def select(T_train, rules, top=12, min_n=60, by_t=True):
    sc = []
    for i, r in enumerate(rules):
        X = apply_rule(T_train, r)
        if len(X) < min_n: continue
        t = X.R.mean() / (X.R.std(ddof=1) / np.sqrt(len(X)) + 1e-9)
        sc.append((t if by_t else 0, i, X.R.mean(), len(X)))
    return sc

def trade(T_test, rules, chosen):
    out = []
    for prio, i in enumerate(chosen):
        X = apply_rule(T_test, rules[i]); X["regle"] = i; X["prio"] = prio; out.append(X)
    if not out: return pd.DataFrame(columns=["day", "sym", "side", "R", "eur", "regle", "prio"])
    X = pd.concat(out).sort_values(["day", "sym", "prio"])
    return X.drop_duplicates(["day", "sym"], keep="first")   # un seul trade par marche et par jour

if __name__ == "__main__":
    T = get_table()
    print("table :", len(T), "lignes", T.day.min(), "->", T.day.max())
    rng = np.random.default_rng(42)
    rules = [random_rule(rng, list(SESS)) for _ in range(6000)]
    folds = [("2024-01-01", "2025-01-01"), ("2025-01-01", "2026-12-01")]
    allX, allRand, picked = [], [], []
    for t0, t1 in folds:
        tr = T[T.day < t0]; te = T[(T.day >= t0) & (T.day < t1)]
        sc = select(tr, rules)
        sc.sort(reverse=True)
        chosen = [i for t, i, m, n in sc if m > 0.1][:15]
        picked.append((t0, [(describe(rules[i]), round(m, 2), n) for t, i, m, n in sc[:15]]))
        X = trade(te, rules, chosen); X["pli"] = t0; allX.append(X)
        # hasard : 200 tirages de 15 regles parmi celles qui ont assez de trades
        elig = [i for t, i, m, n in sc]
        sims = []
        for _ in range(200):
            ch = list(rng.choice(elig, size=min(15, len(elig)), replace=False))
            sims.append(trade(te, rules, ch).eur.sum())
        allRand.append(np.array(sims))
        print(f"\nPli test {t0} -> {t1} : {len(X)} trades, {round(X.eur.sum())} EUR | hasard median {round(np.median(sims))}, proba hasard >= : {(np.array(sims) >= X.eur.sum()).mean():.3f}")
        for d_, m, n in picked[-1][1][:15]: print("   ", d_, "| R moyen passe", m, "| n", n)
    X = pd.concat(allX)
    X.to_pickle("labo_trades_test.pkl")
    with open("labo_regles.pkl", "wb") as fh: pickle.dump((rules, picked), fh)
    print("\nTOTAL hors echantillon 2024-2026 :", round(X.eur.sum()), "EUR,", len(X), "trades,",
          round(len(X) / pd.bdate_range("2024-01-01", "2026-11-02").size, 2), "par jour")
    print(X.groupby(X.day.dt.year).eur.sum().round())
    tot_sims = allRand[0] + allRand[1]
    print("hasard total median", round(np.median(tot_sims)), "| proba hasard >= :", (tot_sims >= X.eur.sum()).mean())
