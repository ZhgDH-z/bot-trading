"""
Backtest multi-marches : or + 11 paires forex, H1, nov. 2012 -> mars 2022.

4 strategies testees, toutes en "R" (gain ou perte divise par le risque pris au depart),
puis combinees en portefeuille avec un risque fixe de X % du capital par trade :

  S1  croisement_mm   : le bot de la video generalise (EMA 8 / SMMA 30 en H1),
                        achat ET vente, stop + trailing en ATR (au lieu de 55 pips fixes)
  S2  cassure_veille  : cassure du plus haut / plus bas de la veille (tres populaire sur l'or),
                        stop de l'autre cote du milieu de la veille, sortie en fin de journee
  S3  cassure_londres : range de la session asiatique, cassure a l'ouverture de Londres,
                        stop de l'autre cote du range, sortie en fin de journee
  S4  tendance_donchian : cassure du plus haut / plus bas de 20 jours (Turtle / "time series
                        momentum"), stop 2 ATR jour, sortie sur le canal de 10 jours

Couts : spread realiste par marche + glissement. Heures = heure serveur MT (GMT+2/+3).

Usage : python multi_backtest.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# diviseur de prix du fichier, spread typique (en prix)
MARKETS = {
    "XAUUSD": (100, 0.30),
    "EURUSD": (100_000, 0.00010),
    "GBPUSD": (100_000, 0.00015),
    "USDJPY": (1_000, 0.010),
    "AUDUSD": (100_000, 0.00012),
    "USDCAD": (100_000, 0.00018),
    "USDCHF": (100_000, 0.00015),
    "EURGBP": (100_000, 0.00015),
    "EURJPY": (1_000, 0.018),
    "GBPJPY": (1_000, 0.025),
    "AUDJPY": (1_000, 0.020),
    "EURCHF": (100_000, 0.00020),
}
SPLIT = pd.Timestamp("2018-01-01")  # avant = "dans l'echantillon", apres = "hors echantillon"


def load(sym):
    div, _ = MARKETS[sym]
    df = pd.read_csv(os.path.join(DATA, f"{sym}h1.csv"), parse_dates=["Date"]).set_index("Date")
    df = df[["open", "high", "low", "close"]] / div
    return df[df.index >= "2012-11-19"]


def atr(df, n):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def daily(df):
    d = df.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return d[d.index.dayofweek < 5]


def trade(sym, side, t_in, t_out, entry, exit_, risk, cost):
    r = (side * (exit_ - entry) - cost) / risk
    return dict(symbol=sym, side=side, open_time=t_in, close_time=t_out, entry=entry, exit=exit_, R=r)


# ------------------------------------------------------------------ S1 : bot de la video generalise
def s1_croisement_mm(sym, df, fast=8, slow=30, atr_mult=4.0, long_only=False):
    cost = MARKETS[sym][1] * 1.2
    f = df["close"].ewm(span=fast, adjust=False).mean().to_numpy()
    s = df["close"].ewm(alpha=1 / slow, adjust=False).mean().to_numpy()
    a = atr(df, 14).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    hr = df.index.hour.to_numpy()
    idx = df.index
    out, pos = [], None
    for i in range(2, len(df)):
        up = f[i - 1] > s[i - 1] and f[i - 2] <= s[i - 2]
        dn = f[i - 1] < s[i - 1] and f[i - 2] >= s[i - 2] and not long_only
        if pos is None and (up or dn) and not (hr[i] >= 23 or hr[i] < 1):
            side = 1 if up else -1
            dist = atr_mult * a[i - 1]
            pos = dict(side=side, entry=o[i], sl=o[i] - side * dist, dist=dist, t=idx[i])
        if pos is None:
            continue
        sd, dist = pos["side"], pos["dist"]
        bearish = c[i] < o[i]
        # ordre intra-bougie prudent : le mouvement favorable d'abord seulement s'il va dans ce sens
        fav_first = (sd == 1 and bearish) or (sd == -1 and not bearish)
        if fav_first:
            pos["sl"] = max(pos["sl"], h[i] - dist) if sd == 1 else min(pos["sl"], l[i] + dist)
        hit = l[i] <= pos["sl"] if sd == 1 else h[i] >= pos["sl"]
        if hit:
            px = pos["sl"]
            if (sd == 1 and o[i] < px) or (sd == -1 and o[i] > px):
                px = o[i]
            out.append(trade(sym, sd, pos["t"], idx[i], pos["entry"], px, dist, cost))
            pos = None
            continue
        if not fav_first:
            pos["sl"] = max(pos["sl"], h[i] - dist) if sd == 1 else min(pos["sl"], l[i] + dist)
    return out


# ------------------------------------------------------------------ outils "cassure intraday"
def intraday_breakout(sym, df, levels, start_hour, end_hour, exit_hour):
    """levels : dict date -> (niveau_achat, niveau_vente, stop_achat, stop_vente).
    Ordres stop poses de start_hour a end_hour, un seul trade par jour, sortie a exit_hour."""
    cost = MARKETS[sym][1] * 1.2
    out = []
    for day, g in df.groupby(df.index.date):
        lv = levels.get(pd.Timestamp(day))
        if lv is None:
            continue
        buy, sell, sl_b, sl_s = lv
        pos = None
        for t, (o, h, l, c) in zip(g.index, g[["open", "high", "low", "close"]].to_numpy()):
            hr = t.hour
            if pos is None:
                if hr < start_hour or hr > end_hour:
                    continue
                hit_b, hit_s = h >= buy, l <= sell
                if hit_b and hit_s:  # les deux dans la meme bougie : le plus proche de l'ouverture d'abord
                    hit_b = abs(buy - o) <= abs(o - sell)
                    hit_s = not hit_b
                if hit_b:
                    e = max(o, buy)
                    pos = dict(side=1, entry=e, sl=sl_b, risk=e - sl_b, t=t)
                elif hit_s:
                    e = min(o, sell)
                    pos = dict(side=-1, entry=e, sl=sl_s, risk=sl_s - e, t=t)
                else:
                    continue
                if pos["risk"] <= 0:
                    pos = None
                    continue
            sd = pos["side"]
            if (sd == 1 and l <= pos["sl"]) or (sd == -1 and h >= pos["sl"]):
                out.append(trade(sym, sd, pos["t"], t, pos["entry"], pos["sl"], pos["risk"], cost))
                break
            if hr >= exit_hour:
                out.append(trade(sym, sd, pos["t"], t, pos["entry"], c, pos["risk"], cost))
                break
        else:
            if pos is not None:
                out.append(trade(sym, pos["side"], pos["t"], g.index[-1], pos["entry"], g["close"].iloc[-1], pos["risk"], cost))
    return out


# ------------------------------------------------------------------ S2 : cassure du plus haut / bas de la veille
def s2_cassure_veille(sym, df):
    d = daily(df)
    prev = d.shift()
    levels = {}
    for day, (ph, pl) in zip(d.index, prev[["high", "low"]].to_numpy()):
        if np.isnan(ph):
            continue
        mid = (ph + pl) / 2
        levels[day] = (ph, pl, mid, mid)
    return intraday_breakout(sym, df, levels, start_hour=1, end_hour=20, exit_hour=23)


# ------------------------------------------------------------------ S3 : cassure de Londres (range asiatique)
def s3_cassure_londres(sym, df):
    asia = df[df.index.hour < 9]
    rng = asia.groupby(asia.index.date).agg(hi=("high", "max"), lo=("low", "min"))
    d_atr = atr(daily(df), 14).shift()
    levels = {}
    for day, (hi, lo) in rng.iterrows():
        day = pd.Timestamp(day)
        a = d_atr.get(day, np.nan)
        if np.isnan(a) or (hi - lo) > 1.2 * a or (hi - lo) < 0.15 * a:
            continue  # range trop grand (deja parti) ou trop petit (faux signaux)
        levels[day] = (hi, lo, lo, hi)
    return intraday_breakout(sym, df, levels, start_hour=9, end_hour=17, exit_hour=23)


# ------------------------------------------------------------------ S4 : tendance Donchian 20/10 jours
def s4_tendance_donchian(sym, df, n_in=20, n_out=10, stop_atr=2.0):
    cost = MARKETS[sym][1] * 1.2
    d = daily(df)
    a = atr(d, 20).to_numpy()
    hi_in = d["high"].rolling(n_in).max().shift().to_numpy()
    lo_in = d["low"].rolling(n_in).min().shift().to_numpy()
    hi_out = d["high"].rolling(n_out).max().shift().to_numpy()
    lo_out = d["low"].rolling(n_out).min().shift().to_numpy()
    o, h, l, c = (d[k].to_numpy() for k in ("open", "high", "low", "close"))
    out, pos = [], None
    for i in range(n_in + 1, len(d)):
        if pos is not None:
            sd = pos["side"]
            stop = max(pos["sl"], lo_out[i]) if sd == 1 else min(pos["sl"], hi_out[i])
            if (sd == 1 and l[i] <= stop) or (sd == -1 and h[i] >= stop):
                px = min(o[i], stop) if sd == 1 else max(o[i], stop)
                out.append(trade(sym, sd, pos["t"], d.index[i], pos["entry"], px, pos["risk"], cost))
                pos = None
            continue
        if h[i] > hi_in[i]:
            e = max(o[i], hi_in[i])
            pos = dict(side=1, entry=e, sl=e - stop_atr * a[i - 1], risk=stop_atr * a[i - 1], t=d.index[i])
        elif l[i] < lo_in[i]:
            e = min(o[i], lo_in[i])
            pos = dict(side=-1, entry=e, sl=e + stop_atr * a[i - 1], risk=stop_atr * a[i - 1], t=d.index[i])
    return out


# ------------------------------------------------------------------ S5 : robot de la 2e video (Paul Bourdeau)
def s5_mm_50_200(sym, df, fast=50, slow=200, sl_atr=4.5, tp_atr=9.0, trail_atr=1.8):
    """EMA 50 / EMA 200 en H1, achat ET vente, SL 500 pts / TP 1000 pts / trailing 200 pts sur EURUSD
    (convertis en ATR pour s'adapter a chaque marche), fermeture + retournement au croisement inverse."""
    cost = MARKETS[sym][1] * 1.2
    f = df["close"].ewm(span=fast, adjust=False).mean().to_numpy()
    s = df["close"].ewm(span=slow, adjust=False).mean().to_numpy()
    a = atr(df, 14).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    idx = df.index
    out, pos = [], None
    for i in range(slow, len(df)):
        up = f[i - 1] > s[i - 1] and f[i - 2] <= s[i - 2]
        dn = f[i - 1] < s[i - 1] and f[i - 2] >= s[i - 2]
        if pos is not None and ((up and pos["side"] == -1) or (dn and pos["side"] == 1)):
            out.append(trade(sym, pos["side"], pos["t"], idx[i], pos["entry"], o[i], pos["risk"], cost))
            pos = None
        if pos is None and (up or dn):
            sd = 1 if up else -1
            r = sl_atr * a[i - 1]
            pos = dict(side=sd, entry=o[i], sl=o[i] - sd * r, tp=o[i] + sd * tp_atr * a[i - 1],
                       risk=r, trail=trail_atr * a[i - 1], t=idx[i])
        if pos is None:
            continue
        sd = pos["side"]
        if (sd == 1 and l[i] <= pos["sl"]) or (sd == -1 and h[i] >= pos["sl"]):
            px = min(o[i], pos["sl"]) if sd == 1 else max(o[i], pos["sl"])
            out.append(trade(sym, sd, pos["t"], idx[i], pos["entry"], px, pos["risk"], cost))
            pos = None
            continue
        if (sd == 1 and h[i] >= pos["tp"]) or (sd == -1 and l[i] <= pos["tp"]):
            out.append(trade(sym, sd, pos["t"], idx[i], pos["entry"], pos["tp"], pos["risk"], cost))
            pos = None
            continue
        pos["sl"] = max(pos["sl"], c[i] - pos["trail"]) if sd == 1 else min(pos["sl"], c[i] + pos["trail"])
    return out


STRATEGIES = {
    "S1 croisement MM (video, achat+vente)": s1_croisement_mm,
    "S1b croisement MM (video, achat seul)": lambda s, d: s1_croisement_mm(s, d, long_only=True),
    "S2 cassure de la veille": s2_cassure_veille,
    "S3 cassure de Londres": s3_cassure_londres,
    "S4 tendance Donchian 20/10": s4_tendance_donchian,
    "S5 MM 50/200 (2e video)": s5_mm_50_200,
}


# ------------------------------------------------------------------ portefeuille
def portfolio(trades, risk_pct=0.5, capital=10_000.0):
    t = trades.sort_values("close_time")
    eq = capital * np.cumprod(1 + risk_pct / 100 * t["R"].to_numpy())
    eq = pd.Series(eq, index=t["close_time"].to_numpy())
    years = (t["close_time"].max() - t["open_time"].min()).days / 365.25
    dd = (eq / np.maximum.accumulate(np.r_[capital, eq.to_numpy()])[1:] - 1).min()
    wins, losses = t.R[t.R > 0].sum(), -t.R[t.R <= 0].sum()
    days = pd.bdate_range(t["open_time"].min(), t["open_time"].max())
    active = t["open_time"].dt.normalize().nunique()
    yearly = eq.groupby(eq.index.year).last()
    yr = (yearly / pd.concat([pd.Series([capital]), yearly.iloc[:-1]]).to_numpy() - 1) * 100
    return dict(
        trades=len(t),
        jours_avec_trade_pct=round(active / len(days) * 100),
        R_moyen=round(t.R.mean(), 3),
        profit_factor=round(wins / losses, 2),
        R_moyen_2012_2017=round(t[t.open_time < SPLIT].R.mean(), 3),
        R_moyen_2018_2022=round(t[t.open_time >= SPLIT].R.mean(), 3),
        rendement_total_pct=round((eq.iloc[-1] / capital - 1) * 100),
        rendement_annuel_pct=round(((eq.iloc[-1] / capital) ** (1 / years) - 1) * 100, 1),
        pire_baisse_pct=round(dd * 100, 1),
        annees_negatives=int((yr < 0).sum()),
    ), yr.round(1), eq


def main():
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    data = {s: load(s) for s in MARKETS}
    summary, per_symbol, yearly = {}, {}, {}
    all_trades = {}
    for name, fn in STRATEGIES.items():
        tr = pd.DataFrame([x for s in MARKETS for x in fn(s, data[s])])
        all_trades[name] = tr
        st, yr, _ = portfolio(tr)
        summary[name] = st
        yearly[name] = yr
        per_symbol[name] = tr.groupby("symbol").R.mean().round(3)
        print(name, st)
    pd.DataFrame(summary).T.to_csv(os.path.join(HERE, "results", "multi_summary.csv"))
    pd.DataFrame(per_symbol).to_csv(os.path.join(HERE, "results", "multi_par_marche.csv"))
    pd.DataFrame(yearly).to_csv(os.path.join(HERE, "results", "multi_par_annee.csv"))
    print(pd.DataFrame(per_symbol).to_string())
    print(pd.DataFrame(yearly).to_string())
    pd.to_pickle(all_trades, os.path.join(HERE, "results", "multi_trades.pkl"))


if __name__ == "__main__":
    main()
