"""Demo reelle contre backtest, semaine par semaine (03/11/2026, Melvin + Claude).

Usage (depuis la racine du depot) :
    python suivi_demo/demo_vs_test.py CHEMIN/journal.csv [--version V107] [--depuis 2026-11-03] [--html rapport.html]

 - journal.csv : fichier ecrit par le robot dans MQL5\\Files\\DayTrader\\journal.csv (une ligne par sortie ;
   les demi-sorties de l'Or Initial Balance sont regroupees par position).
 - Reference : robuste/carnet_1an.json (trades du backtest de la derniere annee, a 100 EUR par trade).
 - Tout est ramene a 100 EUR de risque par trade (resultat / risque x 100), achat comme vente, heures de Paris.

Ce que dit le rapport :
 1. par semaine : trades, gagnants, perdants, resultat de la demo, et ce que le backtest faisait en semaine normale
    (moyenne et fourchette des 80 % de semaines du milieu) ;
 2. par ligne (DAX1B, DAXST, ORIB, ORTEND, ORBREAK) : demo contre backtest en nombre de trades par semaine et en
    resultat moyen par trade, avec un verdict qui tient compte du hasard (ecart en nombre d'erreurs-types) ;
 3. les anomalies : positions qui ont passe la nuit (le robot doit tout fermer le jour meme), lignes inconnues.
Regle : avec moins de 30 trades sur une ligne, aucun verdict n'est fiable. Il faut plusieurs semaines.
"""
import argparse, json, os, sys
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOMS = {"DAX 1re bougie": "DAX1B", "DAX supertrend 15 min": "DAXST", "Or Initial Balance": "ORIB",
        "Or tendance du jour": "ORTEND", "Or cassure de canal 200 bougies": "ORBREAK", "DAX zone de bruit": "DAXBRUIT"}
LIBELLE = {v: k for k, v in NOMS.items()}
SERVEUR_MOINS_PARIS = pd.Timedelta(hours=1)   # serveur MetaQuotes-Demo = heure de Paris + 1 h (verifie dans les donnees)


def lire_demo(path, depuis):
    j = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)
    num = ["risque", "resultat", "resultat_R"]
    for c in num:
        j[c] = pd.to_numeric(j[c].str.replace("+", "", regex=False).str.replace(",", "."), errors="coerce")
    for c in ["ouverture_serveur", "fermeture_serveur"]:
        j[c] = pd.to_datetime(j[c].str.replace(".", "-", regex=False), errors="coerce")
    # une position = un trade (les demi-sorties ORIB sont additionnees)
    g = j.groupby("position").agg(strategie=("strategie", "first"), symbole=("symbole", "first"), sens=("sens", "first"),
                                   ouverture=("ouverture_serveur", "min"), fermeture=("fermeture_serveur", "max"),
                                   risque=("risque", "max"), resultat=("resultat", "sum"), sorties=("resultat", "size"))
    g = g[g.risque > 0].copy()
    g["ouverture"] = g.ouverture - SERVEUR_MOINS_PARIS
    g["fermeture"] = g.fermeture - SERVEUR_MOINS_PARIS
    g["eur100"] = g.resultat / g.risque * 100
    g = g[g.ouverture >= pd.Timestamp(depuis)]
    g["semaine"] = g.ouverture.dt.normalize() - pd.to_timedelta(g.ouverture.dt.dayofweek, unit="D")
    return g.sort_values("ouverture")


def lire_test(version):
    d = json.load(open(os.path.join(ROOT, "robuste", "carnet_1an.json"), encoding="utf-8"))
    t = pd.DataFrame([x for x in d["trades"] if x[0] == version],
                     columns=["id", "ligne", "sens", "ouverture", "fermeture", "eur100", "semaine"])
    if t.empty:
        sys.exit(f"Version {version} absente de robuste/carnet_1an.json")
    t["strategie"] = t.ligne.map(NOMS)
    semaines = pd.Index(d["weeks"])
    return t, semaines


def norme_semaine(t, semaines):
    w = t.groupby("semaine").eur100.sum().reindex(semaines, fill_value=0.0)
    return dict(moy=w.mean(), bas=w.quantile(0.10), haut=w.quantile(0.90), trades=len(t) / len(semaines))


def verdict(n, moy_demo, moy_test, sd_test):
    if n < 30:
        return "trop tot (moins de 30 trades)"
    z = (moy_demo - moy_test) / (sd_test / np.sqrt(n))
    if z < -2.5: return f"ALERTE : nettement sous le test ({z:+.1f} erreurs-types)"
    if z < -1.5: return f"a surveiller : sous le test ({z:+.1f})"
    if z > 2.5:  return f"bien au-dessus du test ({z:+.1f}), verifier qu'il n'y a pas d'erreur"
    return f"dans la norme du test ({z:+.1f})"


def rapport(demo, test, semaines, version):
    L = []
    nt = norme_semaine(test, semaines)
    L.append(f"DEMO contre BACKTEST {version} - 100 EUR par trade, heures de Paris")
    L.append(f"Demo : {len(demo)} trades du {demo.ouverture.min():%d/%m/%Y} au {demo.fermeture.max():%d/%m/%Y}"
             if len(demo) else "Demo : aucun trade")
    L.append(f"Backtest : {nt['trades']:.1f} trades par semaine, {nt['moy']:+.0f} EUR par semaine en moyenne, "
             f"8 semaines sur 10 entre {nt['bas']:+.0f} et {nt['haut']:+.0f} EUR\n")

    L.append("1. SEMAINE PAR SEMAINE")
    sem = []
    for s, g in demo.groupby("semaine"):
        tot = g.eur100.sum()
        etat = "normale" if nt["bas"] <= tot <= nt["haut"] else ("sous la fourchette" if tot < nt["bas"] else "au-dessus")
        sem.append(dict(semaine=f"{s:%d/%m/%Y}", trades=len(g), gagnants=int((g.eur100 > 0).sum()),
                        perdants=int((g.eur100 <= 0).sum()), resultat=round(tot), cumul=0, etat=etat))
    S = pd.DataFrame(sem)
    if len(S):
        S["cumul"] = S.resultat.cumsum()
        L.append(S.to_string(index=False))
        L.append(f"Attendu par le test sur {len(S)} semaine(s) : {nt['moy'] * len(S):+.0f} EUR ; demo : {S.resultat.sum():+.0f} EUR\n")

    L.append("2. LIGNE PAR LIGNE")
    rows = []
    nsem = max(1, demo.semaine.nunique())
    for st in ["DAX1B", "DAXST", "ORIB", "ORTEND", "ORBREAK"]:
        d, t = demo[demo.strategie == st], test[test.strategie == st]
        if t.empty and d.empty:
            continue
        mt, sdt = (t.eur100.mean(), t.eur100.std()) if len(t) else (0.0, 1.0)
        rows.append(dict(ligne=st, trades_demo=len(d), par_sem_demo=round(len(d) / nsem, 1),
                         par_sem_test=round(len(t) / len(semaines), 1),
                         gagnants_demo=f"{(d.eur100 > 0).mean() * 100:.0f} %" if len(d) else "-",
                         gagnants_test=f"{(t.eur100 > 0).mean() * 100:.0f} %",
                         eur_trade_demo=round(d.eur100.mean(), 1) if len(d) else np.nan, eur_trade_test=round(mt, 1),
                         total_demo=round(d.eur100.sum()), verdict=verdict(len(d), d.eur100.mean() if len(d) else 0, mt, sdt)))
    L.append(pd.DataFrame(rows).to_string(index=False) + "\n")

    L.append("3. ANOMALIES")
    nuit = demo[demo.ouverture.dt.date != demo.fermeture.dt.date]
    if len(nuit):
        L.append(f"{len(nuit)} position(s) ont passe la nuit (le robot doit fermer le jour meme) :")
        L.append(nuit[["strategie", "symbole", "sens", "ouverture", "fermeture"]].assign(eur100=nuit.eur100.round(0)).to_string())
    else:
        L.append("Aucune position n'a passe la nuit.")
    inc = demo[~demo.strategie.isin(LIBELLE)]
    if len(inc):
        L.append(f"{len(inc)} trade(s) d'une ligne inconnue : {sorted(inc.strategie.unique())}")
    return "\n".join(L), S, pd.DataFrame(rows), nuit


def html(texte, path):
    page = ("<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'><title>Demo contre backtest</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:24px;background:#fafafa}"
            "pre{background:#fff;border:1px solid #ddd;padding:16px;border-radius:8px;overflow:auto;font-size:13px}</style>"
            "</head><body><h1>Demo contre backtest</h1><pre>" + texte.replace("&", "&amp;").replace("<", "&lt;") +
            "</pre></body></html>")
    open(path, "w", encoding="utf-8").write(page)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("journal")
    a.add_argument("--version", default="V107")
    a.add_argument("--depuis", default="2026-11-03 15:07")
    a.add_argument("--html", default=None)
    o = a.parse_args()
    demo = lire_demo(o.journal, o.depuis)
    test, semaines = lire_test(o.version)
    txt, *_ = rapport(demo, test, semaines, o.version)
    print(txt)
    if o.html:
        html(txt, o.html)
        print(f"\nRapport HTML : {o.html}")
