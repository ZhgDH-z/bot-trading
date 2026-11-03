"""OR EVOLUTIF (demande d'aurele) : le bot n'a pas UNE strategie pour toujours.
Il a des milliers de regles (sessions, sens, analyses), et CHAQUE MOIS il regarde lesquelles ont marche
sur les derniers mois, garde les meilleures, oublie celles qui se mettent a perdre, et joue le mois suivant.
Test honnete sur 14 ans d'or (bougies 1 h, 2012 -> 10/2026) : chaque mois est joue sans l'avoir vu."""
import numpy as np, pandas as pd, os
from or_sessions import D, G, COST
HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(7)

# --- matrices jour x heure
days = G.index[G.atr.notna() & G.sma20.notna()]
def mat(col):
    m = D.pivot_table(index="day", columns="h", values=col, aggfunc="first").reindex(index=days, columns=range(24))
    return m.values
O, H, L, C = mat("open"), mat("high"), mat("low"), mat("close")
atr = G.atr.reindex(days).values
F = pd.DataFrame(index=days)
F["tendance"] = np.sign(G.pc - G.sma20).reindex(days).values
F["veille"] = np.sign(G.pc - G.o.shift()).reindex(days).values
F["elan5"] = np.sign(G.pc - G.c.shift(6)).reindex(days).values
atr100 = pd.concat([G.hi - G.lo], axis=1).max(axis=1).ewm(alpha=1 / 100, adjust=False).mean().shift()
v = (G.atr / atr100).reindex(days).values
F["vol"] = np.where(v < 0.9, 0, np.where(v > 1.15, 2, 1))
F["jour"] = days.dayofweek
F["asie"] = np.sign(C[:, 9] - O[:, 1])
F["londres"] = np.sign(C[:, 15] - O[:, 10])
F["gap"] = np.sign(O[:, 1] - G.pc.reindex(days).values)
FEAT_OK_FROM = {"asie": 10, "londres": 16}    # analyses connues seulement apres cette heure
VALS = {"tendance": [1, -1], "veille": [1, -1], "elan5": [1, -1], "vol": [0, 1, 2], "jour": [0, 1, 2, 3, 4], "asie": [1, -1], "londres": [1, -1], "gap": [1, -1]}
H0 = [1, 3, 5, 8, 10, 12, 14, 15, 16, 17, 18, 20]
DUR = [1, 2, 3, 4, 6, 8]
MODES = ["achat", "vente", "suit_4h", "contre_4h", "tendance"]

def outcome(h0, dur, side, k=0.25):
    h1 = min(22, h0 + dur - 1)
    e = O[:, h0]; x = C[:, h1]
    lo = np.nanmin(L[:, h0:h1 + 1], axis=1); hi = np.nanmax(H[:, h0:h1 + 1], axis=1)
    rk = k * atr
    stop = np.where(side == 1, lo <= e - rk, hi >= e + rk)
    x = np.where(stop, e - side * rk, x)
    R = (side * (x - e) - COST) / rk
    return R

def rule_returns(r):
    h0, dur, mode = r["h0"], r["dur"], r["mode"]
    if mode == "achat": side = np.ones(len(days))
    elif mode == "vente": side = -np.ones(len(days))
    elif mode == "tendance": side = F.tendance.values.astype(float)
    else:
        a = max(0, h0 - 4)
        mv = np.sign(C[:, h0 - 1] - O[:, a]) if h0 >= 1 else np.zeros(len(days))
        side = mv if mode == "suit_4h" else -mv
    m = np.ones(len(days), bool)
    for f, val in r["conds"]: m &= F[f].values == val
    m &= ~np.isnan(O[:, h0]) & ~np.isnan(C[:, min(22, h0 + r["dur"] - 1)]) & (side != 0)
    R = np.full(len(days), np.nan)
    for sd in (1, -1):
        mm = m & (side == sd)
        if mm.any(): R[mm] = outcome(h0, dur, sd)[mm]
    eur = R * np.where(side > 0, 100, 50)
    return R, eur, side

def random_rule():
    h0 = int(rng.choice(H0))
    feats = [f for f in VALS if FEAT_OK_FROM.get(f, 0) <= h0]
    k = rng.integers(0, 3)
    fs = rng.choice(feats, size=k, replace=False) if k else []
    return dict(h0=h0, dur=int(rng.choice(DUR)), mode=str(rng.choice(MODES)), conds=tuple((f, int(rng.choice(VALS[f]))) for f in fs))

def describe(r):
    c = " et ".join(f"{f}={v}" for f, v in r["conds"]) or "toujours"
    return f"{r['h0']}h serveur pendant {r['dur']} h | {r['mode']} | si {c}"

if __name__ == "__main__":
    N = 4000
    rules = [random_rule() for _ in range(N)]
    Rm = np.full((N, len(days)), np.nan); Em = np.full((N, len(days)), np.nan)
    for i, r in enumerate(rules):
        Rm[i], Em[i], _ = rule_returns(r)
    month = days.to_period("M")
    months = month.unique()
    res = {}
    for LOOK in (6, 12, 24):
        for TOP in (3, 8):
            picks, rows = [], []
            for mi in range(LOOK, len(months)):
                past = (month >= months[mi - LOOK]) & (month < months[mi]); cur = month == months[mi]
                Rp = Rm[:, past]; n = np.sum(~np.isnan(Rp), axis=1)
                mean = np.nanmean(np.where(n[:, None] > 0, Rp, 0), axis=1)
                sd = np.nanstd(np.where(n[:, None] > 0, Rp, 0), axis=1) + 1e-9
                t = np.where(n >= max(10, LOOK * 2), mean / sd * np.sqrt(np.maximum(n, 1)), -9)
                order = np.argsort(-t)
                chosen = [i for i in order[:TOP * 3] if t[i] > 1.0][:TOP]
                # un seul trade a la fois sur l'or : a chaque jour, la regle la mieux classee qui declenche
                E = Em[:, cur]; day_eur = np.zeros(cur.sum()); day_n = np.zeros(cur.sum())
                for i in chosen:
                    fire = ~np.isnan(E[i]) & (day_n == 0)
                    day_eur[fire] += E[i][fire]; day_n[fire] += 1
                rows.append(pd.DataFrame({"day": days[cur], "eur": day_eur, "n": day_n}))
                picks.append((str(months[mi]), [describe(rules[i]) for i in chosen]))
            X = pd.concat(rows); X = X[X.n > 0]
            res[(LOOK, TOP)] = (X, picks)
            by = X.groupby(X.day.dt.year).eur.sum().round().astype(int)
            eq = X.eur.cumsum()
            print(f"Memoire {LOOK} mois, {TOP} regles : {len(X)} trades ({len(X)/len(days[month>=months[LOOK]]):.2f}/jour), total {round(X.eur.sum())} EUR, pire baisse {round((eq-eq.cummax()).min())}")
            print("   par an :", by.to_dict())
    import pickle
    with open(os.path.join(HERE, "or_evolutif.pkl"), "wb") as fh: pickle.dump((rules, res), fh)
