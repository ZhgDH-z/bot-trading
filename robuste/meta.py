"""ROBOT QUI APPREND (02/11/2026) : un 'chef d'orchestre' choisit, avant chaque trade, la strategie
a utiliser selon l'analyse du marche. Il n'apprend QUE sur le passe (re-entraine chaque mois)."""
import os, sys
import numpy as np, pandas as pd
from base import load, A_END
SY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sans_yen")

def library():
    L = pd.concat([pd.read_pickle(os.path.join(SY, "daytrade_trades.pkl")),
                   pd.read_pickle(os.path.join(SY, "daytrade2_trades.pkl"))], ignore_index=True)
    L = L[~L.symbol.str.contains("JPY")]
    # doublons quasi identiques (meme entree, autre sortie) : on garde les deux, ce sont deux "facons de jouer"
    L["day"] = L.open_time.dt.normalize()
    L = L.dropna(subset=["R"]).sort_values("open_time").reset_index(drop=True)
    return L

def daily_feats(sym):
    d = load(sym)
    g = d.groupby("day").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = g.c.shift()
    tr = pd.concat([g.h - g.l, (g.h - pc).abs(), (g.l - pc).abs()], axis=1).max(axis=1)
    f = pd.DataFrame(index=g.index)
    f["prevc"] = g.c.shift()
    f["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean().shift()
    f["atr100"] = tr.ewm(alpha=1 / 100, adjust=False).mean().shift()
    f["sma20"] = g.c.rolling(20).mean().shift()
    f["c5"] = g.c.shift(6)
    f["rng1"] = ((g.h - g.l) / f["atr"].shift(-0)).shift()   # range d'hier / ATR
    return f

def features(L):
    parts = []
    for sym, T in L.groupby("symbol"):
        f = daily_feats(sym)
        T = T.join(f, on="day")
        parts.append(T)
    X = pd.concat(parts).sort_values("open_time").reset_index(drop=True)
    s = X.side
    X["tend"] = np.sign(X.prevc - X.sma20) * s                       # +1 = trade dans le sens de la tendance 20 j
    X["ecart_ma"] = s * (X.prevc / X.sma20 - 1) / (X.atr / X.prevc)
    X["vol"] = X.atr / X.atr100                                        # >1 = marche plus agite que d'habitude
    X["deja"] = s * (X.entry - X.prevc) / X.atr                        # chemin deja fait dans le sens du trade
    X["mom5"] = s * (X.prevc / X.c5 - 1) / (X.atr / X.prevc)
    X["risk_atr"] = X.risk / X.atr
    X["heure"] = X.open_time.dt.hour
    X["jour"] = X.open_time.dt.dayofweek
    # forme recente de la ligne : moyenne des R des trades FERMES avant l'ouverture
    for n in (20, 60):
        X[f"forme{n}"] = np.nan
    for ln, T in X.groupby("ligne"):
        T = T.sort_values("open_time")
        closed = T.sort_values("close_time")[["close_time", "R"]]
        for n in (20, 60):
            roll = closed.R.rolling(n, min_periods=max(5, n // 3)).mean()
            ref = pd.DataFrame({"close_time": closed.close_time.values, "v": roll.values})
            m = pd.merge_asof(T[["open_time"]].reset_index(), ref, left_on="open_time", right_on="close_time",
                              direction="backward", allow_exact_matches=False)
            X.loc[m["index"].values, f"forme{n}"] = m.v.values
    return X

FEATS = ["tend", "ecart_ma", "vol", "deja", "mom5", "risk_atr", "heure", "jour", "forme20", "forme60", "side"]

def one_per_symbol_day(T, score):
    """Un seul trade par marche et par jour : le premier qui passe le seuil (a egalite d'heure, le meilleur score)."""
    T = T.assign(score=score).sort_values(["open_time", "score"], ascending=[True, False])
    return T.drop_duplicates(["symbol", "day"], keep="first")

def walk_forward(X, start="2023-01-01"):
    from sklearn.ensemble import HistGradientBoostingRegressor
    lines = sorted(X.ligne.unique()); lid = {l: i for i, l in enumerate(lines)}
    X = X.copy(); X["lid"] = X.ligne.map(lid)
    X["p_gb"] = np.nan; X["p_tab"] = np.nan
    months = pd.date_range(start, X.open_time.max() + pd.offsets.MonthBegin(1), freq="MS")
    for m0, m1 in zip(months[:-1], months[1:]):
        tr = X[X.close_time < m0]; te = X[(X.open_time >= m0) & (X.open_time < m1)]
        if len(te) == 0: continue
        # 1) IA : gradient boosting sur le passe (R plafonne pour ne pas apprendre les gros coups de chance)
        y = tr.R.clip(-1.5, 3)
        mdl = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                            min_samples_leaf=200, l2_regularization=1.0,
                                            categorical_features=[len(FEATS)], random_state=0)
        mdl.fit(tr[FEATS + ["lid"]].values, y.values)
        X.loc[te.index, "p_gb"] = mdl.predict(te[FEATS + ["lid"]].values)
        # 2) table de regimes : ligne x (avec/contre tendance) x volatilite (3 niveaux), moyenne passee
        def key(df): return df.ligne + "|" + df.tend.astype(str) + "|" + pd.cut(df.vol, [0, 0.9, 1.15, 9], labels=["calme", "normal", "agite"]).astype(str)
        tab = tr.groupby(key(tr)).R.agg(["mean", "count"])
        k = key(te)
        mm = tab["mean"].reindex(k).values; cc = tab["count"].reindex(k).fillna(0).values
        X.loc[te.index, "p_tab"] = np.where(cc >= 40, mm, np.nan)
    return X

def stats(T, label):
    A = T[T.day < A_END]; B = T[T.day >= A_END]
    eq = T.sort_values("open_time").R.cumsum() * 100
    nd = T.day.nunique()
    return dict(choix=label, trades=len(T), par_jour=round(len(T) / max(1, T.day.dt.to_period("D").nunique()), 2),
                eur_2023_24=round(A.R.sum() * 100), eur_2025_26=round(B.R.sum() * 100), moyR=round(T.R.mean(), 3),
                gagnants_pct=round((T.R > 0).mean() * 100), pire_baisse=round(float((eq - eq.cummax()).min())))

def random_p(pool, chosen, n_sim=2000, seed=3):
    """Hasard : chaque mois, on tire au sort autant de trades que le robot en a pris, parmi TOUS les trades possibles."""
    rng = np.random.default_rng(seed)
    pool = pool.assign(mo=pool.open_time.dt.to_period("M")); chosen = chosen.assign(mo=chosen.open_time.dt.to_period("M"))
    cnt = chosen.groupby("mo").size()
    groups = {m: pool.R.values[pool.mo.values == m] for m in cnt.index}
    actual = chosen.R.sum()
    sims = np.zeros(n_sim)
    for m, c in cnt.items():
        g = groups[m]
        if len(g) == 0: continue
        idx = rng.integers(0, len(g), size=(n_sim, min(c, len(g))))
        sims += g[idx].sum(axis=1)
    return float((sims >= actual).mean()), float(np.median(sims) * 100)

if __name__ == "__main__":
    L = library()
    print("bibliotheque :", len(L), "trades,", L.ligne.nunique(), "lignes,", L.open_time.min(), "->", L.open_time.max())
    X = features(L)
    X = walk_forward(X)
    X.to_pickle("meta_preds.pkl")
    P = X[X.open_time >= "2023-01-01"].copy()
    rows = []
    rows.append(stats(one_per_symbol_day(P, 0), "tout prendre (1er signal du jour par marche)"))
    for thr in (0.0, 0.05, 0.10):
        C = P[P.p_gb > thr]; C = one_per_symbol_day(C, C.p_gb)
        s = stats(C, f"IA (gradient boosting) > {thr}"); s["p_hasard"], s["hasard_median"] = random_p(P, C); rows.append(s)
    for thr in (0.0, 0.05):
        C = P[P.p_tab > thr]; C = one_per_symbol_day(C, C.p_tab)
        s = stats(C, f"table de regimes > {thr}"); s["p_hasard"], s["hasard_median"] = random_p(P, C); rows.append(s)
    for thr in (0.0, 0.05):
        C = P[P.forme60 > thr]; C = one_per_symbol_day(C, C.forme60)
        s = stats(C, f"forme recente 60 trades > {thr}"); s["p_hasard"], s["hasard_median"] = random_p(P, C); rows.append(s)
    C = P[(P.tend > 0)]; C = one_per_symbol_day(C, 0)
    s = stats(C, "regle simple : seulement dans le sens de la tendance"); s["p_hasard"], s["hasard_median"] = random_p(P, C); rows.append(s)
    R = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(R.to_string(index=False))
    R.to_csv("meta_resultats.csv", index=False)
