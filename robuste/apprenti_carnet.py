"""Ajoute l'Apprenti v2 (DAX, or, 3 indices US ; seuil 0,10 R) au journal hebdo (carnet2_data.json)."""
import json, numpy as np, pandas as pd
from zoneinfo import ZoneInfo
from base import load
from apprenti import SESS, portefeuille, NOM_FAM
NY, PAR = ZoneInfo("America/New_York"), ZoneInfo("Europe/Paris")
def paris(ts):
    t = (pd.to_datetime(pd.Series(ts)) - pd.Timedelta(hours=7)).dt.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward")
    return t.dt.tz_convert(PAR).dt.tz_localize(None).values
VAR = {"S03_T05": (0.3, 0.5), "S03_T10": (0.3, 1.0), "S03_FIN": (0.3, None), "S05_T05": (0.5, 0.5), "S05_FIN": (0.5, None), "S015_FIN": (0.15, None)}
NOM = {"DE40": "DAX", "XAUUSD": "Or", "US500": "S&P 500", "USTECH100M": "Nasdaq 100", "US30": "Dow Jones"}
T = pd.read_pickle("apprenti2_DE40_XAUUSD_US500_USTECH100M_US30.pkl")
S = portefeuille(T[T.EX >= 0.10]).copy()
# heure de sortie exacte
outs = []
for r in S.itertuples():
    d = load(r.sym); op, cl = SESS[r.sym]; t = d.index.values
    i0 = np.searchsorted(t, np.datetime64(r.t_in)); i1 = i0
    while i1 + 1 < len(t) and d.day.values[i1 + 1] == d.day.values[i0] and d.hm.values[i1 + 1] < cl: i1 += 1
    g = d.groupby("day").agg(h=("high", "max"), l=("low", "min"), c=("close", "last")); pc = g.c.shift()
    a = pd.concat([g.h - g.l, (g.h - pc).abs(), (g.l - pc).abs()], axis=1).max(axis=1).ewm(alpha=1 / 14, adjust=False).mean().shift().loc[r.day]
    sm, tm = VAR[r.sortie]; e = d.open.values[i0]; s = r.side; sd = sm * a
    hh = d.high.values[i0:i1 + 1]; ll = d.low.values[i0:i1 + 1]
    hs = (ll <= e - s * sd) if s == 1 else (hh >= e - s * sd)
    js = np.argmax(hs) if hs.any() else 10 ** 9
    if tm: ht = (hh >= e + s * tm * sd) if s == 1 else (ll <= e + s * tm * sd); jt = np.argmax(ht) if ht.any() else 10 ** 9
    else: jt = 10 ** 9
    j = (i1 - i0) if (js == 10 ** 9 and jt == 10 ** 9) else min(js, jt)
    outs.append(t[i0 + j] + np.timedelta64(15, "m"))
S["t_out"] = outs
S = S[S.day >= "2024-12-30"]
S["op"] = paris(S.t_in); S["cl"] = paris(S.t_out)
D = json.load(open("carnet2_data.json"))
D["trades"] = [t for t in D["trades"] if t[0] != "APPRENTI"]; D["summary"] = [s for s in D["summary"] if s["id"] != "APPRENTI"]
weeks = D["weeks"]
new = []
for r in S.itertuples():
    op = pd.Timestamp(r.op); wk = (op.normalize() - pd.Timedelta(days=op.dayofweek)).strftime("%Y-%m-%d")
    new.append(["APPRENTI", f"{NOM[r.sym]} · {NOM_FAM[r.fam]}", int(r.side), op.strftime("%Y-%m-%d %H:%M"),
                pd.Timestamp(r.cl).strftime("%Y-%m-%d %H:%M"), int(round(r.R * 100)), wk, int(round(r.P * 100))])
e = np.array([t[5] for t in new]); W = pd.Series(0.0, index=weeks)
for t in new:
    if t[6] in W.index: W[t[6]] += t[5]
summ = dict(id="APPRENTI", nom="L'Apprenti (setups + mémoire)",
            desc="Analyse le marché en continu, garde chaque setup en mémoire et ne trade que si les setups ressemblants du passé ont gagné. DAX, or, S&P 500, Nasdaq, Dow Jones.",
            trades=len(new), gagnants=int((e > 0).sum()), perdants=int((e < 0).sum()), total=int(e.sum()),
            moy_trade=float(round(e.mean(), 1)), sem_pos=int(round(100 * (W > 0).mean())), moy_sem=int(round(W.mean())),
            pire_sem=int(W.min()), meilleure_sem=int(W.max()))
D["summary"].insert(0, summ); D["trades"] += new
json.dump(D, open("carnet2_data.json", "w"), ensure_ascii=False)
print(summ)
n = S.groupby(S.op.astype("datetime64[ns]").dt.normalize()).size(); print("par jour", n.mean(), (n >= 3).mean())
print("sans 5 meilleures semaines", W.sum() - W.nlargest(5).sum(), "semaines", (W > 0).sum(), (W < 0).sum(), W[W < 0].sum())
print(S.groupby("sym").R.agg(n="size", eur=lambda x: round(x.sum() * 100), tg=lambda x: round(100 * (x > 0).mean())))
