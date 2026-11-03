"""Les 9 stratégies du backtest TradingView (skill tradingview-mcp) en day trading sur l'or et le DAX (03/11/2026).
Signal à la clôture d'une bougie, entrée à l'ouverture de la suivante, sortie au signal inverse ou en fin de séance,
stop de secours k x ATR(14) de l'unité de temps. Coûts SPREAD x 1,2. P = 2023 -> 02/11/2025, L = dernière année."""
import os, sys, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from base import load, cost
L0, P0 = pd.Timestamp("2025-11-03"), pd.Timestamp("2023-01-01")
SESS = {"DE40": (1000, 1815), "XAUUSD": (1000, 2245)}

def bars(sym, rule):
    d = load(sym)
    if rule == "15min": b = d[["open", "high", "low", "close"]].copy()
    else:
        b = d[["open", "high", "low", "close"]].resample(rule, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b = b[b.index.dayofweek < 5]
    pc = b.close.shift()
    tr = pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1)
    b["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return b

def rsi(c, n=14):
    d = c.diff(); g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); l = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + g / l)

def signals(b, name):
    c = b.close; s = pd.Series(0, index=b.index, dtype=float)
    if name == "rsi":
        r = rsi(c); s[(r.shift() < 30) & (r >= 30)] = 1; s[(r.shift() > 70) & (r <= 70)] = -1
    elif name == "bollinger":
        m = c.rolling(20).mean(); sd = c.rolling(20).std(); s[c < m - 2 * sd] = 1; s[c > m + 2 * sd] = -1
    elif name == "macd":
        mc = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean(); sg = mc.ewm(span=9, adjust=False).mean()
        x = np.sign(mc - sg); s[(x != x.shift()) & (x != 0)] = x
    elif name == "ema_cross":
        x = np.sign(c.ewm(span=9, adjust=False).mean() - c.ewm(span=21, adjust=False).mean()); s[(x != x.shift()) & (x != 0)] = x
    elif name == "supertrend":
        hl = (b.high + b.low) / 2; up = hl - 3 * b.atr; dn = hl + 3 * b.atr
        fu, fd, tr = up.copy(), dn.copy(), pd.Series(1, index=b.index)
        cv, fuv, fdv, trv = c.values.copy(), fu.values.copy(), fd.values.copy(), tr.values.copy(); upv, dnv = up.values.copy(), dn.values.copy()
        for i in range(1, len(b)):
            fuv[i] = max(upv[i], fuv[i - 1]) if cv[i - 1] > fuv[i - 1] else upv[i]
            fdv[i] = min(dnv[i], fdv[i - 1]) if cv[i - 1] < fdv[i - 1] else dnv[i]
            trv[i] = 1 if cv[i] > fdv[i - 1] else (-1 if cv[i] < fuv[i - 1] else trv[i - 1])
        x = pd.Series(trv, index=b.index); s[x != x.shift()] = x
    elif name == "donchian":
        s[c > b.high.shift().rolling(20).max()] = 1; s[c < b.low.shift().rolling(20).min()] = -1
    elif name == "rsi_pullback":
        e = c.ewm(span=200, adjust=False).mean(); r = rsi(c); s[(c > e) & (r < 40)] = 1; s[(c < e) & (r > 60)] = -1
    elif name == "keltner_breakout":
        e = c.ewm(span=20, adjust=False).mean(); s[c > e + 2 * b.atr] = 1; s[c < e - 2 * b.atr] = -1
    elif name == "triple_ema":
        a, m, l = (c.ewm(span=k, adjust=False).mean() for k in (8, 21, 55))
        x = pd.Series(np.where((a > m) & (m > l), 1, np.where((a < m) & (m < l), -1, 0)), index=b.index)
        s[(x != x.shift()) & (x != 0)] = x
    return s

def run(sym, rule, name, k):
    b = bars(sym, rule); s = signals(b, name).values
    hm = (b.index.hour * 100 + b.index.minute).values; day = b.index.normalize().values
    o, h, l, c, a = b.open.values, b.high.values, b.low.values, b.close.values, b.atr.values
    st, en = SESS[sym]; cs = cost(sym); out = []; pos = 0
    for i in range(len(b) - 1):
        if pos:
            stop_hit = (l[i] <= sp) if pos > 0 else (h[i] >= sp)
            if stop_hit: out.append((ed, -1 - cs / rk)); pos = 0
            elif hm[i] >= en or day[i + 1] != day[i] or (s[i] == -pos):
                x = c[i]; out.append((ed, (pos * (x - e) - cs) / rk)); pos = 0
        if not pos and s[i] != 0 and st <= hm[i] < en and day[i + 1] == day[i] and hm[i + 1] < en:
            pos = int(s[i]); e = o[i + 1]; rk = k * a[i]
            if rk <= 0 or np.isnan(rk): pos = 0; continue
            sp = e - pos * rk; ed = day[i]
    o_ = pd.DataFrame(out, columns=["day", "R"]); o_["day"] = pd.to_datetime(o_.day)
    return o_[o_.day >= P0]

res = []
for sym, rule, name, k in itertools.product(["DE40", "XAUUSD"], ["15min", "1h"], ["rsi", "bollinger", "macd", "ema_cross", "supertrend", "donchian", "rsi_pullback", "keltner_breakout", "triple_ema"], [1.0, 2.0]):
    o = run(sym, rule, name, k)
    P, L = o[o.day < L0], o[o.day >= L0]
    res.append((sym, rule, name, k, len(P), round(P.R.sum() * 1000), len(L), round(L.R.sum() * 1000), round(len(L) / 256, 1)))
R = pd.DataFrame(res, columns=["marché", "UT", "stratégie", "stopATR", "nP", "P_€", "nL", "L_€", "trades/j L"])
pd.set_option("display.width", 200)
print(R.sort_values("P_€", ascending=False).head(15).to_string())
print("réglages gagnants sur P :", (R["P_€"] > 0).sum(), "/", len(R), " dont gagnants aussi sur L :", ((R["P_€"] > 0) & (R["L_€"] > 0)).sum())
R.to_pickle(os.path.join(HERE, "fs_strategies.pkl"))
