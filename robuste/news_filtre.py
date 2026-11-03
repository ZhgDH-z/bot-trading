"""Filtre « annonces US » (03/11/2026), idée tirée de fxmacrodata-calendar.
Dates officielles via FRED (CPI release 10, Employment Situation release 50) et calendrier Fed (FOMC).
Heures serveur MT5 (= New York + 7 h) : CPI et NFP 8h30 NY = 15:30 ; FOMC 14h00 NY = 21:00.
Variantes testées sur v103_trades.pkl, P puis L, à 1 000 € par trade."""
import os, sys
import pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from base import load

CPI = """2022-12-13 2023-01-12 2023-02-14 2023-03-14 2023-04-12 2023-05-10 2023-06-13 2023-07-12 2023-08-10 2023-09-13 2023-10-12 2023-11-14 2023-12-12
2024-01-11 2024-02-13 2024-03-12 2024-04-10 2024-05-15 2024-06-12 2024-07-11 2024-08-14 2024-09-11 2024-10-10 2024-11-13 2024-12-11
2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18
2026-01-13 2026-02-13 2026-03-11 2026-04-10 2026-05-12 2026-06-10 2026-07-14 2026-08-12 2026-09-11 2026-10-14""".split()
NFP = """2022-12-02 2023-01-06 2023-02-03 2023-03-10 2023-04-07 2023-05-05 2023-06-02 2023-07-07 2023-08-04 2023-09-01 2023-10-06 2023-11-03 2023-12-08
2024-01-05 2024-02-02 2024-03-08 2024-04-05 2024-05-03 2024-06-07 2024-07-05 2024-08-02 2024-09-06 2024-10-04 2024-11-01 2024-12-06
2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06 2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16
2026-01-09 2026-02-11 2026-03-06 2026-04-03 2026-05-08 2026-06-05 2026-07-02 2026-08-07 2026-09-04 2026-10-02""".split()
FOMC = """2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13 2024-01-31 2024-03-20 2024-05-01 2024-06-12
2024-07-31 2024-09-18 2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28""".split()
EV = [(pd.Timestamp(d) + pd.Timedelta("15:30:00"), "CPI") for d in CPI] + \
     [(pd.Timestamp(d) + pd.Timedelta("15:30:00"), "NFP") for d in NFP] + \
     [(pd.Timestamp(d) + pd.Timedelta("21:00:00"), "FOMC") for d in FOMC]
EV = pd.DataFrame(EV, columns=["t", "type"])
EVDAY = {t.normalize(): ty for t, ty in zip(EV.t, EV.type)}

if __name__ == "__main__":
    T = pd.read_pickle(os.path.join(HERE, "v103_trades.pkl")).copy()
    T["day"] = pd.to_datetime(T["day"])
    T["evday"] = T.day.map(EVDAY)
    # événement pendant le trade ?
    def ev_during(r):
        e = EV[(EV.t > r.open_time) & (EV.t <= r.close_time)]
        return e.t.iloc[0] if len(e) else pd.NaT
    T["ev_t"] = T.apply(ev_during, axis=1)
    # trade ouvert juste avant/après l'annonce (de -60 min à +30 min)
    def near(r):
        d = (EV.t - r.open_time).dt.total_seconds() / 60
        return bool(((d >= -30) & (d <= 60)).any())
    T["near"] = T.apply(near, axis=1)

    # sortie juste avant l'annonce : prix de clôture de la bougie qui finit à l'heure de l'annonce
    def r_exit(r):
        if pd.isna(r.ev_t): return r.R
        d = load(r.symbol)
        bar = r.ev_t - pd.Timedelta(minutes=15)
        if bar not in d.index: return r.R
        px = d.loc[bar, "close"]
        return r.side * (px - r.entry) / r.risk - r.costR
    T["R_sortie"] = T.apply(r_exit, axis=1)

    def bilan(R, msk_keep, per):
        s = R[msk_keep & (T.per == per)]
        return len(s), round(s.sum() * 1000)

    lignes = {"Tout": T.ligne.notna(), "DAX": T.symbol == "DE40", "Or": T.symbol == "XAUUSD"}
    for k, v in [("Trades sur un jour d'annonce", T.evday.notna()), ("Annonce PENDANT le trade", T.ev_t.notna()), ("Ouvert de -30 à +60 min de l'annonce", T.near)]:
        for per in "PL":
            s = T[v & (T.per == per)]
            print(f"{k:40s} {per}: {len(s):4d} trades, {s.R.sum()*1000:+9.0f} €, moyenne {s.R.mean():+.2f} R")
    print()
    rows = []
    for nom, m in lignes.items():
        base = {p: bilan(T.R, T.ligne.notna(), p) for p in "PL"}
        var = {
            "Pas de trade le jour d'annonce": ~(m & T.evday.notna()),
            "Pas de trade le jour d'annonce (CPI+NFP seuls)": ~(m & T.evday.isin(["CPI", "NFP"])),
            "Pas d'ouverture de -30 à +60 min": ~(m & T.near),
            "Pas de trade traversant l'annonce": ~(m & T.ev_t.notna()),
        }
        for vn, keep in var.items():
            p, l = bilan(T.R, keep, "P"), bilan(T.R, keep, "L")
            rows.append((nom, vn, p[0], p[1] - base["P"][1], l[0], l[1] - base["L"][1]))
        Rs = T.R.where(~m, T.R_sortie)
        p, l = bilan(Rs, T.ligne.notna(), "P"), bilan(Rs, T.ligne.notna(), "L")
        rows.append((nom, "Sortir juste avant l'annonce", p[0], p[1] - base["P"][1], l[0], l[1] - base["L"][1]))
    R = pd.DataFrame(rows, columns=["marché", "variante", "P_trades", "P_écart_€", "L_trades", "L_écart_€"])
    print("Base v1.03 : P", bilan(T.R, T.ligne.notna(), "P"), " L", bilan(T.R, T.ligne.notna(), "L"))
    print(R.to_string())
    T.to_pickle(os.path.join(HERE, "news_trades.pkl"))
