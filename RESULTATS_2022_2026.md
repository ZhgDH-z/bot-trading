# Résultats sur les vraies données de ton broker (export MT5 du 31/10/2026)

Les données viennent de ton MT5 (serveur MetaQuotes-Demo), exportées par `ExportHistory.mq5`. Les coûts comptés sont le spread (plus large que celui de ton broker, donc prudent) et, pour les indices, un financement de nuit de 7 % par an.

## 1. Le bot forex/or, sur des données jamais vues (mars 2022 → octobre 2026)

La config de MultiBot a été fixée **avant** de voir ces données. C'est donc un vrai test.

| Marché | Stratégie | Trades | R moyen | Verdict |
|---|---|---|---|---|
| USDJPY | MM achat seul | 244 | **+0,25** | gagne |
| EURJPY | MM achat seul | 257 | +0,11 | gagne |
| USDJPY | Cassure de Londres | 1 097 | +0,08 | gagne |
| XAUUSD (or) | Cassure de Londres | 1 124 | +0,05 | gagne |
| GBPJPY | MM (achat + vente) | 364 | −0,06 | perd |
| GBPUSD | MM (achat + vente) | 394 | −0,04 | perd |
| GBPJPY | EMA 50/200 | 177 | −0,04 | perd |

À 0,5 % de risque par trade :

- **Sans l'or : +14 % par an**, pire baisse −10 %, 2026 à ce jour −0,3 % ;
- **Avec l'or : +21 % par an**, mais une pire baisse de −19 %.

**Ce qui fait vraiment gagner : la tendance, pas le signal.**

- Le dollar est passé de 115 à 157 yens (+37 %) et l'or a doublé (+102 %).
- Des **achats au hasard** sur USDJPY, avec le même stop, font +0,20 R par trade, contre +0,25 R pour le bot. Sur EURJPY, c'est +0,10 R au hasard contre +0,11 R pour le bot.
- Sur la cassure de Londres USDJPY, les achats font +0,15 R et les ventes 0.

En clair, le bot gagne parce qu'il est acheteur de yen faible et d'or fort. Si le yen se retourne, ces lignes perdent. C'est ce qui se passe **en octobre 2026** : les paires en yen y perdent 14 R, soit environ −7 %. C'est le pire mois de toute la période.

## 2. Le module indices : achat sur repli (RSI(2), journalier)

| Indice | Données | Trades | Gagnants | R moyen (avant 2018 / après) |
|---|---|---|---|---|
| **S&P 500 (US500)** | 2012 → 2026 | 130 | **79 %** | **+0,15** (+0,22 / +0,11) |
| **Nasdaq (USTECH100M)** | 2020 → 2026 | 54 | 74 % | **+0,14** |
| Dow Jones (US30) | 2012 → 2026 | 132 | 71 % | +0,05 (+0,06 / +0,04) |
| Nikkei (JPN225) | 2019 → 2026 | 60 | 67 % | +0,04 |
| Pays-Bas (NETH25) | 2011 → 2026 | 119 | 65 % | +0,02 |
| DAX (DE40) | 2012 → 2026 | 111 | 65 % | +0,01 |
| CAC 40 (FRA40) | 2019 → 2026 | 48 | 71 % | −0,02 |
| DAX tech (TECHDE30) | 2015 → 2026 | 86 | 63 % | −0,03 |

(Le FTSE 100 a un trou de 3 ans dans les données : il est inutilisable. Chez ce broker, « CAC », « DAX », « DOW » et « WTI » sont des actions ou des ETF, pas les indices.)

**L'avantage existe sur les indices américains**, comme le disent les études publiques sur le RSI(2). Ailleurs, il est proche de zéro. Je garde donc les 3 indices US : c'était le choix prévu avant le test.

Indices US seuls, à 1 % de risque par trade, de 2012 à 2026 :

- 316 trades, soit un trade environ 7 % des jours ;
- profit factor 1,79 ;
- **+2,5 % par an**, pire baisse **−4 %** ;
- 3 petites années négatives : −1,5 %, −2,8 % et −2,3 %.

À 2 % de risque, c'est +5 % par an pour une pire baisse de −8 %.

Il faut le dire franchement : ce module **ne rend pas riche**. Il est en position trop peu souvent. À titre de comparaison, garder le S&P 500 a rapporté environ +12 % par an, mais avec des baisses de −25 à −35 %. Son rôle dans le bot, c'est de **lisser** les résultats.

## 3. Les deux combinés (ton choix), mars 2022 → octobre 2026

Le forex est à 0,5 % de risque par trade, les indices US à 1 %.

| | Par an | Pire baisse | Mois positifs | Mois médian | Pire mois |
|---|---|---|---|---|---|
| Forex seul (sans or) | +14 % | −10 % | 62 % | +0,8 % | −7,6 % |
| **Forex + indices US** | **+19 %** | **−11 %** | **69 %** | **+1,6 %** | −7,3 % |
| Forex + or + indices US | +26 % | −19 % | 67 % | +1,9 % | −9,1 % |

Pour ton objectif de revenu mensuel : **environ 2 mois sur 3 sont positifs, et 1 sur 3 est négatif.** Ce n'est pas un salaire régulier, et aucun système honnête ne l'est.

## 4. Les limites (à garder en tête)

- Ce sont 4 ans et demi, portés par 2 grosses tendances (yen faible, or fort). Un retournement du yen, comme en août 2024 ou en octobre 2026, coûte cher.
- Les baisses sont mesurées sur les trades fermés. En cours de trade, elles peuvent être un peu plus fortes.
- Un backtest n'est pas le réel : glissements, requotes, swaps qui changent. D'où **3 mois minimum en démo** avant d'envisager quoi que ce soit.

Fichiers : `results/trades_2022_2026.csv`, `results/indices_us_trades.csv`, `results/combine_2022_2026.csv`.
