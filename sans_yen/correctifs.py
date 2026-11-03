import pandas as pd, numpy as np
T = pd.read_pickle("trio_features.pkl").sort_values("open_time").reset_index(drop=True)
T["per"] = np.where(T.open_time < "2025-01-01", "1) 2022-2024 (avant)", np.where(T.open_time < "2026-01-01", "2) 2025", "3) 2026 (jan-oct)"))

def adapt(df, n=20, low=0.5):
    """Bot evolutif : chaque strategie regarde ses n derniers trades (deja termines). Si leur somme est negative,
    elle passe a low x la mise (50 EUR au lieu de 100). Rien ne regarde le futur."""
    w = pd.Series(1.0, index=df.index)
    for st, g in df.groupby("strat"):
        past = g.R.shift(1).rolling(n, min_periods=n).sum()
        w.loc[g.index] = np.where(past < 0, low, 1.0)
    return w

def show(label, df, w=None):
    w = pd.Series(1.0, index=df.index) if w is None else w
    df = df.assign(eur=df.R * 100 * w)
    out = []
    for p, g in df.groupby("per"):
        wk = g.groupby(g.open_time.dt.to_period("W")).eur.sum()
        cum = g.eur.cumsum(); dd = (cum - cum.cummax()).min()
        out.append(f"{p}: {len(g)} trades, {round(g.eur.sum()):+} EUR, sem.+ {round((wk>0).mean()*100)} %, pire baisse {round(dd)} EUR")
    print(f"--- {label}\n   " + "\n   ".join(out))

show("Trio de base (achat + vente, 100 EUR)", T)
F = T[T.side == T.tend]
show("Correctif 1 : seulement dans le sens de la tendance 20 jours", F)
show("Correctif 2 : bot evolutif (mise reduite apres 20 mauvais trades)", T, adapt(T))
show("Correctifs 1 + 2", F, adapt(F))
print("\nPar strategie, sens de la tendance seulement :")
print(F.groupby(["strat", "per"]).R.agg(["count", "mean"]).unstack().round(3).to_string())
print("\nPar strategie, CONTRE la tendance :")
print(T[T.side != T.tend].groupby(["strat", "per"]).R.agg(["count", "mean"]).unstack().round(3).to_string())
print("\nachats / ventes dans le sens de la tendance, 2025-26 :")
print(F[F.open_time >= "2025"].groupby(["strat", "side"]).eur.agg(["count", "sum"]).round(0).to_string())
