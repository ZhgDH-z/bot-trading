"""
Recherche d'une strategie SANS YEN qui trade tous les jours.
Donnees : exports MT5 d'aurele (MetaQuotes-Demo), H1, 2012 -> oct. 2026.
Protocole honnete en 3 periodes :
  CONCEPTION  2012-2017 : on regarde
  VALIDATION  2018-2021 : on garde un couple strategie+marche seulement s'il gagne sur les 2
  TEST FINAL  2022-03 -> 2026-10 : jamais regarde pour choisir
Toutes les regles et parametres sont fixes AVANT (valeurs classiques, aucune optimisation).
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, "..", "data_export")
P1, P2, P3 = pd.Timestamp("2018-01-01"), pd.Timestamp("2022-01-01"), pd.Timestamp("2022-03-01")

# spread prudent (en prix), x1.2 pour le glissement
SPREAD = {"EURUSD": 0.00010, "GBPUSD": 0.00015, "AUDUSD": 0.00012, "USDCAD": 0.00018, "USDCHF": 0.00015,
          "EURGBP": 0.00015, "EURCHF": 0.00020, "XAUUSD": 0.30, "XAGUSD": 0.03,
          "US500": 0.6, "US30": 3.0, "USTECH100M": 2.0, "DE40": 1.5}
INDICES = {"US500", "US30", "USTECH100M", "DE40"}
FIN = 0.07  # financement annuel d'un CFD tenu la nuit (prudent, toutes positions)


def load(sym):
    d = pd.read_csv(os.path.join(EXP, f"{sym}_H1.csv"))
    d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M")
    d = d.set_index("time")[["open", "high", "low", "close"]]
    return d[d.index.dayofweek < 5]


def daily(df):
    return df.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def atr(df, n):
    pc = df["close"].shift()
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def mk(sym, side, t0, t1, e, x, risk):
    nights = max(0, (t1.normalize() - t0.normalize()).days)
    cost = SPREAD[sym] * 1.2 + e * FIN * nights / 365 * (1 if sym in INDICES else 0.3)
    return dict(symbol=sym, side=side, open_time=t0, close_time=t1, entry=e, exit=x, risk=risk,
                R=(side * (x - e) - cost) / risk)


# ---------------------------------------------------------------- A : RSI(2) journalier (Connors), achat ET vente
def rsi2(sym, df, long_only=False, lo=10, hi=90):
    d = daily(df)
    c = d.close
    r2, ma200, ma5, a = rsi(c, 2).values, c.rolling(200).mean().values, c.rolling(5).mean().values, atr(d, 20).values
    o, h, l, cl, idx = d.open.values, d.high.values, d.low.values, c.values, d.index
    out, pos = [], None
    for i in range(201, len(d)):
        if pos is None:
            sd = 0
            if cl[i-1] > ma200[i-1] and r2[i-1] < lo: sd = 1
            elif not long_only and cl[i-1] < ma200[i-1] and r2[i-1] > hi: sd = -1
            if not sd: continue
            r = 3 * a[i-1]
            pos = dict(sd=sd, e=o[i], sl=o[i] - sd * r, r=r, t=idx[i], i=i)
        sd = pos["sd"]; px = None
        if (sd == 1 and l[i] <= pos["sl"]) or (sd == -1 and h[i] >= pos["sl"]):
            px = min(o[i], pos["sl"]) if sd == 1 else max(o[i], pos["sl"])
        elif (sd == 1 and cl[i] > ma5[i]) or (sd == -1 and cl[i] < ma5[i]) or i - pos["i"] >= 10:
            px = cl[i]
        if px is not None:
            out.append(mk(sym, sd, pos["t"], idx[i] + pd.Timedelta(hours=23), pos["e"], px, pos["r"])); pos = None
    return out


# ---------------------------------------------------------------- B : retour a la moyenne H1 en session asiatique
def asie(sym, df, z_in=2.0):
    c = df.close
    m, s = c.rolling(20).mean().values, c.rolling(20).std().values
    a = atr(df, 14).values
    o, h, l, cl, idx = df.open.values, df.high.values, df.low.values, c.values, df.index
    hr = idx.hour.values
    out, pos = [], None
    for i in range(21, len(df)):
        if pos is not None:
            sd = pos["sd"]; px = None
            if (sd == 1 and l[i] <= pos["sl"]) or (sd == -1 and h[i] >= pos["sl"]):
                px = min(o[i], pos["sl"]) if sd == 1 else max(o[i], pos["sl"])
            elif (sd == 1 and cl[i] >= m[i]) or (sd == -1 and cl[i] <= m[i]) or hr[i] >= 9:
                px = cl[i]
            if px is not None:
                out.append(mk(sym, sd, pos["t"], idx[i], pos["e"], px, pos["r"])); pos = None
            continue
        if not (1 <= hr[i] <= 7) or s[i-1] == 0: continue
        z = (cl[i-1] - m[i-1]) / s[i-1]
        sd = -1 if z > z_in else (1 if z < -z_in else 0)
        if not sd: continue
        r = 2 * a[i-1]
        pos = dict(sd=sd, e=o[i], sl=o[i] - sd * r, r=r, t=idx[i])
    return out


# ---------------------------------------------------------------- C : repli intraday sur indices (session US)
def repli_us(sym, df, k=1.0):
    """Si l'indice est tombe de plus de k x ATR(H1,14)*... sous l'ouverture du jour pendant la seance US,
    on achete, sortie a la cloture du jour (22h serveur) ou stop 2 ATR H1."""
    a = atr(df, 14).values
    da = atr(daily(df), 14).shift()
    o, h, l, cl, idx = df.open.values, df.high.values, df.low.values, df.close.values, df.index
    out = []
    for day, g in df.groupby(df.index.date):
        dA = da.get(pd.Timestamp(day), np.nan)
        if np.isnan(dA): continue
        op = g.open.iloc[0]; pos = None
        for t, (oo, hh, ll, cc) in zip(g.index, g[["open", "high", "low", "close"]].values):
            if pos is None:
                if 17 <= t.hour <= 20 and cc < op - 0.5 * dA:
                    pos = "next"; continue
                continue
            if pos == "next":
                r = 0.6 * dA
                pos = dict(e=oo, sl=oo - r, r=r, t=t)
            if ll <= pos["sl"]:
                out.append(mk(sym, 1, pos["t"], t, pos["e"], min(oo, pos["sl"]), pos["r"])); pos = None; break
            if t.hour >= 22:
                out.append(mk(sym, 1, pos["t"], t, pos["e"], cc, pos["r"])); pos = None; break
        if isinstance(pos, dict):
            out.append(mk(sym, 1, pos["t"], g.index[-1], pos["e"], g.close.iloc[-1], pos["r"]))
    return out


# ---------------------------------------------------------------- D : nuit sur indices (cloture US -> avant ouverture)
def nuit(sym, df):
    da = atr(daily(df), 14).shift()
    out = []
    days = df.groupby(df.index.date)
    keys = list(days.groups.keys())
    for k0, k1 in zip(keys[:-1], keys[1:]):
        g0, g1 = days.get_group(k0), days.get_group(k1)
        a = da.get(pd.Timestamp(k0), np.nan)
        e = g0[g0.index.hour == 22]
        x = g1[g1.index.hour == 15]
        if np.isnan(a) or e.empty or x.empty: continue
        out.append(mk(sym, 1, e.index[0], x.index[0], e.open.iloc[0], x.open.iloc[0], 0.5 * a))
    return out


# ---------------------------------------------------------------- E : tendance Donchian 20 jours (reference)
def donchian(sym, df):
    d = daily(df); a = atr(d, 20).values
    hi, lo = d.high.rolling(20).max().shift().values, d.low.rolling(20).min().shift().values
    ho, lw = d.high.rolling(10).max().shift().values, d.low.rolling(10).min().shift().values
    o, h, l, idx = d.open.values, d.high.values, d.low.values, d.index
    out, pos = [], None
    for i in range(21, len(d)):
        if pos is not None:
            sd = pos["sd"]
            st = max(pos["sl"], lw[i]) if sd == 1 else min(pos["sl"], ho[i])
            if (sd == 1 and l[i] <= st) or (sd == -1 and h[i] >= st):
                px = min(o[i], st) if sd == 1 else max(o[i], st)
                out.append(mk(sym, sd, pos["t"], idx[i], pos["e"], px, pos["r"])); pos = None
            continue
        if h[i] > hi[i]:
            e = max(o[i], hi[i]); pos = dict(sd=1, e=e, sl=e - 2*a[i-1], r=2*a[i-1], t=idx[i])
        elif l[i] < lo[i]:
            e = min(o[i], lo[i]); pos = dict(sd=-1, e=e, sl=e + 2*a[i-1], r=2*a[i-1], t=idx[i])
    return out


STRATS = {
    "RSI2": lambda s, d: rsi2(s, d, long_only=s in INDICES),
    "ASIE": asie,
    "REPLI_US": repli_us,
    "NUIT": nuit,
    "DONCHIAN": donchian,
}
FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "EURGBP", "EURCHF", "XAUUSD", "XAGUSD"]
MARKETS = {"RSI2": FX + list(INDICES), "ASIE": FX, "REPLI_US": list(INDICES), "NUIT": list(INDICES),
           "DONCHIAN": FX + list(INDICES)}


def period(t):
    return np.where(t < P1, "A_2012-17", np.where(t < P2, "B_2018-21", np.where(t >= P3, "C_2022-26", "gap")))


if __name__ == "__main__":
    data = {}
    allt = []
    for st, mkts in MARKETS.items():
        for s in mkts:
            if s not in data: data[s] = load(s)
            t = pd.DataFrame(STRATS[st](s, data[s]))
            if t.empty: continue
            t["strat"] = st
            allt.append(t)
    T = pd.concat(allt)
    T["periode"] = period(T.open_time)
    T.to_pickle(os.path.join(HERE, "tous_trades.pkl"))
    g = T[T.periode != "gap"].groupby(["strat", "symbol", "periode"]).R.agg(["count", "mean"]).unstack()
    pd.set_option("display.width", 250)
    print(g.round(3).to_string())
