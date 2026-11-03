"""
Vrai test hors echantillon : les couples strategie + marche retenus dans MultiBot,
rejoues sur les donnees H1 exportees du broker d'aurele (ExportHistory.mq5), de mars 2022 a aujourd'hui.
Ces donnees n'ont jamais servi a choisir les reglages.

Usage : python test_2022_2026.py <dossier_export>
"""
import os
import sys

import pandas as pd

import multi_backtest as mb
from indices_backtest import load_export

CONFIG = [
    ("S1 croisement MM (video, achat+vente)", "GBPJPY"),
    ("S1 croisement MM (video, achat+vente)", "GBPUSD"),
    ("S1b croisement MM (video, achat seul)", "USDJPY"),
    ("S1b croisement MM (video, achat seul)", "EURJPY"),
    ("S3 cassure de Londres", "USDJPY"),
    ("S5 MM 50/200 (2e video)", "GBPJPY"),
    ("S3 cassure de Londres", "XAUUSD"),
]
START = os.environ.get("START", "2022-03-01")


def main(export_dir):
    rows, trades = [], []
    for strat, sym in CONFIG:
        path = os.path.join(export_dir, f"{sym}_H1.csv")
        if not os.path.exists(path):
            print("manquant :", path)
            continue
        df = load_export(path)[["open", "high", "low", "close"]]
        # on garde 300 bougies avant le debut pour initialiser les moyennes
        first = df.index.searchsorted(pd.Timestamp(START))
        df = df.iloc[max(0, first - 300):]
        t = pd.DataFrame(mb.STRATEGIES[strat](sym, df))
        t = t[t.open_time >= START]
        trades.append(t)
        rows.append(dict(strategie=strat, marche=sym, trades=len(t), R_moyen=round(t.R.mean(), 3),
                         gagnants_pct=round((t.R > 0).mean() * 100)))
    print(pd.DataFrame(rows).to_string(index=False))
    t = pd.concat(trades)
    for label, sub in (("sans l'or", t[t.symbol != "XAUUSD"]), ("avec l'or", t)):
        st, yr, _ = mb.portfolio(sub, risk_pct=0.5)
        print(label, st)
        print(yr.to_dict())
    t.to_csv(os.path.join(mb.HERE, "results", "trades_2022_2026.csv"), index=False)


if __name__ == "__main__":
    main(sys.argv[1])
