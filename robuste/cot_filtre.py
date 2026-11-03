"""Idée cot-contrarian-detector (03/11/2026) : position des fonds spéculatifs (managed money) sur l'or,
rapport COT de la CFTC (contrat 088691). Rapport du mardi publié le vendredi -> utilisable dès le lundi suivant.
Filtres testés sur les trades or de la v1.03 : choix sur P, vérification sur L."""
import os, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
c = pd.read_csv(os.path.join(HERE, "cot_or.csv"), parse_dates=["date"])
c["net"] = (c.mm_long - c.mm_short) / c.oi
c["pct"] = c.net.rolling(156, min_periods=104).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True)
c["chg"] = c.net.diff()
c["dispo"] = c.date + pd.Timedelta(days=6)
T = pd.read_pickle(os.path.join(HERE, "v103_trades.pkl"))
T["day"] = pd.to_datetime(T.day)
T = T.sort_values("day")
m = pd.merge_asof(T, c[["dispo", "pct", "chg"]].sort_values("dispo"), left_on="day", right_on="dispo")
G = m.symbol == "XAUUSD"
base = {p: m[m.per == p].R.sum() * 1000 for p in "PL"}
print("Base v1.03 : P %+.0f €, L %+.0f €" % (base["P"], base["L"]))
print("Or, couverture COT :", m[G].pct.notna().mean().round(2))
rows = []
for x in [0.7, 0.8, 0.9]:
    crowd = G & (((m.side > 0) & (m.pct > x)) | ((m.side < 0) & (m.pct < 1 - x)))
    rows.append((f"retirer les trades dans le sens de la foule (seuil {x})", crowd))
    contre = G & (((m.side > 0) & (m.pct < 1 - x)) | ((m.side < 0) & (m.pct > x)))
    rows.append((f"retirer les trades contre la foule (seuil {x})", contre))
rows.append(("retirer si le trade va contre la variation de la semaine", G & (np.sign(m.chg) == -m.side)))
rows.append(("retirer si le trade suit la variation de la semaine", G & (np.sign(m.chg) == m.side)))
for nom, out in rows:
    r = {p: (m[(m.per == p) & ~out].R.sum() * 1000 - base[p], int((out & (m.per == p)).sum())) for p in "PL"}
    print(f"{nom:62s} P {r['P'][0]:+8.0f} € ({r['P'][1]} retirés)   L {r['L'][0]:+8.0f} € ({r['L'][1]} retirés)")
