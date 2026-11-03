"""Le supertrend 15 min qui marche sur le DAX : est-ce qu'il marche ailleurs ? (03/11/2026)
Réglages FIGÉS du DAX (multiplicateur 4, stop 1,5 ATR) + 8 voisins pour vérifier le plateau. P = 2023 -> 02/11/2025, L = dernière année."""
import os, sys, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "sans_yen"))
import recherche
from base import load as load_a, cost
L0, P0 = pd.Timestamp("2025-11-03"), pd.Timestamp("2023-01-01")
M15B = os.path.join(HERE, "..", "data_m15b")
def load_b(sym):
    d = pd.read_csv(os.path.join(M15B, f"{sym}_M15.csv"))
    dec = max(len(str(x).split(".")[1]) if "." in str(x) else 0 for x in d.close.head(200))
    d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M"); d = d.set_index("time"); d = d[d.index.dayofweek < 5]
    sp = float(np.median(d.spread_points.tail(20000))) * 10 ** (-dec)
    if sym in ST: sp = max(sp, 0.0004 * float(d.close.median()))
    recherche.SPREAD[sym] = sp
    return d
EU = ["DE40", "FRA40", "EUSTX50", "NETH25", "ESP35", "SWI20"]; US = ["US500", "USTECH100M", "US30"]
ST = ["NVDA", "TSLA", "AAPL", "AMD", "META", "MSFT", "AMZN", "GOOGL", "NFLX"]; MET = ["XAUUSD", "XAGUSD"]
def sess(sym): return (1000, 1815) if sym in EU else ((1000, 2245) if sym in MET else (1630, 2245))
def prep(sym):
    d = load_a(sym) if sym in EU[:1] + US + MET else load_b(sym)
    b = d[["open", "high", "low", "close"]].copy(); pc = b.close.shift()
    tr = pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1)
    b["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean(); return b
def st_sig(b, m):
    hl = ((b.high + b.low) / 2).values; up = hl - m * b.atr.values; dn = hl + m * b.atr.values; cv = b.close.values
    fu, fd, tr = up.copy(), dn.copy(), np.ones(len(b))
    for i in range(1, len(b)):
        fu[i] = max(up[i], fu[i - 1]) if cv[i - 1] > fu[i - 1] else up[i]
        fd[i] = min(dn[i], fd[i - 1]) if cv[i - 1] < fd[i - 1] else dn[i]
        tr[i] = 1 if cv[i] > fd[i - 1] else (-1 if cv[i] < fu[i - 1] else tr[i - 1])
    s = np.zeros(len(b)); s[1:] = np.where(tr[1:] != tr[:-1], tr[1:], 0); return s
def run(b, s, k, st, en, cs):
    hm = (b.index.hour * 100 + b.index.minute).values; day = b.index.normalize().values
    o, h, l, c, a = b.open.values, b.high.values, b.low.values, b.close.values, b.atr.values; out = []; pos = 0
    for i in range(len(b) - 1):
        if pos:
            if (l[i] <= sp) if pos > 0 else (h[i] >= sp): out.append((ed, pos, b.index[i0], b.index[i], -1 - cs / rk)); pos = 0
            elif hm[i] >= en or day[i + 1] != day[i] or s[i] == -pos:
                out.append((ed, pos, b.index[i0], b.index[i], (pos * (c[i] - e) - cs) / rk)); pos = 0
        if not pos and s[i] != 0 and st <= hm[i] < en and day[i + 1] == day[i] and hm[i + 1] < en:
            pos = int(s[i]); e = o[i + 1]; rk = k * a[i]; i0 = i + 1
            if not rk > 0: pos = 0; continue
            sp = e - pos * rk; ed = day[i]
    d = pd.DataFrame(out, columns=["day", "side", "t0", "t1", "R"]); d["day"] = pd.to_datetime(d.day); return d[d.day >= P0]
if __name__ == "__main__":
    rows = []; keep = {}
    for sym in EU + US + MET + ST:
        try: b = prep(sym)
        except Exception as ex: print(sym, "erreur", ex); continue
        st, en = sess(sym); cs = cost(sym)
        for m, k in itertools.product([3.0, 3.5, 4.0], [1.25, 1.5, 1.75]):
            o = run(b, st_sig(b, m), k, st, en, cs); P, L = o[o.day < L0], o[o.day >= L0]
            rows.append((sym, m, k, len(P), round(P.R.sum() * 1000), len(L), round(L.R.sum() * 1000)))
            if (m, k) == (4.0, 1.5): keep[sym] = o
    R = pd.DataFrame(rows, columns=["sym", "mult", "stop", "nP", "P_€", "nL", "L_€"]); R.to_pickle(os.path.join(HERE, "st_marches.pkl"))
    pd.to_pickle(keep, os.path.join(HERE, "st_marches_trades.pkl"))
    g = R.groupby("sym").agg(P_pos=("P_€", lambda x: (x > 0).sum()), L_pos=("L_€", lambda x: (x > 0).sum()))
    f = R[(R.mult == 4.0) & (R.stop == 1.5)].set_index("sym")[["nP", "P_€", "nL", "L_€"]]
    print(f.join(g).to_string())
