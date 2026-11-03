"""DAX 1re bougie : 3 règles du dépôt trade-skills rejouées sur bougies 15 min (03/11/2026).
Piège 30 : stop au moins x fois l'ATR du jour ; piège 4 : se retourner après le stop ; piège 27 : entrer sur le retest du milieu."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from base import load, cost
V = pd.read_pickle(os.path.join(HERE, "v103_trades.pkl")); V["day"] = pd.to_datetime(V.day)
D = V[V.ligne == "DAX 1re bougie"].copy()
d = load("DE40"); cs = cost("DE40")
def path(day):
    x = d[(d.day == day) & (d.hm >= 1015) & (d.hm <= 1815)]
    return x
def run_stop(e, side, rk, x, from_i=0):
    """sortie au stop (rk) ou à 18:30 ; renvoie (pnl en points, index de sortie, stoppé ?)"""
    sp = e - side * rk
    for i in range(from_i, len(x)):
        if (x.low.iloc[i] <= sp) if side > 0 else (x.high.iloc[i] >= sp): return -rk, i, True
    return side * (x.close.iloc[-1] - e), len(x) - 1, False
rows = []
for r in D.itertuples():
    x = path(r.day)
    if len(x) < 10: continue
    e, side, rk, atr = r.entry, r.side, r.risk, r.atr
    base_pts, i_stop, stopped = run_stop(e, side, rk, x)
    row = dict(day=r.day, per=r.per, R_ref=r.R, R_base=(base_pts - cs) / rk)
    for k in [0.2, 0.25, 0.3]:
        rk2 = max(rk, k * atr); p, _, _ = run_stop(e, side, rk2, x); row[f"stop_min_{k}"] = (p - cs) / rk2
    # retournement après le stop : nouvelle position inverse au prix du stop, même risque
    if stopped and i_stop < len(x) - 2:
        e2 = e - side * rk; p2, _, _ = run_stop(e2, -side, rk, x, i_stop + 1)
        row["flip"] = row["R_base"] + (p2 - cs) / rk
    else: row["flip"] = row["R_base"]
    # retest : ordre limite au milieu de la 1re bougie jusqu'à 12:00, stop de l'autre côté de la bougie
    mid = e - side * rk / 2; rk3 = rk / 2; xr = x[x.hm < 1200]; hit = None
    for i in range(len(xr)):
        if (xr.low.iloc[i] <= mid) if side > 0 else (xr.high.iloc[i] >= mid): hit = i; break
    if hit is None: row["retest"] = 0.0; row["retest_pris"] = 0
    else:
        # prudence : si la bougie du retest touche aussi le stop, on compte la perte
        p3, _, _ = run_stop(mid, side, rk3, x, hit); row["retest"] = (p3 - cs) / rk3; row["retest_pris"] = 1
    rows.append(row)
R = pd.DataFrame(rows)
print("contrôle (moteur vs v1.03) : écart moyen", round((R.R_base - R.R_ref).abs().mean(), 3))
for c in ["R_base", "stop_min_0.2", "stop_min_0.25", "stop_min_0.3", "flip", "retest"]:
    print(f"{c:15s} P {R[R.per=='P'][c].sum()*1000:+9.0f} €   L {R[R.per=='L'][c].sum()*1000:+9.0f} €")
print("retests pris :", R.groupby("per").retest_pris.sum().to_dict(), "sur", R.groupby("per").size().to_dict())
R.to_pickle(os.path.join(HERE, "ts_dax1b.pkl"))
