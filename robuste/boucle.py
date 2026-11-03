"""BOUCLE demandee par aurele : tester le bot de la demo (DayTrader v1.01), regarder ou il perd,
comprendre pourquoi, corriger, retester. On repete tant qu'une cause nette de pertes existe.
Bot de la demo = DAX 1re bougie + zone de bruit DAX + Initial Balance or, avec filtre de tendance 20 j,
100 EUR par achat, 50 EUR par vente. Periode : toutes les donnees 2022 -> 02/11/2026."""
import numpy as np, pandas as pd
from base import A_END
X = pd.read_pickle("meta_preds.pkl")
X["vol_b"] = pd.cut(X.vol, [0, 0.9, 1.15, 99], labels=["calme", "normal", "agite"]).astype(str)
NOMS = {"ORB15dir_DAX:DE40": "DAX 1re bougie", "BRUIT_DAX:DE40": "DAX zone de bruit", "IB_OR:XAUUSD": "Or Initial Balance"}
bot = X[X.ligne.isin(NOMS) & (X.tend > 0)].copy()
bot["mise"] = np.where(bot.side > 0, 100, 50)
bot["eur"] = bot.R * bot.mise
bot["an"] = bot.day.dt.year

def conds(T):
    c = {}
    for b in ("calme", "normal", "agite"): c[f"marche {b}"] = T.vol_b == b
    c["achats"] = T.side > 0; c["ventes"] = T.side < 0
    for j, nm in enumerate(["lundi", "mardi", "mercredi", "jeudi", "vendredi"]): c[nm] = T.jour == j
    for col, nm in (("deja", "prix deja parti dans le sens du trade"), ("risk_atr", "stop"), ("ecart_ma", "ecart a la moyenne 20 j"), ("mom5", "elan sur 5 jours")):
        lo, hi = T[col].quantile([1 / 3, 2 / 3])
        c[f"{nm} faible"] = T[col] <= lo; c[f"{nm} fort"] = T[col] >= hi
    return c

def bilan(T, lab):
    eq = T.sort_values("open_time").eur.cumsum()
    by = T.groupby("an").eur.sum().round().astype(int).to_dict()
    nd = pd.bdate_range("2022-03-09", "2026-11-02").size
    return dict(etape=lab, trades=len(T), trades_par_jour=round(len(T) / nd, 2), total=round(T.eur.sum()),
                **{str(k): v for k, v in by.items()}, pire_baisse=round(float((eq - eq.cummax()).min())),
                gagnants_pct=round((T.R > 0).mean() * 100))

def loop(T, max_iter=8, min_n=40, min_loss=300, log=None):
    fixes = []
    for it in range(max_iter):
        best = None
        for ln, G in T.groupby("ligne"):
            for nm, m in conds(G).items():
                if (ln, nm) in [(f[0], f[1]) for f in fixes]: continue
                n = int(m.sum()); s = G.eur[m].sum()
                if n < min_n or len(G) - n < 60: continue
                if s < -min_loss and (best is None or s < best[3]):
                    best = (ln, nm, n, s, G.R[m].mean())
        if best is None: break
        ln, nm, n, s, mr = best
        G = T[T.ligne == ln]; m = conds(G)[nm]
        drop = G.index[m]
        fixes.append((ln, nm, n, round(s), round(mr, 2)))
        T = T.drop(drop)
        if log is not None: log.append(bilan(T, f"correctif {it+1} : {NOMS[ln]} sans '{nm}'"))
    return T, fixes

rows = [bilan(bot, "bot de la demo (v1.01)")]
fixed, fixes = loop(bot, log=rows)
R = pd.DataFrame(rows)
pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 90)
print(R.to_string(index=False))
print("\nCauses trouvees (ligne, situation, trades retires, euros perdus dans cette situation, R moyen) :")
for f in fixes: print("  ", NOMS[f[0]], "|", f[1], "|", f[2], "|", f[3], "|", f[4])
R.to_csv("boucle.csv", index=False); fixed.to_pickle("boucle_trades.pkl")

# Controle d'honnetete : meme boucle, mais en ne regardant que 2022-2024, puis on applique a 2025-2026
botA = bot[bot.day < A_END]; botB = bot[bot.day >= A_END]
fA, fixA = loop(botA)
keepB = botB.copy()
for ln, nm, *_ in fixA:
    G = keepB[keepB.ligne == ln]
    # seuils recalcules sur 2022-2024 pour les quantiles
    base = botA[botA.ligne == ln]
    m = conds(pd.concat([base, G]))[nm].loc[G.index] if True else None
    keepB = keepB.drop(G.index[m])
print("\nControle (boucle faite sur 2022-2024 seulement, puis appliquee a 2025-2026) :")
print("  correctifs choisis :", [(NOMS[a], b) for a, b, *_ in fixA])
print("  2025-26 bot demo :", round(botB.eur.sum()), "| 2025-26 apres correctifs :", round(keepB.eur.sum()),
      "| trades", len(botB), "->", len(keepB))
rng = np.random.default_rng(11); frac = len(keepB) / len(botB)
sims = [botB.eur.values[rng.random(len(botB)) < frac].sum() for _ in range(2000)]
print("  hasard (retirer autant de trades au hasard) : mediane", round(np.median(sims)), "| proba que le hasard fasse mieux :", round(float(np.mean(np.array(sims) >= keepB.eur.sum())), 3))
