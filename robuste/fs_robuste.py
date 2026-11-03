"""Vérification des pistes « suivi de tendance DAX 15 min » (supertrend, donchian, ema_cross, keltner) : réglages voisins,
coûts x1 et x2, P puis L. Même moteur que fs_strategies.py."""
import os, sys, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fs_strategies as F
from base import cost
L0, P0 = F.L0, F.P0
B = F.bars("DE40", "15min")
def sig(name, p):
    b = B; c = b.close; s = pd.Series(0.0, index=b.index)
    if name == "donchian":
        s[c > b.high.shift().rolling(p).max()] = 1; s[c < b.low.shift().rolling(p).min()] = -1
    elif name == "ema_cross":
        f, sl = p; x = np.sign(c.ewm(span=f, adjust=False).mean() - c.ewm(span=sl, adjust=False).mean()); s[(x != x.shift()) & (x != 0)] = x
    elif name == "keltner":
        e = c.ewm(span=20, adjust=False).mean(); s[c > e + p * b.atr] = 1; s[c < e - p * b.atr] = -1
    elif name == "supertrend":
        hl = ((b.high + b.low) / 2).values; up = hl - p * b.atr.values; dn = hl + p * b.atr.values; cv = c.values
        fu, fd, tr = up.copy(), dn.copy(), np.ones(len(b))
        for i in range(1, len(b)):
            fu[i] = max(up[i], fu[i - 1]) if cv[i - 1] > fu[i - 1] else up[i]
            fd[i] = min(dn[i], fd[i - 1]) if cv[i - 1] < fd[i - 1] else dn[i]
            tr[i] = 1 if cv[i] > fd[i - 1] else (-1 if cv[i] < fu[i - 1] else tr[i - 1])
        x = pd.Series(tr, index=b.index); s[x != x.shift()] = x
    return s.values
def run(s, k, cm=1.0):
    b = B; hm = (b.index.hour * 100 + b.index.minute).values; day = b.index.normalize().values
    o, h, l, c, a = b.open.values, b.high.values, b.low.values, b.close.values, b.atr.values
    st, en = F.SESS["DE40"]; cs = cost("DE40") * cm; out = []; pos = 0
    for i in range(len(b) - 1):
        if pos:
            if (l[i] <= sp) if pos > 0 else (h[i] >= sp): out.append((ed, t0, b.index[i], -1 - cs / rk)); pos = 0
            elif hm[i] >= en or day[i + 1] != day[i] or s[i] == -pos:
                out.append((ed, t0, b.index[i], (pos * (c[i] - e) - cs) / rk)); pos = 0
        if not pos and s[i] != 0 and st <= hm[i] < en and day[i + 1] == day[i] and hm[i + 1] < en:
            pos = int(s[i]); e = o[i + 1]; rk = k * a[i]; t0 = b.index[i + 1]
            if not rk > 0: pos = 0; continue
            sp = e - pos * rk; ed = day[i]
    d = pd.DataFrame(out, columns=["day", "t0", "t1", "R"]); d["day"] = pd.to_datetime(d.day)
    return d[d.day >= P0]
if __name__ == "__main__":
    grids = {"donchian": [10, 20, 30, 40], "ema_cross": [(5, 20), (9, 21), (12, 26), (20, 50)], "keltner": [1.5, 2.0, 2.5], "supertrend": [2.0, 3.0, 4.0]}
    rows = []
    for name, ps in grids.items():
        for p in ps:
            s = sig(name, p)
            for k in [0.75, 1.0, 1.5, 2.0]:
                for cm in [1.0, 2.0]:
                    o = run(s, k, cm); P, L = o[o.day < L0], o[o.day >= L0]
                    rows.append((name, str(p), k, cm, len(P), round(P.R.sum() * 1000), len(L), round(L.R.sum() * 1000), round(100 * (L.R > 0).mean())))
    R = pd.DataFrame(rows, columns=["strat", "param", "stopATR", "coûts", "nP", "P_€", "nL", "L_€", "gagn_L_%"])
    R.to_pickle(os.path.join(HERE, "fs_robuste.pkl"))
    pd.set_option("display.width", 220); pd.set_option("display.max_rows", 300)
    for name in grids:
        r = R[R.strat == name]
        print(name, "| coûts x1 : gagnant P", (r[r.coûts == 1]["P_€"] > 0).mean().round(2), " gagnant L", (r[r.coûts == 1]["L_€"] > 0).mean().round(2),
              "| coûts x2 : gagnant P", (r[r.coûts == 2]["P_€"] > 0).mean().round(2), " gagnant L", (r[r.coûts == 2]["L_€"] > 0).mean().round(2))
    print(R[R.coûts == 2].sort_values("P_€", ascending=False).head(20).to_string())
