# Day trading sans yen : ce que disent les données (02/11/2026)

Données : l'historique **15 minutes** de ton MT5, exporté le 02/11 (indices depuis mi-2022, forex depuis fin 2022).

Protocole :

- **Conception**, début 2022 → juin 2024 : je choisis les stratégies qui gagnent ;
- **Test final**, juillet 2024 → octobre 2026 : je ne l'ai pas regardé pour choisir.

Les coûts sont comptés avec des spreads de broker classique, plus larges que ceux de ta démo. Toutes les positions sont fermées le jour même.

## Les stratégies testées (13 marchés sans yen)

| Stratégie | Source | Conception | Test final |
|---|---|---|---|
| **Cassure des 30 premières minutes US** (S&P, Dow, Nasdaq) | ORB, classique du day trading | **+0,07 R** | −0,02 R |
| **Cassure des 30 premières minutes du DAX** | ORB | **+0,11 R** | −0,01 R |
| 1re bougie de 15 min US, dans son sens | Zarattini & Aziz 2023 | 0,00 R | −0,02 R |
| Cassure de Londres en 15 min (or, forex) | classique | −0,10 R | −0,03 R |
| Retour à la VWAP (indices, forex) | classique | −0,08 R | −0,05 R |

(R = gain d'un trade divisé par le risque pris.)

Les lignes gagnantes en conception, réunies en un bot, donnent ceci à 0,25 % de risque par trade :

- **conception** : environ 5 trades par jour, +28 % par an ;
- **test final** : environ 5 trades par jour, **−3 % par an, pire baisse −39 %**.

C'est le piège classique du day trading : ce qui marchait en 2022-2024 s'est éteint ensuite. Avant les coûts, ces stratégies sont proches de zéro, et le spread payé 5 fois par jour fait la différence. Contre des trades au hasard (mêmes heures, sens tiré au hasard), le bot fait un peu mieux : le hasard le bat 20 % du temps. L'avantage est trop petit pour payer les coûts.

## Les 3 versions possibles (chiffres du test final, juillet 2024 → octobre 2026)

| Version | Trades par jour | Jours avec trade | Par an | Pire baisse |
|---|---|---|---|---|
| A. **Hybride** : SansYen + module day trading à 0,1 % | ~5 | 95 % | **+8 %** | −14 % |
| B. Day trader pur à 0,1 % | ~4 | 92 % | −0,7 % | −13 % |
| C. Day trader pur à 0,25 % | ~4 | 92 % | −2 % | −29 % |
| (pour comparer : SansYen seul) | 0,7 | 48 % | +9 % | −12 % |

- **A** : tu as du day trading chaque jour, et le cœur SansYen (EURCHF la nuit, achat sur repli des indices US) porte le résultat. Le module day trading coûte à peu près 1 % par an : c'est le prix de l'activité quotidienne.
- **B / C** : de vrais day traders, mais sans avantage prouvé aujourd'hui. Bien pour apprendre en démo, pas pour gagner de l'argent.
- Sur ta démo, les spreads sont plus serrés qu'en réel : le module day trading y aura l'air un peu meilleur qu'il ne le sera.

**Pour aller plus loin :** l'historique en 5 minutes ne remonte qu'à 2025, parce que ton MT5 limite chaque export à 100 000 bougies. Si tu passes **Outils → Options → Graphiques → Nombre max de barres sur le graphique** à « Unlimited » puis redémarres MT5, je peux retester sur 2016-2026.

Scripts : `daytrade.py`, `daytrade_portfolio.py`. Données : `data_m15/`.
