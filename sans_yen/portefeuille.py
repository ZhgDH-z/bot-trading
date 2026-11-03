"""Portefeuilles sans yen + comparaison avec des trades au hasard, sur le TEST FINAL 2022-03 -> 2026-10."""
import numpy as np, pandas as pd
from recherche import *

T = pd.concat([pd.read_pickle(os.path.join(HERE, "tous_trades.pkl")), pd.read_pickle(os.path.join(HERE, "tous_trades2.pkl"))])
T["ligne"] = T.strat + ":" + T.symbol

# Regle fixee d'avance : on garde une ligne si R moyen > 0 en 2012-17 ET en 2018-21 (>= 20 trades par periode)
g = T.groupby(["ligne", "periode"]).R.agg(["count", "mean"]).unstack()
ok = g[(g[("mean", "A_2012-17")] > 0) & (g[("mean", "B_2018-21")] > 0) &
       (g[("count", "A_2012-17")] >= 20) & (g[("count", "B_2018-21")] >= 20)]
print("Lignes retenues (gagnantes sur les 2 premieres periodes) :")
print(ok.round(3).to_string())

def stats(t, risk):
    t = t.sort_values("close_time")
    eq = 10000 * np.cumprod(1 + risk[t.ligne].values / 100 * t.R.values)
    eq = pd.Series(eq, index=t.close_time.values)
    yrs = (t.close_time.max() - t.open_time.min()).days / 365.25
    dd = (eq / np.maximum.accumulate(np.r_[10000, eq.values])[1:] - 1).min()
    m = eq.resample("ME").last().ffill()
    mr = m.pct_change().fillna(m.iloc[0] / 10000 - 1)
    bd = pd.bdate_range(t.open_time.min(), t.close_time.max())
    # jours ou le bot OUVRE au moins un trade, et jours ou il a au moins une position ouverte
    opened = t.open_time.dt.normalize().nunique() / len(bd)
    held = set()
    for a, b in zip(t.open_time.dt.normalize(), t.close_time.dt.normalize()):
        held.update(pd.bdate_range(a, b))
    y = eq.groupby(eq.index.year).last(); y = (y / np.r_[10000, y.values[:-1]] - 1) * 100
    return dict(trades=len(t), R_moyen=round(t.R.mean(), 3), par_an_pct=round(((eq.iloc[-1]/10000) ** (1/yrs) - 1) * 100, 1),
                pire_baisse_pct=round(dd * 100, 1), mois_positifs_pct=round((mr > 0).mean() * 100),
                pire_mois_pct=round(mr.min() * 100, 1), jours_avec_ouverture_pct=round(opened * 100),
                jours_en_position_pct=round(len(held) / len(bd) * 100), par_annee=y.round(1).to_dict())

def risk_for(lines, fx=0.5, idx=1.0):
    return pd.Series({l: (idx if l.split(":")[1] in INDICES else fx) for l in lines})

C = T[T.periode == "C_2022-26"]
keep = list(ok.index)
# variantes RSI2 / RSI2_25 sur le meme indice : on garde la plus frequente (RSI2_25) pour eviter les doublons
keep = [l for l in keep if not (l.startswith("RSI2:") and l.replace("RSI2:", "RSI2_25:") in keep)]
# Nasdaq : pas de donnees avant 2020, on applique la meme regle que S&P / Dow (choix annonce, pas un resultat)
keep.append("RSI2_25:USTECH100M")
print("\nPortefeuille QUALITE :", keep)
print("Par ligne (test final) :")
print(C[C.ligne.isin(keep)].groupby("ligne").R.agg(["count", "mean"]).round(3).to_string())
print("QUALITE", stats(C[C.ligne.isin(keep)], risk_for(keep)))

# Portefeuille FREQUENT : + lignes proches de zero pour trader plus souvent
freq = keep + ["ASIE:EURUSD", "ASIE:EURGBP", "ASIE:USDCHF", "REPLI_US:US500", "REPLI_US:DE40", "REPLI_US:USTECH100M",
               "TOM:US500", "TOM:US30", "TOM:DE40"]
print("FREQUENT", stats(C[C.ligne.isin(freq)], risk_for(freq)))
pd.to_pickle(dict(keep=keep, freq=freq), os.path.join(HERE, "selection.pkl"))
C[C.ligne.isin(keep)].to_csv(os.path.join(HERE, "trades_test_final_qualite.csv"), index=False)

# ---------------- comparaison au hasard : memes marches, memes durees, memes stops, entrees au hasard
rng = np.random.default_rng(42)
print("\nHasard (500 tirages) vs strategie, test final :")
for l in keep:
    t = C[C.ligne == l]; sym = l.split(":")[1]; df = load(sym)
    df = df[df.index >= P3]
    o, h, lo_, cl, idx = df.open.values, df.high.values, df.low.values, df.close.values, df.index
    dur = ((t.close_time - t.open_time) / pd.Timedelta(hours=1)).clip(lower=1).astype(int).values
    sides = t.side.values; risks = t.risk.values / t.entry.values  # risque relatif
    means = []
    for _ in range(500):
        st = rng.integers(0, len(df) - 300, len(t)); Rs = []
        for s0, du, sd, rr in zip(st, dur, sides, risks):
            if l.startswith("ASIE"): sd = rng.choice([-1, 1])
            e = o[s0]; r = rr * e; sl = e - sd * r; px = None
            for j in range(s0, min(s0 + du, len(df) - 1) + 1):
                if (sd == 1 and lo_[j] <= sl) or (sd == -1 and h[j] >= sl): px = sl; break
            if px is None: px = cl[min(s0 + du, len(df) - 1)]
            Rs.append(mk(sym, sd, idx[s0], idx[min(s0 + du, len(df) - 1)], e, px, r)["R"])
        means.append(np.mean(Rs))
    means = np.array(means)
    print(f"{l:22s} strategie {t.R.mean():+.3f}  hasard median {np.median(means):+.3f}  "
          f"part des tirages au hasard qui font mieux : {(means >= t.R.mean()).mean()*100:.0f} %")
