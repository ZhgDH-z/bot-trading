"""
Backtest de la strategie de la video "Il cree un bot de trading rentable avec ChatGPT"
(Impact Trading, janvier 2026), reproduite fidelement :

- USD/JPY, unite de temps H1
- Croisement de 2 moyennes mobiles : la rapide (collee au prix) passe au-dessus de la lente (lissee) -> ACHAT
- Achat uniquement, jamais de vente / contre-tendance
- Stop loss 55 pips + trailing stop 55 pips qui demarre au meme niveau que le stop loss
- Une seule position a la fois ; apres la cloture on attend le prochain croisement
- Strategie evaluee uniquement a l'ouverture d'une nouvelle bougie (signal sur la bougie cloturee)
- Pas d'entree entre 23h et 1h (heure serveur), filtre de spread
- Lot fixe 0,7 pour 10 000 de capital (ou lot automatique proportionnel au capital)

Pas de martingale, pas de grid. Swaps ignores (voir rapport).

Usage :
    python backtest.py                 # backtest avec les parametres par defaut + rapport
    python backtest.py --grid          # teste toutes les periodes de moyennes (robustesse / sur-optimisation)
"""
import argparse
import itertools
import json
import os
import random

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PIP = 0.01  # 1 pip sur une paire en JPY


# ---------------------------------------------------------------- donnees
def load_h1(path):
    df = pd.read_csv(path, parse_dates=["Date"])
    for c in ("open", "high", "low", "close"):
        df[c] = df[c] / 1000.0  # le fichier stocke les prix x1000
    return df.set_index("Date")


# ---------------------------------------------------------------- indicateurs (memes formules que MetaTrader)
def moving_average(s, period, method):
    if method == "SMA":
        return s.rolling(period).mean()
    if method == "EMA":
        return s.ewm(span=period, adjust=False).mean()
    if method == "SMMA":  # MODE_SMMA de MetaTrader = moyenne de Wilder
        return s.ewm(alpha=1.0 / period, adjust=False).mean()
    if method == "LWMA":
        w = np.arange(1, period + 1)
        return s.rolling(period).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)
    raise ValueError(method)


# ---------------------------------------------------------------- moteur de backtest
def backtest(df, fast=8, slow=30, fast_method="EMA", slow_method="SMMA",
             sl_pips=55, trail_pips=55, spread_pips=1.0, slippage_pips=0.3,
             lots_per_10k=0.7, auto_lot=False, capital=10_000.0,
             no_entry_from=23, no_entry_to=1, random_entries=None, seed=0):
    """Retourne (liste de trades, serie d'equity journaliere)."""
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    hours = df.index.hour.to_numpy()
    n = len(df)

    if random_entries is None:
        f = moving_average(df["close"], fast, fast_method).to_numpy()
        s = moving_average(df["close"], slow, slow_method).to_numpy()
        # signal a l'ouverture de la bougie i : croisement entre les bougies cloturees i-2 et i-1
        cross = np.zeros(n, dtype=bool)
        cross[2:] = (f[1:-1] > s[1:-1]) & (f[:-2] <= s[:-2])
    else:
        rng = random.Random(seed)
        cross = np.zeros(n, dtype=bool)
        for i in rng.sample(range(2, n), random_entries):
            cross[i] = True

    spread, slip = spread_pips * PIP, slippage_pips * PIP
    balance = capital
    trades = []
    pos = None  # dict(entry, sl, lots, i)
    equity = np.empty(n)

    for i in range(n):
        if pos is None and cross[i]:
            hr = hours[i]
            blocked = (hr >= no_entry_from or hr < no_entry_to) if no_entry_from > no_entry_to \
                else (no_entry_from <= hr < no_entry_to)
            if not blocked:
                lots = lots_per_10k * (balance / 10_000.0 if auto_lot else capital / 10_000.0)
                lots = max(0.01, round(lots, 2))
                entry = o[i] + spread + slip  # achat au prix ask
                pos = dict(entry=entry, sl=entry - sl_pips * PIP, lots=lots, i=i)

        if pos is not None:
            exit_px = None
            # Ordre intra-bougie inconnu en H1 : si la bougie est baissiere on suppose
            # que le plus haut est venu avant le plus bas (hypothese prudente).
            bearish = c[i] < o[i]
            if o[i] <= pos["sl"] and i > pos["i"]:
                exit_px = o[i] - slip  # gap sous le stop
            else:
                if bearish:
                    pos["sl"] = max(pos["sl"], h[i] - trail_pips * PIP)
                if l[i] <= pos["sl"]:
                    exit_px = pos["sl"] - slip
                elif not bearish:
                    pos["sl"] = max(pos["sl"], h[i] - trail_pips * PIP)
            if exit_px is not None:
                pnl_jpy = (exit_px - pos["entry"]) * pos["lots"] * 100_000
                pnl = pnl_jpy / exit_px  # conversion en USD
                balance += pnl
                trades.append(dict(open_time=df.index[pos["i"]], close_time=df.index[i],
                                   entry=round(pos["entry"], 3), exit=round(exit_px, 3),
                                   lots=pos["lots"], pips=round((exit_px - pos["entry"]) / PIP, 1),
                                   pnl=round(pnl, 2), balance=round(balance, 2)))
                pos = None

        floating = 0.0
        if pos is not None:
            floating = (c[i] - spread - pos["entry"]) * pos["lots"] * 100_000 / c[i]
        equity[i] = balance + floating

    eq = pd.Series(equity, index=df.index)
    return pd.DataFrame(trades), eq


def stats(trades, eq, capital=10_000.0):
    if trades.empty:
        return dict(trades=0)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    final = eq.iloc[-1]
    dd = (eq / eq.cummax() - 1).min()
    wins, losses = trades[trades.pnl > 0], trades[trades.pnl <= 0]
    pf = wins.pnl.sum() / -losses.pnl.sum() if len(losses) and losses.pnl.sum() < 0 else float("inf")
    cagr = (final / capital) ** (1 / years) - 1 if final > 0 else -1.0
    return dict(
        trades=len(trades),
        net_profit_usd=round(final - capital, 0),
        total_return_pct=round((final / capital - 1) * 100, 1),
        cagr_pct=round(cagr * 100, 1),
        max_drawdown_pct=round(dd * 100, 1),
        win_rate_pct=round(len(wins) / len(trades) * 100, 1),
        profit_factor=round(pf, 2),
        avg_win_pips=round(wins.pips.mean(), 1) if len(wins) else 0,
        avg_loss_pips=round(losses.pips.mean(), 1) if len(losses) else 0,
        calmar=round(cagr / -dd, 2) if dd < 0 else None,
    )


def yearly_returns(eq):
    y = eq.resample("YE").last()
    start = pd.concat([pd.Series([eq.iloc[0]]), y.iloc[:-1]]).to_numpy()
    return pd.Series((y.to_numpy() / start - 1) * 100, index=y.index.year).round(1)


def monthly_returns(eq):
    m = eq.resample("ME").last()
    start = pd.concat([pd.Series([eq.iloc[0]]), m.iloc[:-1]]).to_numpy()
    return pd.Series((m.to_numpy() / start - 1) * 100, index=m.index)


# ---------------------------------------------------------------- grille de robustesse
FASTS = [2, 3, 5, 8, 10, 13]
SLOWS = [20, 30, 50, 75, 100, 150, 200]
METHODS = [("EMA", "EMA"), ("SMA", "SMA"), ("EMA", "SMMA")]


def run_grid(df, split="2018-01-01"):
    rows = []
    ins, oos = df[df.index < split], df[df.index >= split]
    for (fm, sm), fast, slow in itertools.product(METHODS, FASTS, SLOWS):
        if fast >= slow:
            continue
        p = dict(fast=fast, slow=slow, fast_method=fm, slow_method=sm)
        r = dict(**p)
        for name, part in (("full", df), ("in", ins), ("oos", oos)):
            t, e = backtest(part, **p)
            st = stats(t, e)
            r[f"{name}_ret"] = st.get("total_return_pct", 0)
            r[f"{name}_dd"] = st.get("max_drawdown_pct", 0)
            r[f"{name}_pf"] = st.get("profit_factor", 0)
            r[f"{name}_n"] = st.get("trades", 0)
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "data", "USDJPYh1.csv"))
    ap.add_argument("--fast", type=int, default=8)
    ap.add_argument("--slow", type=int, default=30)
    ap.add_argument("--fast-method", default="EMA")
    ap.add_argument("--slow-method", default="SMMA")
    ap.add_argument("--lots-per-10k", type=float, default=0.7)
    ap.add_argument("--spread", type=float, default=1.0)
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    df = load_h1(a.data)
    print(f"Donnees : {df.index[0]} -> {df.index[-1]}  ({len(df)} bougies H1)")

    if a.grid:
        g = run_grid(df)
        g.to_csv(os.path.join(a.out, "grid.csv"), index=False)
        print(g.sort_values("in_ret", ascending=False).head(15).to_string())
        return

    p = dict(fast=a.fast, slow=a.slow, fast_method=a.fast_method, slow_method=a.slow_method,
             lots_per_10k=a.lots_per_10k, spread_pips=a.spread)
    trades, eq = backtest(df, **p)
    st = stats(trades, eq)
    print(json.dumps(st, indent=2))
    print(yearly_returns(eq).to_string())
    trades.to_csv(os.path.join(a.out, "trades.csv"), index=False)
    eq.resample("W").last().to_csv(os.path.join(a.out, "equity_weekly.csv"))


if __name__ == "__main__":
    main()
