# DayTrader_MT5 v1.01 : fichiers pour TradeNotifier

## Dépôt des fichiers
- **Dossier** : `MQL5\Files\DayTrader\outbox\`, dans le dossier du terminal (pas FILE_COMMON).
- **Nom** : `AAAAMMJJ_HHMMSS_TYPE_POSITION.txt`, avec la date et l'heure du **serveur**.
  - Si le nom est déjà pris, le robot ajoute 1 seconde.
- **Écriture** : d'abord en `.tmp`, puis `FileMove` en `.txt`.
- **Contenu** : ANSI, une ligne `cle=valeur`, point décimal, textes sans accents. Les nombres de variation et de résultat sont signés (`+1.23`, `-0.45`).
- DayTrader n'appelle **jamais** `SendNotification`.
- `DayTrader\journal.csv` et `DayTrader\etat.txt` appartiennent au robot : ne pas les déplacer.

## Clés communes à tous les fichiers
| clé | exemple |
|---|---|
| type | MATIN, SOIR, OUVERTURE, FERMETURE |
| heure_serveur | 2026-11-03 10:15:02 |
| heure_paris | 2026-11-03 09:15:02 (horloge du PC) |
| position | 0 pour MATIN/SOIR, sinon l'identifiant de la position |
| robot | DayTrader_MT5 |
| devise | EUR |
| trades_fermes_jour, gagnants_jour, perdants_jour | 2, 1, 1 |
| resultat_bot_jour | +85.20 (trades du robot fermés aujourd'hui, heure serveur) |
| bilan.DAX1B / bilan.DAXBRUIT / bilan.ORIB | 1 trade(s), +95.00 |
| capital, variation_capital_jour | 100085.20, +85.20 |
| coupe_circuit | non / OUI |

## MATIN et SOIR (position = 0)
- **Liste et extrêmes**
  - `marches=DE40,XAUUSD,US500,USTECH100M,US30,EURUSD,GBPUSD,XAGUSD,XTIUSD` : c'est la liste réelle. Le pétrole est le 1er symbole qui existe parmi XTIUSD, XBRUSD, USOIL, UKOIL, WTI et BRENT. Lire les préfixes ici.
  - `plus_forte_hausse=DE40 +1.23 %`, `plus_forte_baisse=XAGUSD -2.10 %`.
- **Par stratégie**
  - `strategie.<STRAT>.symbole`
  - `strategie.<STRAT>.plan` : ce que le filtre de tendance autorise aujourd'hui, par exemple "achats seulement (tendance 20 jours haussiere), risque 100 EUR".
- **Par marché `<SYM>.`**
  - `nom` : DAX 40, Or, S&P 500, Petrole WTI…
  - `prix`
  - `var_jour` (% depuis la clôture d'hier), `var_5j`, `var_20j`
  - `tendance20j` (haussiere / baissiere), `ecart_ma20_pct`
  - `atr_pct` (ATR 14 jours en % du prix), `atr_relatif` (ATR 14 / range moyen 60 jours), `volatilite` (faible < 0.85 ≤ normale ≤ 1.2 < forte)
  - `range_jour`, `range_vs_atr`, `haut_jour`, `bas_jour`

## OUVERTURE
- **Le trade**
  - `symbole`, `nom`
  - `sens` : achat ou vente
  - `strategie` : DAX1B, DAXBRUIT ou ORIB
  - `magic`, `lots`, `prix`, `stop`
  - `objectif` : le prix visé, ou "aucun (sortie par la strategie)"
  - `risque` : 1 R en devise
  - `raison_entree`
- **Le marché à ce moment-là** : les clés marché ci-dessus **sans préfixe**, de `var_jour` à `bas_jour`, mais sans `prix`.

## FERMETURE
Les mêmes clés que l'OUVERTURE, avec en plus :
- **Prix**
  - `prix_entree`
  - `prix` : le prix de sortie
- **Résultat**
  - `resultat` en devise, et `resultat_R`
  - `issue` : gagnant, perdant ou nul
  - `duree_min`
- **Excursions** (calculées à la minute près)
  - `mfe` : le plus grand gain latent, en devise
  - `mae` : la plus grande perte latente, en devise et négative
  - `mfe_R` et `mae_R`
- **Sortie** : `raison_sortie`, qui peut être :
  - stop touche
  - objectif atteint
  - fin de journee 18h30
  - retour dans la zone de bruit…
  - fermeture manuelle…

## Heures
Le serveur a 1 h d'avance sur Paris, et 2 h pendant les semaines où les heures d'été US et UE diffèrent (mi à fin mars, dernière semaine d'octobre).

| événement | heure serveur | heure de Paris |
|---|---|---|
| MATIN | 09:45 | 08:45 (avant l'ouverture du DAX) |
| SOIR | 23:05 | 22:05 (après la fermeture de l'or) |
| DAX1B : décision | 10:15 | 09:15 |
| DAX1B : fermeture au plus tard | 18:30 | 17:30 |
| DAXBRUIT : décisions toutes les 30 min | 10:30 à 18:00 | 09:30 à 17:00 |
| DAXBRUIT : fermeture au plus tard | 18:30 | 17:30 |
| ORIB : ordre posé à partir de | 17:30 | 16:30 |
| ORIB : fermeture au plus tard | 23:00 | 22:00 |

**Magic numbers** : 26110300 (DAX1B), 26110301 (DAXBRUIT) et 26110302 (ORIB).

Certains jours, il n'y aura aucun trade : c'est le cas quand la tendance de 20 jours va contre le signal.
