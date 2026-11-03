"""Carnet semaine par semaine (demande d'aurele) : chaque trade a 100 EUR (gain = R x 100, achats ET ventes),
heures de Paris, 01/2025 -> 02/11/2026."""
import os, sys, json, numpy as np, pandas as pd
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "or"))
NY, PAR = ZoneInfo("America/New_York"), ZoneInfo("Europe/Paris")
def paris(ts):
    t = (pd.to_datetime(pd.Series(ts)) - pd.Timedelta(hours=7)).dt.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward")
    return t.dt.tz_convert(PAR).dt.tz_localize(None).values
START = pd.Timestamp("2025-01-01")
out = []   # (strat, marche, side, open, close, eur)

# 1) bot de la demo v1.01 et v1.02 (DAX)
X = pd.read_pickle(os.path.join(HERE, "meta_preds.pkl"))
bot = X[X.ligne.isin(["ORB15dir_DAX:DE40", "BRUIT_DAX:DE40", "IB_OR:XAUUSD"]) & (X.tend > 0)].copy()
bot["op"], bot["cl"] = paris(bot.open_time), paris(bot.close_time)
NOMS = {"ORB15dir_DAX:DE40": "DAX 1re bougie", "BRUIT_DAX:DE40": "DAX zone de bruit", "IB_OR:XAUUSD": "Or Initial Balance"}
for r in bot.itertuples():
    out.append(("DEMO", NOMS[r.ligne], r.side, r.op, r.cl, r.R * 100))
dax = bot[bot.ligne == "ORB15dir_DAX:DE40"]
v102 = bot[~((bot.ligne == "ORB15dir_DAX:DE40") & ((bot.risk_atr > 0.189) | (bot.jour == 0)))]
for r in v102.itertuples():
    out.append(("V102", NOMS[r.ligne], r.side, r.op, r.cl, r.R * 100))

# 2) or tendance du jour (bougies 1 h, spread 0,15)
os.environ["OR_COST"] = "0.15"
import or_sessions as O
for day in O.G.index[O.G.index >= START]:
    r = O.G.loc[day]
    if np.isnan(r.atr) or np.isnan(r.sma20): continue
    b = O.bars(day, 10, 22)
    if len(b) < 9 or b.h.iloc[0] != 10: continue
    side = int(np.sign(r.pc - r.sma20)); e = b.open.iloc[0]; rk = 0.5 * r.atr
    x, t1 = b.close.iloc[-1], b.index[-1] + pd.Timedelta(hours=1)
    for t, hh, ll in zip(b.index, b.high.values, b.low.values):
        if side == 1 and ll <= e - rk: x, t1 = e - rk, t + pd.Timedelta(minutes=30); break
        if side == -1 and hh >= e + rk: x, t1 = e + rk, t + pd.Timedelta(minutes=30); break
    R = (side * (x - e) - 0.15) / rk
    op = paris([b.index[0]])[0]; cl = paris([t1])[0]
    for s in ("ORTEND", "V102"):
        out.append((s, "Or tendance du jour", side, op, cl, R * 100))

# 3) stratégie unique DAX (score de votes)
from unique import run
U = run("DE40", seuil=1, vwap_exit=False)
for r in U.itertuples():
    t0 = pd.Timestamp(r.day) + pd.Timedelta(hours=10, minutes=15)
    out.append(("UNIQUE", "DAX score des analyses", r.side, paris([t0])[0], paris([r.t1 + pd.Timedelta(minutes=15)])[0], r.R * 100))

# 4) labo : regles inventees (tous marches), joue hors echantillon
L = pd.read_pickle(os.path.join(HERE, "labo_trades_test.pkl"))
SESS_OPEN = {"DE40": 1000, "US500": 1630, "USTECH100M": 1630, "US30": 1630, "XAUUSD": 1630, "XAGUSD": 1630, "EURUSD": 1000, "GBPUSD": 1000}
rules = pd.read_pickle(os.path.join(HERE, "labo_regles.pkl"))[0] if False else None
import pickle
rules, picked = pickle.load(open(os.path.join(HERE, "labo_regles.pkl"), "rb"))
for r in L.itertuples():
    rule = rules[int(r.regle)]; o = SESS_OPEN[r.sym]; add = 15 if rule["dt"] == "15min" else 60
    t0 = pd.Timestamp(r.day) + pd.Timedelta(hours=o // 100, minutes=o % 100 + add)
    out.append(("LABO", r.sym, int(r.side), paris([t0])[0], None, r.R * 100))

T = pd.DataFrame(out, columns=["s", "m", "side", "op", "cl", "eur"])
T = T[(T.op >= START)].dropna(subset=["op", "eur"]).sort_values("op")
T["wk"] = (T.op.dt.normalize() - pd.to_timedelta(T.op.dt.dayofweek, unit="D")).dt.strftime("%Y-%m-%d")
weeks = sorted(T.wk.unique())
META = {
 "V102": ("Bot proposé v1.02", "Démo actuelle + 2 correctifs DAX (pas de grosse 1re bougie, pas de lundi) + or dans le sens de la tendance"),
 "DEMO": ("Bot de la démo v1.01", "DAX 1re bougie, DAX zone de bruit, or Initial Balance, filtre de tendance 20 jours"),
 "ORTEND": ("Or tendance du jour", "1 trade par jour sur l'or dans le sens de la tendance 20 jours, 9h → 22h"),
 "UNIQUE": ("DAX : une seule stratégie", "Toutes les analyses votent (bougie, tendance, gap, élan, VWAP), avec les 2 correctifs"),
 "LABO": ("Labo : règles inventées", "Règles imaginées par le bot, apprises sur le passé et jouées sur des mois jamais vus (tous marchés)"),
}
summ = []
for k, (nom, desc) in META.items():
    g = T[T.s == k]
    w = g.groupby("wk").eur.sum().reindex(weeks, fill_value=0)
    summ.append(dict(id=k, nom=nom, desc=desc, trades=len(g), gagnants=int((g.eur > 0).sum()), perdants=int((g.eur <= 0).sum()),
                     total=int(round(g.eur.sum())), moy_trade=round(g.eur.mean(), 1), sem_pos=int(round((w > 0).mean() * 100)),
                     moy_sem=int(round(w.mean())), pire_sem=int(round(w.min())), meilleure_sem=int(round(w.max()))))
fmt = lambda t: None if t is None or pd.isna(t) else pd.Timestamp(t).strftime("%Y-%m-%d %H:%M")
trades = [[r.s, r.m, int(r.side), fmt(r.op), fmt(r.cl), int(round(r.eur)), r.wk] for r in T.itertuples()]
json.dump(dict(weeks=weeks, summary=summ, trades=trades), open(os.path.join(HERE, "carnet2_data.json"), "w"), separators=(",", ":"), ensure_ascii=False)
print(len(trades), "trades", len(weeks), "semaines", weeks[0], weeks[-1])
for s in summ: print(s)
