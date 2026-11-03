"""BOUCLE DIAGNOSTIC -> CORRECTIF -> NOUVEAU TEST (demande d'aurele, 02/11/2026).
Pour chaque ligne (strategie x marche) :
 1. on regarde UNIQUEMENT 2022-2024 : si elle gagne, on la garde telle quelle ;
 2. si elle perd, on cherche OU sont les pertes (tendance, volatilite, heure, jour, sens, chemin deja fait,
    taille du stop) et on retire au plus 2 situations perdantes (correctif) ;
 3. on re-teste le correctif sur 2025-2026, que le diagnostic n'a jamais vu.
Controle : on compare a des 'correctifs au hasard' qui retirent autant de trades."""
import numpy as np, pandas as pd
from base import A_END

X = pd.read_pickle("meta_preds.pkl")
X["vol_b"] = pd.cut(X.vol, [0, 0.9, 1.15, 99], labels=["calme", "normal", "agite"]).astype(str)

def conditions(A):
    """Situations candidates (seuils calcules sur 2022-2024 seulement)."""
    c = {}
    c["contre la tendance 20 j"] = lambda d: d.tend < 0
    c["avec la tendance 20 j"] = lambda d: d.tend > 0
    for b in ("calme", "normal", "agite"):
        c[f"marche {b}"] = (lambda b: lambda d: d.vol_b == b)(b)
    c["achats"] = lambda d: d.side > 0
    c["ventes"] = lambda d: d.side < 0
    for j, nm in enumerate(["lundi", "mardi", "mercredi", "jeudi", "vendredi"]):
        c[nm] = (lambda j: lambda d: d.jour == j)(j)
    for col, nm in (("deja", "prix deja parti"), ("risk_atr", "stop"), ("ecart_ma", "ecart a la moyenne"), ("mom5", "elan 5 jours")):
        lo, hi = A[col].quantile([1 / 3, 2 / 3])
        c[f"{nm} faible"] = (lambda col, lo: lambda d: d[col] <= lo)(col, lo)
        c[f"{nm} fort"] = (lambda col, hi: lambda d: d[col] >= hi)(col, hi)
    hs = sorted(A.heure.unique())
    if len(hs) > 2:
        for h in hs:
            if (A.heure == h).sum() >= 30:
                c[f"entree a {h}h serveur"] = (lambda h: lambda d: d.heure == h)(h)
    return c

def diagnose(A, max_fix=2, min_keep=0.4, min_n=60):
    conds = conditions(A); removed = []
    keep = pd.Series(True, index=A.index)
    for _ in range(max_fix):
        best, gain = None, 0
        for nm, f in conds.items():
            if nm in removed: continue
            m = f(A) & keep
            if m.sum() < 20: continue
            newkeep = keep & ~m
            if newkeep.sum() < max(min_n, min_keep * len(A)): continue
            g = -A.R[m].sum()                     # gain obtenu en retirant cette situation
            if g > gain: best, gain = nm, g
        if best is None or gain < 3: break        # il faut au moins +300 EUR d'amelioration
        removed.append(best); keep &= ~conds[best](A)
    return removed, conds

rows, trades_fixed, trades_raw = [], [], []
rng = np.random.default_rng(7)
for ln, T in X.groupby("ligne"):
    A, B = T[T.day < A_END], T[T.day >= A_END]
    if len(A) < 80 or len(B) < 30: continue
    rawA, rawB = A.R.sum() * 100, B.R.sum() * 100
    if rawA > 0:
        verdict, fix, fa, fb, keepB, rnd = "gagnante : gardee telle quelle", [], rawA, rawB, B, np.nan
    else:
        fix, conds = diagnose(A)
        if not fix:
            verdict, fa, fb, keepB, rnd = "perdante : aucune cause nette", rawA, rawB, None, np.nan
        else:
            mA = pd.Series(True, index=A.index); mB = pd.Series(True, index=B.index)
            for nm in fix:
                mA &= ~conds[nm](A); mB &= ~conds[nm](B)
            fa, fb = A.R[mA].sum() * 100, B.R[mB].sum() * 100
            keepB = B[mB] if fa > 0 else None
            # hasard : retirer au hasard la meme proportion de trades de 2025-2026
            frac = mB.mean()
            rnd = np.median([B.R.values[rng.random(len(B)) < frac].sum() * 100 for _ in range(500)])
            verdict = "corrigee sur 2022-24" if fa > 0 else "amelioree mais toujours perdante"
    if keepB is not None:
        trades_fixed.append(keepB.assign(ligne=ln))
    trades_raw.append(B.assign(ligne=ln))
    rows.append(dict(ligne=ln, verdict=verdict, correctif=" + ".join(f"sans '{f}'" for f in fix),
                     avant_2022_24=round(rawA), apres_2022_24=round(fa), avant_2025_26=round(rawB), apres_2025_26=round(fb),
                     hasard_2025_26=round(rnd) if not np.isnan(rnd) else None, trades_B=len(B)))
R = pd.DataFrame(rows).sort_values("apres_2025_26", ascending=False)
pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 80); pd.set_option("display.max_rows", 200)
print(R.to_string(index=False))
R.to_csv("diagnostic.csv", index=False)
fixed = R[R.verdict == "corrigee sur 2022-24"]
print("\nLignes corrigees sur 2022-24 :", len(fixed),
      "| tiennent sur 2025-26 :", int((fixed.apres_2025_26 > 0).sum()),
      "| ameliorees vs avant sur 2025-26 :", int((fixed.apres_2025_26 > fixed.avant_2025_26).sum()),
      "| mieux que le hasard :", int((fixed.apres_2025_26 > fixed.hasard_2025_26).sum()))
print("Somme 2025-26 des lignes corrigees : avant", fixed.avant_2025_26.sum(), "apres", fixed.apres_2025_26.sum(), "hasard", fixed.hasard_2025_26.sum())
g = R[R.verdict.str.startswith("gagnante")]
print("Lignes gagnantes 2022-24 gardees :", len(g), "| encore gagnantes 2025-26 :", int((g.avant_2025_26 > 0).sum()), "| somme 2025-26 :", g.avant_2025_26.sum())
pd.concat(trades_fixed).to_pickle("diag_trades_B.pkl")
