import pandas as pd, numpy as np
from recherche import SPREAD
T = pd.read_pickle("daytrade_trades.pkl")
g = T.groupby(["ligne", "periode"]).R.agg(["count", "mean"]).unstack()
keep = list(g[(g[("mean", "A_conception")] > 0) & (g[("count", "A_conception")] >= 100)].index)
print("Lignes retenues sur la conception :", keep)
B = T[(T.periode == "B_test") & T.ligne.isin(keep)].copy()
A = T[(T.periode == "A_conception") & T.ligne.isin(keep)].copy()
DEMO = {'US500':0.4,'US30':0.9,'USTECH100M':2.2,'DE40':0.3}
for X in (A, B):
    X["R_demo"] = X.R + X.symbol.map(SPREAD) * 1.2 / X.risk - X.symbol.map(DEMO) / X.risk

def stats(t, col, risk):
    t = t.sort_values("close_time")
    eq = pd.Series(10000 * np.cumprod(1 + risk / 100 * t[col].values), index=t.close_time.values)
    yrs = (t.close_time.max() - t.open_time.min()).days / 365.25
    dd = (eq / np.maximum.accumulate(np.r_[10000, eq.values])[1:] - 1).min()
    m = eq.resample("ME").last(); mr = m.pct_change().fillna(m.iloc[0] / 10000 - 1)
    bd = pd.bdate_range(t.open_time.min(), t.close_time.max())
    days = t.open_time.dt.normalize().nunique()
    wins = (t[col] > 0).mean()
    return dict(trades=len(t), par_jour=round(len(t) / len(bd), 1), jours_avec_trade_pct=round(days / len(bd) * 100),
                gagnants_pct=round(wins * 100), R_moyen=round(t[col].mean(), 3),
                par_an_pct=round(((eq.iloc[-1] / 10000) ** (1 / yrs) - 1) * 100, 1), pire_baisse_pct=round(dd * 100, 1),
                mois_positifs_pct=round((mr > 0).mean() * 100))
for name, X in (("CONCEPTION", A), ("TEST FINAL", B)):
    for col in ("R", "R_demo"):
        print(name, col, stats(X, col, 0.25))
print(B.groupby("ligne")[["R", "R_demo"]].mean().round(3))
# hasard : memes entrees et sorties, sens tire au hasard
rng = np.random.default_rng(1)
cost = B.symbol.map(SPREAD) * 1.2 / B.risk
gross_move = (B.R + cost) * B.side  # mouvement dans le sens achat, en R
sims = [((gross_move * rng.choice([-1, 1], len(B))) - cost).mean() for _ in range(2000)]
print("TEST FINAL : strategie", round(B.R.mean(), 3), "| hasard median", round(np.median(sims), 3),
      "| hasard fait mieux", round((np.array(sims) >= B.R.mean()).mean() * 100), "%")
