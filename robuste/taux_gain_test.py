"""Test « 70 a 80 % de trades gagnants » (03/11/2026, demande de Melvin).
Idee : petit objectif, stop plus large -> on gagne souvent, un peu ; on perd rarement, beaucoup.
Regles fixees AVANT de regarder les resultats :
 - 13 marches (base.MKTS), bougies 15 min, 1 trade par jour et par marche, entree a l'ouverture de la seance
   (DAX 10h00, US 16h30, or/argent/forex 10h00 serveur), sortie a l'objectif, au stop, ou en fin de seance.
 - sens : celui de la tendance 20 jours (cloture d'hier > moyenne 20 jours -> achat), comme le bot.
 - objectif T et stop S en multiples de l'ATR 14 jours d'hier : (0,10 ; 0,30) (0,15 ; 0,45) (0,20 ; 0,60) (0,10 ; 0,50) (0,20 ; 1,00).
 - si objectif et stop sont touches dans la meme bougie : on compte le stop (prudent).
 - 100 EUR perdus au stop. Couts prudents (spread x 1,2). P = 2022 -> 02/11/2025, L = 03/11/2025 -> 02/11/2026.
 - comparaison au hasard : memes trades, sens tire au hasard (2 000 tirages)."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from base import load, cost, daily_atr, MKTS  # noqa

L0 = pd.Timestamp("2025-11-03")
SESS = {"DE40": (1000, 1815), "US500": (1630, 2245), "USTECH100M": (1630, 2245), "US30": (1630, 2245)}
GRID = [(0.10, 0.30), (0.15, 0.45), (0.20, 0.60), (0.10, 0.50), (0.20, 1.00)]


def run(sym, T, S):
    d = load(sym); s0, s1 = SESS.get(sym, (1000, 2245)); c = cost(sym)
    at = daily_atr(sym)
    dc = d.groupby("day").close.last(); trend = np.sign(dc.shift(1) - dc.rolling(20).mean().shift(1))
    out = []
    for day, g in d.groupby("day"):
        a, tr = at.get(day, np.nan), trend.get(day, 0)
        if not (a > 0) or not (tr in (1, -1)): continue
        g = g[(g.hm >= s0) & (g.hm <= s1)]
        if len(g) < 4 or g.hm.iloc[0] != s0: continue
        e = g.open.iloc[0]; risk = S * a
        res = {}
        for sd in (1, -1):                       # on calcule les 2 sens (pour le test au hasard)
            tp, sl = e + sd * T * a, e - sd * S * a; x = None
            for h, l in zip(g.high.values, g.low.values):
                hit_sl = (l <= sl) if sd > 0 else (h >= sl); hit_tp = (h >= tp) if sd > 0 else (l <= tp)
                if hit_sl: x = sl; break
                if hit_tp: x = tp; break
            if x is None: x = g.close.iloc[-1]
            res[sd] = sd * (x - e) / risk
        out.append(dict(day=day, R_gross=res[int(tr)], R_other=res[-int(tr)], cost_R=c / risk))
    t = pd.DataFrame(out); t["R"] = t.R_gross - t.cost_R
    return t


def stats(t, rng):
    if len(t) == 0: return {}
    P, L = t[t.day < L0], t[t.day >= L0]
    sims = []
    for _ in range(2000):
        pick = rng.random(len(t)) < 0.5
        sims.append((np.where(pick, t.R_gross, t.R_other) - t.cost_R).sum())
    return dict(trades=len(t), gagnants=round((t.R > 0).mean() * 100), eurP=round(P.R.sum() * 100), eurL=round(L.R.sum() * 100),
                gagnantsL=round((L.R > 0).mean() * 100) if len(L) else 0, pire=round(t.R.min() * 100),
                p_hasard=round(float((np.array(sims) >= t.R.sum()).mean()), 3))


if __name__ == "__main__":
    rng = np.random.default_rng(1); rows = []
    for sym in MKTS:
        for T, S in GRID:
            st = stats(run(sym, T, S), rng); st.update(marche=sym, objectif=T, stop=S); rows.append(st)
    R = pd.DataFrame(rows)[["marche", "objectif", "stop", "trades", "gagnants", "gagnantsL", "eurP", "eurL", "pire", "p_hasard"]]
    pd.set_option("display.width", 200); print(R.to_string(index=False))
    R.to_csv(os.path.join(HERE, "taux_gain_test.csv"), index=False)
    ok = R[(R.eurP > 0) & (R.eurL > 0) & (R.gagnants >= 70)]
    print(f"\n{len(R)} combinaisons ; gagnantes sur P ET L avec >= 70 % de gagnants : {len(ok)}")
    print(ok.to_string(index=False))
    print("\nMoyenne des taux de gagnants :", round(R.gagnants.mean()), "% ; total de toutes les combinaisons P :", R.eurP.sum(), "€, L :", R.eurL.sum(), "€")
