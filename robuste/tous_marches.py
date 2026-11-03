"""Bot sur TOUS les marchés, stratégie ADAPTÉE à chaque marché (demande d'aurele, 03/11/2026 vers 2h30 Paris).
Méthode honnête :
 - un menu de stratégies intraday (fermées le jour même), fixé AVANT de regarder ;
 - pour chaque marché on choisit la meilleure sur P (2023 -> 02/11/2025) seulement ;
 - conditions sur P : au moins 60 trades, gain moyen >= 0,03 R, les 2 moitiés de P gagnantes ;
 - on regarde ensuite la dernière année L (03/11/2025 -> 02/11/2026), jamais utilisée pour choisir.
DAX et or : on garde la v1.05 telle quelle (déjà adaptée à ces 2 marchés)."""
import os, sys, itertools, numpy as np, pandas as pd
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "sans_yen"))
import recherche
from recherche import daily, atr, mk
from daytrade import session_breakout
from daytrade2 import noise, vwap_trend, initial_balance
import st_marches as stm

P0, PM, L0, L1 = pd.Timestamp("2023-01-01"), pd.Timestamp("2024-06-01"), pd.Timestamp("2025-11-03"), pd.Timestamp("2026-11-02")
EU = ["FRA40", "EUSTX50", "NETH25", "ESP35", "SWI20"]
USI = ["US500", "USTECH100M", "US30"]
ST = ["NVDA", "TSLA", "AAPL", "AMD", "META", "MSFT", "AMZN", "GOOGL", "NFLX"]
FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "EURGBP", "EURCHF"]
OTH = ["XAGUSD", "JPN225"]
ALL = EU + USI + ST + FX + OTH
NOMS = {"FRA40": "CAC 40", "EUSTX50": "Euro Stoxx 50", "NETH25": "AEX", "ESP35": "IBEX 35", "SWI20": "SMI",
        "US500": "S&P 500", "USTECH100M": "Nasdaq 100", "US30": "Dow Jones", "XAGUSD": "Argent", "JPN225": "Nikkei",
        "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD", "USDCHF": "USD/CHF",
        "EURGBP": "EUR/GBP", "EURCHF": "EUR/CHF"}

def add(hm, m):
    t = (hm // 100) * 60 + hm % 100 + m; return (t // 60) * 100 + t % 60

def sessions(sym):
    if sym in EU: return {"Europe": (1000, 1815)}
    if sym in USI + ST: return {"US": (1630, 2245)}
    if sym in FX: return {"Londres": (1000, 1845), "New York": (1630, 2245)}
    return {"Europe": (1000, 2245), "US": (1630, 2245)}   # argent, Nikkei

SPLITS = {"NFLX": (pd.Timestamp("2025-11-17"), 10.0)}   # NFLX : division par 10 le 17/11/2025, prix d'avant non ajustés
def load(sym):
    d = stm.load_a(sym) if sym in USI + FX + ["XAGUSD"] else stm.load_b(sym)
    d = d[d.index >= pd.Timestamp("2022-06-01")].copy()
    if sym in SPLITS:
        t, k = SPLITS[sym]; m = d.index < t
        for c in ["open", "high", "low", "close"]: d.loc[m, c] = d.loc[m, c] / k
    if sym in ST:   # coût = au moins 0,04 % du prix de la dernière année
        recherche.SPREAD[sym] = max(recherche.SPREAD[sym] if sym not in SPLITS else 0, 0.0004 * float(d.close[d.index >= L0].median()))
    return d

def st_trades(sym, d, m, k, o, e):
    b = d[["open", "high", "low", "close"]].copy(); pc = b.close.shift()
    tr = pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1)
    b["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    cs = recherche.SPREAD[sym] * 1.2
    r = stm.run(b, stm.st_sig(b, m), k, o, e, cs)
    return [dict(symbol=sym, side=x.side, open_time=x.t0, close_time=x.t1, R=x.R) for x in r.itertuples()]

def menu(sym, d):
    out = {}
    for sn, (o, e) in sessions(sym).items():
        out[f"1re bougie ({sn})"] = lambda o=o, e=e: session_breakout(sym, d, (o, o), (add(o, 15), add(o, 15)), e, one_dir="candle")
        out[f"Cassure 30 min ({sn})"] = lambda o=o, e=e: session_breakout(sym, d, (o, add(o, 15)), (add(o, 30), add(o, 240)), e)
        out[f"Zone de bruit ({sn})"] = lambda o=o, e=e: noise(sym, d, open_hm=o, last_hm=e)
        out[f"Tendance VWAP ({sn})"] = lambda o=o, e=e: vwap_trend(sym, d, start=o, end=e)
        out[f"Initial Balance ({sn})"] = lambda o=o, e=e: initial_balance(sym, d, ib=(o, add(o, 45)), last_entry=add(e, -45), exit_hm=e, minp=0.0015, maxp=0.03)
        out[f"Supertrend x4 ({sn})"] = lambda o=o, e=e: st_trades(sym, d, 4.0, 1.5, o, e)
        out[f"Supertrend x3 ({sn})"] = lambda o=o, e=e: st_trades(sym, d, 3.0, 1.5, o, e)
    return out

def one(sym):
    try: d = load(sym)
    except Exception as ex: return sym, None, str(ex)
    dd = daily(d); tend = np.sign(dd.close - dd.close.rolling(20).mean()).shift()
    res = {}
    for nom, f in menu(sym, d).items():
        try: t = pd.DataFrame(f())
        except Exception as ex: print(sym, nom, "erreur", ex, flush=True); continue
        if t.empty: continue
        t["day"] = pd.to_datetime(t.open_time).dt.normalize(); t = t[(t.day >= P0) & (t.day <= L1)]
        t = t[np.isfinite(t.R)]
        res[nom] = t[["symbol", "side", "open_time", "close_time", "R", "day"]]
        tt = tend.reindex(t.day).values
        res[nom + " + tendance 20 j"] = res[nom][tt == t.side.values]
    print(sym, "fini", flush=True)
    return sym, res, None

def stats(t):
    P = t[t.day < L0]; L = t[t.day >= L0]; P1, P2 = P[P.day < PM], P[P.day >= PM]
    return dict(nP=len(P), P=P.R.sum(), moyP=P.R.mean() if len(P) else 0, P1=P1.R.sum(), P2=P2.R.sum(), nL=len(L), L=L.R.sum())

if __name__ == "__main__":
    with Pool(8) as pool: allr = pool.map(one, ALL)
    rows, chosen = [], {}
    for sym, res, err in allr:
        if res is None: print(sym, "données illisibles :", err); continue
        for nom, t in res.items():
            rows.append(dict(sym=sym, strat=nom, **stats(t)))
    R = pd.DataFrame(rows); R.to_pickle(os.path.join(HERE, "tous_marches_menu.pkl"))
    pd.to_pickle({sym: res for sym, res, err in allr if res is not None}, os.path.join(HERE, "tous_marches_all.pkl"))
    ok = R[(R.nP >= 60) & (R.moyP >= 0.03) & (R.P1 > 0) & (R.P2 > 0)]
    best = ok.sort_values("P", ascending=False).groupby("sym").head(1).set_index("sym")
    for sym, res, err in allr:
        if res is not None and sym in best.index: chosen[sym] = res[best.loc[sym, "strat"]]
    pd.to_pickle(dict(best=best, trades=chosen), os.path.join(HERE, "tous_marches_choix.pkl"))
    pd.set_option("display.width", 200)
    b = best.copy(); b["P_€"] = (b.P * 1000).round(); b["L_€"] = (b.L * 1000).round()
    print(b[["strat", "nP", "P_€", "nL", "L_€"]].to_string())
    print("Sans stratégie valable sur P :", [s for s in ALL if s not in best.index])
    print("Total L (1 000 €/trade) :", round(b.L.sum() * 1000), "€ pour", int(b.nL.sum()), "trades")
