"""Le bot passerait-il l'examen FTMO 2 etapes ? (03/11/2026, Melvin + Claude)
Regles (2026) : phase 1 +10 %, phase 2 +5 %, perte max 5 % par jour, 10 % au total (fixe), pas de limite de temps,
4 jours de trading minimum. Base : trades du backtest v1.07 sur la derniere annee (carnet_1an.json, en R).
Methode : on tire des JOURS de trading au hasard (les trades d'un meme jour restent ensemble), avec remise.
'avantage gardé' : 100 % = le backtest est juste, 50 % = la moitie du gain moyen disparait en reel, 0 % = aucun avantage.
Perte du jour : pire point des trades fermes dans la journee (approximation : FTMO compte aussi le flottant)."""
import json, numpy as np, pandas as pd, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "carnet_1an.json"), encoding="utf-8"))
t = pd.DataFrame([x for x in d["trades"] if x[0] == "V107"], columns=["id", "ligne", "side", "op", "cl", "e", "w"])
t["R"] = t.e / 100; t["day"] = t.op.str[:10]; t = t.sort_values(["day", "cl"])
days = np.array([(np.cumsum(g.R.values)[-1], min(0, np.cumsum(g.R.values).min())) for _, g in t.groupby("day")])
rng = np.random.default_rng(7)

def phase(rp, target, keep, nsim=4000, maxdays=750):
    mu = days[:, 0].mean(); end = days[:, 0] - mu * (1 - keep); low = days[:, 1]; ok, dd = [], []
    for _ in range(nsim):
        eq, r = 0.0, False
        for k, i in enumerate(rng.integers(0, len(days), maxdays)):
            if low[i] * rp <= -5 or end[i] * rp <= -5 or eq + min(low[i], end[i]) * rp <= -10: break
            eq += end[i] * rp
            if eq >= target and k >= 3: r = True; break
        ok.append(r); dd.append(k + 1)
    ok = np.array(ok); return ok.mean(), (np.median(np.array(dd)[ok]) if ok.any() else np.nan)

if __name__ == "__main__":
    print("risque/trade | avantage garde | phase 1 | jours (median) | les 2 phases")
    for rp in [0.25, 0.5, 1.0]:
        for keep in [1.0, 0.5, 0.25, 0.0]:
            p1, d1 = phase(rp, 10, keep); p2, _ = phase(rp, 5, keep)
            print(f"{rp:>5} % | {int(keep*100):>3} % | {p1*100:4.0f} % | {d1:4.0f} | {p1*p2*100:4.0f} %")
