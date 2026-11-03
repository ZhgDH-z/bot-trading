"""
Module "achat sur repli" pour les indices (S&P 500, Nasdaq, DAX...), en journalier.

Regles (inspirees des strategies RSI(2) de Larry Connors, testees publiquement depuis les annees 2000) :
  - Filtre de tendance : on n'achete QUE si la cloture est au-dessus de la moyenne 200 jours
  - Signal : RSI(2) sous 10 (l'indice vient de baisser 2-3 jours d'affilee)
  - Entree a l'ouverture du jour suivant
  - Sortie : cloture au-dessus de la moyenne 5 jours (le rebond), ou apres 10 jours maximum
  - Stop de securite : 3 x ATR(20) journalier sous l'entree (krach)
  - Achat seulement, une position a la fois par indice

Couts : spread reel exporte du broker + financement overnight des CFD (taux annuel ~7 % du nominal).

Usage :
    python indices_backtest.py export/US500_D1.csv export/NAS100_D1.csv ...
"""
import os
import sys

import numpy as np
import pandas as pd

SPLIT = pd.Timestamp("2018-01-01")
FINANCING_PER_YEAR = 0.07  # cout de financement d'un achat de CFD indice, par an


def load_export(path):
    """CSV exporte par ExportHistory.mq5 : time,open,high,low,close,tick_volume,spread_points"""
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M")
    return df.set_index("time")


def rsi(close, n):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def atr(df, n):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def dip_buy(name, d, point, rsi_th=10, exit_ma=5, max_days=10, stop_atr=3.0, trend_ma=200):
    c = d["close"]
    r2 = rsi(c, 2).to_numpy()
    ma_t = c.rolling(trend_ma).mean().to_numpy()
    ma_x = c.rolling(exit_ma).mean().to_numpy()
    a = atr(d, 20).to_numpy()
    o, h, l, cl = (d[k].to_numpy() for k in ("open", "high", "low", "close"))
    spread = (d["spread_points"].to_numpy() * point) if "spread_points" in d else np.zeros(len(d))
    idx = d.index
    out, pos = [], None
    for i in range(trend_ma + 1, len(d)):
        if pos is None:
            if cl[i - 1] > ma_t[i - 1] and r2[i - 1] < rsi_th:
                e = o[i] + spread[i]
                pos = dict(entry=e, sl=e - stop_atr * a[i - 1], risk=stop_atr * a[i - 1], t=idx[i], i=i)
            else:
                continue
        px = None
        if l[i] <= pos["sl"]:
            px = min(o[i], pos["sl"])
        elif cl[i] > ma_x[i] or i - pos["i"] >= max_days:
            px = cl[i]
        if px is not None:
            days = max(1, (idx[i] - pos["t"]).days)
            fin = pos["entry"] * FINANCING_PER_YEAR * days / 365
            R = (px - pos["entry"] - fin) / pos["risk"]
            out.append(dict(symbol=name, side=1, open_time=pos["t"], close_time=idx[i],
                            entry=pos["entry"], exit=px, R=R, pct=(px - pos["entry"] - fin) / pos["entry"] * 100))
            pos = None
    return out


def main(paths):
    from multi_backtest import portfolio
    allt = []
    for p in paths:
        d = load_export(p)
        name = os.path.basename(p).replace("_D1.csv", "")
        dec = d["close"].astype(str).str.split(".").str[-1].str.len().max()
        point = 10 ** -int(dec)
        t = pd.DataFrame(dip_buy(name, d, point))
        if t.empty:
            continue
        win = (t.R > 0).mean() * 100
        print(f"{name:10s} {d.index[0].date()} -> {d.index[-1].date()}  trades {len(t):4d}  gagnants {win:4.0f} %  "
              f"R moyen {t.R.mean():+.3f}  (avant 2018 {t[t.open_time < SPLIT].R.mean():+.3f} / "
              f"apres {t[t.open_time >= SPLIT].R.mean():+.3f})  gain moyen {t.pct.mean():+.2f} %")
        allt.append(t)
    if allt:
        t = pd.concat(allt)
        st, yr, _ = portfolio(t, risk_pct=1.0)
        print("Portefeuille (1 % de risque par trade) :", st)
        print(yr.to_dict())
        t.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "indices_trades.csv"), index=False)


if __name__ == "__main__":
    main(sys.argv[1:])
