"""Decalage horaire (03/11/2026, Melvin + Claude).

Constat dans les donnees M15 : le serveur MetaQuotes-Demo suit l'heure d'ete EUROPEENNE.
 - Le DAX ouvre toujours a 10h00 serveur (= 9h00 Francfort) : il est bien cale toute l'annee.
 - Pendant les semaines ou les Etats-Unis sont deja (ou encore) a l'heure d'ete et pas l'Europe
   (2e dimanche de mars -> dernier dimanche de mars, dernier dimanche d'octobre -> 1er dimanche de novembre),
   New York est a serveur - 6 h au lieu de serveur - 7 h : l'ouverture US passe de 16h30 a 15h30 serveur
   et les CFD ferment a 23h00 serveur au lieu de minuit.

Constat 2 (le plus important) : depuis fin mars 2026, la derniere bougie de l'or est 22h45 TOUS les jours :
le marche ferme a 23h00 serveur. La v1.07 ferme l'or a 23h00 : trop tard, la position passe la nuit.
La v1.08 ferme l'or a 22h50 (ou 10 min avant la fin de seance du broker).

Ce script :
 0. affiche l'heure de la derniere bougie de l'or, mois par mois ;
 1. affiche la preuve (amplitude moyenne des bougies 15 min du S&P 500 a 15h30 et 16h30, semaines normales / decalees) ;
 2. rejoue l'Initial Balance de l'or (sans_yen/daytrade2.initial_balance) avec les heures fixes (comme la v1.07)
    puis avec les heures New York recalees pendant les semaines decalees. Resultat : rien de prouve (40 trades),
    la v1.08 garde donc les heures d'entree de la v1.07.
Resultats a 100 EUR par trade, couts prudents (spread x 1,2).
"""
import os, sys
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sans_yen"))
from daytrade import load15, hm  # noqa
from recherche import mk  # noqa

NY, EU = ZoneInfo("America/New_York"), ZoneInfo("Europe/Berlin")


def semaine_decalee(day):
    """True si New York est a l'heure d'ete et pas l'Europe ce jour-la (midi UTC)."""
    t = pd.Timestamp(day).tz_localize("UTC") + pd.Timedelta(hours=12)
    return bool(t.tz_convert(NY).dst()) and not bool(t.tz_convert(EU).dst())


def preuve():
    d = load15("US500")
    d["r"] = d.high - d.low
    d["gap"] = [semaine_decalee(x) for x in d.index.normalize()]
    d["hh"] = d.index.hour * 100 + d.index.minute
    print("Amplitude moyenne des bougies 15 min du S&P 500 (points) :")
    for g, lab in [(False, "semaines normales "), (True, "semaines decalees ")]:
        x = d[d.gap == g]
        print(f"  {lab}: 15h30 = {x[x.hh == 1530].r.mean():.1f}   16h30 = {x[x.hh == 1630].r.mean():.1f}   "
              f"derniere bougie du jour (mode) = {x.groupby(x.index.date).hh.max().mode().iloc[0]}")


def ib(df, recale, minp=0.003, maxp=0.015):
    """Copie de daytrade2.initial_balance ; si recale, toutes les heures New York sont avancees d'1 h les semaines decalees."""
    out = []
    for day, g in df.groupby(df.index.date):
        s = 100 if (recale and semaine_decalee(day)) else 0
        k = np.array([hm(t) for t in g.index])
        ib0, ib1, last_entry, exit_hm = 1630 - s, 1715 - s, 2200 - s, 2245 - s
        r = g[(k >= ib0) & (k <= ib1)]
        if len(r) < 3:
            continue
        hi, lo = r.high.max(), r.low.min(); w = hi - lo
        if not (minp <= w / r.open.iloc[0] <= maxp):
            continue
        after = g[k > ib1]
        side = 0; pos = None
        for t, (o, h, l, c) in zip(after.index, after[["open", "high", "low", "close"]].values):
            x = hm(t)
            if pos is None:
                if x > last_entry: break
                if side == 0:
                    if h > hi: side = 1
                    elif l < lo: side = -1
                    continue
                e = hi - 0.25 * w if side == 1 else lo + 0.25 * w
                if (side == 1 and l <= e) or (side == -1 and h >= e):
                    ent = min(o, e) if side == 1 else max(o, e)
                    pos = (side, ent, ent - side * 0.6 * w, (hi + 0.5 * w) if side == 1 else (lo - 0.5 * w), 0.6 * w, t)
                else:
                    continue
            sd, e, sl, tp, rk, t0 = pos
            if (sd == 1 and l <= sl) or (sd == -1 and h >= sl):
                out.append(mk("XAUUSD", sd, t0, t, e, sl, rk)); pos = None; break
            if (sd == 1 and h >= tp) or (sd == -1 and l <= tp):
                out.append(mk("XAUUSD", sd, t0, t, e, tp, rk)); pos = None; break
            if x >= exit_hm:
                out.append(mk("XAUUSD", sd, t0, t, e, c, rk)); pos = None; break
        if pos is not None:
            sd, e, sl, tp, rk, t0 = pos
            out.append(mk("XAUUSD", sd, t0, after.index[-1], e, after.close.iloc[-1], rk))
    T = pd.DataFrame(out)
    T["day"] = T.open_time.dt.normalize()
    T["gap"] = [semaine_decalee(x) for x in T.day]
    return T


def bilan(T, lab):
    g = T[T.gap]
    print(f"  {lab:28s} tous les jours : {len(T):4d} trades, {round(T.R.sum() * 100):+7d} EUR | "
          f"semaines decalees seules : {len(g):3d} trades, {(g.R > 0).sum():2d} G / {(g.R <= 0).sum():2d} P, "
          f"{round(g.R.sum() * 100):+6d} EUR")


def fermeture_or():
    d = load15("XAUUSD")
    last = d.groupby(d.index.normalize()).apply(lambda g: g.index.max().strftime("%H:%M"))
    print("Derniere bougie de l'or (heure serveur), la plus frequente par mois :")
    print("  " + "  ".join(f"{m}:{v.mode().iloc[0]}" for m, v in last.groupby(last.index.to_period("M")) if str(m) >= "2025-10"))


if __name__ == "__main__":
    fermeture_or()
    preuve()
    gold = load15("XAUUSD")
    print("\nOr, Initial Balance brute (sans filtres A/B/C ni tendance), 100 EUR par trade, depuis", gold.index[0].date())
    bilan(ib(gold, False), "heures fixes (v1.07)")
    bilan(ib(gold, True), "heures recalees (rejete)")
