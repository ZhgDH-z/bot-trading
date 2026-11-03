"""Prepare les trades (test final 07/2024 -> 10/2026) de toutes les strategies testees, en heure de Paris,
avec 100 EUR de risque par trade (gain en EUR = R x 100)."""
import pandas as pd, numpy as np, json
from zoneinfo import ZoneInfo
NY, PAR = ZoneInfo("America/New_York"), ZoneInfo("Europe/Paris")

def paris(ts):
    # heure serveur MT5 = heure de New York + 7 h
    t = (pd.to_datetime(ts) - pd.Timedelta(hours=7)).dt.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward")
    return t.dt.tz_convert(PAR).dt.tz_localize(None)

NAMES = {
 "ORB30_US": ("Cassure des 30 premières minutes US", "jour"),
 "ORB30_DAX": ("Cassure des 30 premières minutes du DAX", "jour"),
 "ORB15dir_US": ("1re bougie de 15 min US (Zarattini & Aziz 2023)", "jour"),
 "ORB15dir_US_10R": ("1re bougie de 15 min US, objectif 10 R", "jour"),
 "ORB15dir_DAX": ("1re bougie de 15 min du DAX", "jour"),
 "LONDON15": ("Cassure de Londres (range asiatique)", "jour"),
 "LONDON15_1R": ("Cassure de Londres, objectif 1 R", "jour"),
 "VWAP_US": ("Retour à la VWAP, indices US", "jour"),
 "VWAP_DAX": ("Retour à la VWAP, DAX", "jour"),
 "VWAP_FX": ("Retour à la VWAP, forex et métaux", "jour"),
 "BRUIT_US": ("Zone de bruit US (Zarattini, Aziz, Barbon 2024)", "jour"),
 "BRUIT_DAX": ("Zone de bruit, DAX", "jour"),
 "IB_OR": ("Initial Balance sur l'or (TradeThatSwing)", "jour"),
 "IB_INDICES": ("Initial Balance sur les indices US", "jour"),
 "SILVER_BULLET": ("ICT Silver Bullet (10h-11h New York)", "jour"),
 "CHASSE_ASIE": ("Chasse de liquidité du range asiatique (ICT)", "jour"),
 "CHASSE_US": ("Chasse de liquidité à l'ouverture US (ICT)", "jour"),
 "VWAP_TENDANCE": ("Tendance VWAP (Zarattini & Aziz 2023)", "jour"),
 "SANSYEN": ("Bot SansYen (positions de plusieurs heures à plusieurs jours)", "swing"),
}
T = pd.concat([pd.read_pickle("daytrade_trades.pkl"), pd.read_pickle("daytrade2_trades.pkl")])
S = pd.read_csv("trades_test_final_qualite.csv", parse_dates=["open_time", "close_time"])
S["strat"] = "SANSYEN"; S["ligne"] = "SANSYEN:" + S["ligne"].str.replace("RSI2_25", "DIP").str.replace("REPLI_US", "REPLI").str.replace("DONCHIAN", "DONCH")
T = pd.concat([T, S[S.open_time >= "2024-07-01"]], ignore_index=True)
T = T[T.open_time >= "2025-01-01"].copy()
T["op"], T["cl"] = paris(T.open_time), paris(T.close_time)
T = T.dropna(subset=["op", "cl"])
T["eur"] = (T.R * 100).round(0)
T["wk"] = (T.op.dt.normalize() - pd.to_timedelta(T.op.dt.dayofweek, unit="D")).dt.strftime("%Y-%m-%d")
T["sub"] = T.ligne.str.split(":").str[-1] if False else T.ligne.str.replace(r"^[^:]+:", "", regex=True)
weeks = sorted(T.wk.unique())
# resume par strategie sur toutes les semaines du test
rows = []
for st, g in T.groupby("strat"):
    w = g.groupby("wk").eur.sum().reindex(weeks, fill_value=0)
    rows.append(dict(id=st, nom=NAMES[st][0], type=NAMES[st][1], trades=len(g), par_semaine=round(len(g) / len(weeks), 1),
                     gagnants=round((g.R > 0).mean() * 100), moy_sem=round(w.mean()), sem_pos=round((w > 0).mean() * 100),
                     total=int(g.eur.sum()), pire_sem=int(w.min()), meilleure_sem=int(w.max())))
summary = sorted(rows, key=lambda r: -r["moy_sem"])
trades = [[r.strat, r.sub, int(r.side), r.op.strftime("%Y-%m-%d %H:%M"), r.cl.strftime("%Y-%m-%d %H:%M"), int(r.eur), r.wk]
          for r in T.sort_values("op").itertuples()]
json.dump(dict(weeks=weeks, summary=summary, trades=trades), open("semaine_data.json", "w"), separators=(",", ":"), ensure_ascii=False)
print(len(trades), "trades,", len(weeks), "semaines, derniere :", weeks[-1])
last = T[T.wk == weeks[-1]]
print(last.groupby("strat").eur.agg(["count", "sum"]).to_string())
for r in summary: print(r)
