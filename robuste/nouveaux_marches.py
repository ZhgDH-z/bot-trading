"""Copier les lignes DAX (1re bougie + zone de bruit) sur d'autres indices europeens, et les lignes US sur des actions
(demande d'aurele, 03/11/2026). Donnees : export M15 du 03/11/2026 (data_m15b). Heures serveur.
Regles : filtre de tendance 20 j comme la demo ; 1re bougie : pas le lundi, pas si bougie > 0,19 x ATR.
P = debut -> 02/11/2025, L = derniere annee 03/11/2025 -> 02/11/2026. Il faut gagner sur les DEUX."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sans_yen"))
import recherche, daytrade, daytrade2
from recherche import daily, atr
M15B = os.path.join(HERE, "..", "data_m15b")
EU = ["FRA40", "EUSTX50", "NETH25", "TECHDE30", "ESP35", "SWI20"]
ST = ["NVDA", "TSLA", "AAPL", "AMD", "META", "MSFT", "AMZN", "GOOGL", "NFLX"]

def load(sym):
    d = pd.read_csv(os.path.join(M15B, f"{sym}_M15.csv"))
    dec = max(len(str(x).split(".")[1]) if "." in str(x) else 0 for x in d.close.head(200))
    d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M"); d = d.set_index("time")
    d = d[d.index.dayofweek < 5]
    sp = float(np.median(d.spread_points.tail(20000))) * 10 ** (-dec)
    if sym in ST: sp = max(sp, 0.0004 * float(d.close.median()))
    recherche.SPREAD[sym] = sp
    return d

def tendance(df):
    d = daily(df); return np.sign(d.close.shift() - d.close.rolling(20).mean().shift()), atr(d, 14).shift()

rows = []
for sym in EU + ST:
    df = load(sym); tr, da = tendance(df)
    if sym in EU:
        lignes = {"1re bougie": daytrade.session_breakout(sym, df, (1000, 1000), (1015, 1015), 1815, one_dir="candle"),
                  "zone de bruit": daytrade2.noise(sym, df, open_hm=1000, last_hm=1815)}
    else:
        lignes = {"1re bougie": daytrade.session_breakout(sym, df, (1630, 1630), (1645, 1645), 2245, one_dir="candle"),
                  "zone de bruit": daytrade2.noise(sym, df, open_hm=1630, last_hm=2245)}
    for lig, tr_list in lignes.items():
        for t in tr_list:
            day = t["open_time"].normalize()
            tt = tr.get(day, np.nan); a = da.get(day, np.nan)
            if not np.isfinite(tt) or tt != t["side"]: continue      # filtre de tendance
            if lig == "1re bougie":
                if day.dayofweek == 0: continue
                if np.isfinite(a) and t["risk"] > 0.19 * a: continue
            rows.append(dict(sym=sym, ligne=lig, day=day, **t))
T = pd.DataFrame(rows)
T["per"] = np.where(T.day >= pd.Timestamp("2025-11-03"), "L", "P")
T = T[T.day <= pd.Timestamp("2026-11-02")]
T.to_pickle(os.path.join(HERE, "nouveaux_marches.pkl"))
g = T.groupby(["sym", "ligne", "per"]).R.agg(n="size", eur=lambda x: round(x.sum() * 1000), moy=lambda x: round(x.mean(), 3),
                                             g=lambda x: round(100 * (x > 0).mean())).unstack("per")
print(g.to_string())
print({s: recherche.SPREAD[s] for s in EU + ST})
