import pandas as pd, numpy as np
from daytrade import load15
from recherche import atr, daily
T = pd.concat([pd.read_pickle("daytrade_trades.pkl"), pd.read_pickle("daytrade2_trades.pkl")])
T = T[T.strat.isin(["ORB15dir_DAX", "BRUIT_DAX", "IB_OR"])].copy()
T["eur"] = T.R * 100
T["an"] = T.open_time.dt.year
T["jour"] = T.open_time.dt.dayofweek
T["h"] = T.open_time.dt.hour
T["duree_h"] = (T.close_time - T.open_time) / pd.Timedelta(hours=1)
# volatilite : ATR journalier relatif et taille du risque / ATR
feat = []
for sym in T.symbol.unique():
    d = daily(load15(sym)); a = atr(d, 14).shift(); a20 = (d.high - d.low).rolling(60).mean().shift()
    ma = d.close.rolling(20).mean().shift(); pc = d.close.shift()
    f = pd.DataFrame({"atr": a, "atr_rel": a / a20, "tend": np.sign(pc - ma), "gap": (d.open - pc) / a})
    f["symbol"] = sym; feat.append(f)
F = pd.concat(feat).reset_index().rename(columns={"index": "day", "time": "day"})
F = F.rename(columns={F.columns[0]: "day"})
T["day"] = T.open_time.dt.normalize()
T = T.merge(F, on=["symbol", "day"], how="left")
T["risk_atr"] = T.risk / T.atr
T["avec_tend"] = (T.side == T.tend)
T["sortie"] = np.where(T.R <= -0.95, "stop", np.where(T.R > 0.9, "gros gain", "fin de journee / autre"))
pd.set_option("display.width", 250)
R = T[T.open_time >= "2025-01-01"]
for st, g in R.groupby("strat"):
    print("\n=====", st, len(g), "trades, total", round(g.eur.sum()), "EUR")
    print("par annee :", g.groupby("an").eur.agg(["count", "sum"]).round(0).to_dict("index"))
    print("par sens :", g.groupby("side").eur.agg(["count", "mean", "sum"]).round(0).to_dict("index"))
    print("par jour :", g.groupby("jour").eur.agg(["count", "sum"]).round(0).to_dict("index"))
    print("dans le sens de la tendance 20 j :", g.groupby("avec_tend").eur.agg(["count", "mean", "sum"]).round(0).to_dict("index"))
    print("sortie :", g.groupby("sortie").eur.agg(["count", "sum"]).round(0).to_dict("index"))
    for col, bins in (("risk_atr", [0, .1, .2, .3, .5, 1, 9]), ("atr_rel", [0, .8, 1, 1.2, 1.5, 9]), ("gap", [-9, -.5, -.2, .2, .5, 9])):
        x = g.groupby(pd.cut(g[col], bins), observed=True).eur.agg(["count", "mean", "sum"]).round(0)
        print(col, x.to_dict("index"))
    # serie de pertes
    s = (g.sort_values("open_time").eur < 0).astype(int)
    runs = s.groupby((s != s.shift()).cumsum()).sum()
    print("plus longue serie de pertes :", runs.max())
T.to_pickle("trio_features.pkl")
