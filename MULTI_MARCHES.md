# Bot multi-marchés : ce que j'ai cherché, testé et construit

## 1. Les stratégies cherchées

| Piste | D'où elle vient |
|---|---|
| **S1 / S1b : croisement de moyennes (EMA 8 / SMMA 30, H1)** | Notre premier bot (vidéo Impact Trading), étendu à la vente et à tous les marchés, avec un stop en ATR (la volatilité du marché) au lieu de 55 pips fixes |
| **S2 : cassure du plus haut / plus bas de la veille** | Très populaire sur l'or sur YouTube (ex. « Backtesting a Previous Day High and Low Breakout Strategy on XAUUSD », Trading Steady, juin 2026) |
| **S3 : cassure de Londres** | Le range de la session asiatique, puis une entrée quand Londres le casse. Classique sur l'or et le forex (guides « London breakout », « Opening range breakout ») |
| **S4 : tendance Donchian 20/10 jours** | Le « time series momentum » documenté par AQR sur un siècle et 67 marchés (Hurst, Ooi, Pedersen, 2017), et la méthode des Turtles |
| **S5 : EMA 50 / EMA 200 (H1)** | La stratégie de ta 2e vidéo (Paul Bourdeau) : SL 500 pts, TP 1000 pts, trailing 200 pts, fermeture au croisement inverse |

## 2. Les résultats sur l'or + 11 paires forex (H1, nov. 2012 → mars 2022)

Les coûts sont réalistes (spread de chaque marché + glissement). Le risque est de 0,5 % du capital par trade.

| Stratégie | Trades | Jours avec un trade | Gain moyen par trade (R) | Profit factor | Résultat |
|---|---|---|---|---|---|
| S1 croisement MM (achat + vente) | 8 898 | 94 % | −0,03 | 0,93 | **−76 %** |
| S1b croisement MM (achat seul) | 6 489 | 91 % | −0,02 | 0,95 | **−59 %** |
| S2 cassure de la veille | 24 107 | 99 % | −0,09 | 0,81 | **−100 %** |
| S3 cassure de Londres | 27 174 | 99 % | −0,05 | 0,91 | **−100 %** |
| S4 tendance Donchian | 1 317 | 38 % | −0,06 | 0,87 | **−36 %** |
| S5 EMA 50/200 (2e vidéo) | 4 304 | 78 % | −0,02 | 0,89 | **−40 %** |

(R = gain ou perte d'un trade divisé par le risque pris. +0,05 R par trade, c'est déjà un bon système.)

**La vérité brute : appliquées partout et tous les jours, toutes ces stratégies perdent de l'argent.** Avant les coûts, elles sont proches de zéro (entre −0,05 et +0,02 R). Le spread mange ensuite 0,01 à 0,07 R par trade. Plus le bot trade souvent, plus il paie de spread. Trader tous les jours n'est pas un avantage en soi.

## 3. Trier les marchés : ce qui tient et ce qui ne tient pas

- **Test honnête.** J'ai choisi les couples stratégie + marché gagnants sur 2012-2017, puis je les ai testés sur 2018-2022. Résultat : **−0,015 R par trade**, donc toujours perdant. Seuls 8 couples sur 25 restent gagnants.
- **Les couples gagnants sur les DEUX périodes** sont ceux qui sont réglés par défaut dans MultiBot :

| Marché | Stratégie | R moyen 2012-2017 | R moyen 2018-2022 |
|---|---|---|---|
| GBPJPY | MM (achat + vente) | +0,06 | +0,09 |
| GBPUSD | MM (achat + vente) | +0,03 | +0,02 |
| USDJPY | MM achat seul | +0,18 | +0,05 |
| EURJPY | MM achat seul | +0,02 | +0,04 |
| USDJPY | Cassure de Londres | +0,08 | +0,02 |
| GBPJPY | EMA 50/200 | +0,02 | +0,07 |
| XAUUSD (or) | Cassure de Londres | +0,06 | −0,005 (≈ 0) |

Ensemble, à 0,5 % de risque par trade : environ **+16 % par an, une pire baisse de −13,5 %**, et un trade **96 % des jours**. Avec l'or : un trade 99 % des jours, mais 3 années négatives et une pire baisse de −20 %.

⚠️ **Ces chiffres sont flatteurs par construction.** J'ai gardé ce qui avait marché sur les deux périodes, donc en connaissant déjà le résultat. Le vrai test, c'est sur des données que je n'ai pas encore vues : **2022 → 2026, dans le testeur MT5 de ton PC.** Si le bot y perd, on ne le lance pas en démo.

**L'or :** aucune stratégie n'a tenu sur les deux périodes. Je l'ai laissé avec la cassure de Londres parce que tu le voulais, mais attends-toi à environ zéro. Si le test 2022-2026 est négatif, retire `XAUUSD:LONDON` de la config.

## 4. Le bot : MultiBot_MT5.mq5

Un seul robot, posé sur un seul graphique, gère tous les marchés en même temps.

- **Config** : `InpConfig = "GBPJPY:MM,GBPUSD:MM,USDJPY:MMLONG,EURJPY:MMLONG,USDJPY:LONDON,GBPJPY:MM200,US500:DIP,US30:DIP,USTECH100M:DIP"`. Tu ajoutes ou retires des `SYMBOLE:STRATEGIE`.
- **Stratégies** : `MM`, `MMLONG`, `MM200`, `LONDON`, et `DIP` (achat sur repli des indices US, ajouté le 31/10). Les détails sont en tête du fichier.
- **L'or** est retiré de la config depuis le 31/10 (choix d'aurele) : il double la pire baisse sans avantage prouvé. Pour le remettre, ajoute `,XAUUSD:LONDON`.
- **Indices** : les noms dépendent du broker. Chez MetaQuotes-Demo, ce sont `US500`, `US30` et `USTECH100M`. Ailleurs, ce peut être `SPX500`, `NAS100`, etc. Un symbole introuvable est simplement ignoré.
- **Risque** : le lot est calculé pour risquer `InpRiskPct` = 0,5 % du capital par trade (forex et or). Pour les indices, c'est `InpDipRiskPct` = 1 %.
- **Protections** :
  - 10 positions maximum en même temps ;
  - plus d'entrées si la journée perd plus de 3 % ;
  - coupe-circuit si le capital baisse de plus de 20 % depuis son plus haut ;
  - filtre de spread ;
  - blocage sur compte réel.
- **Suffixe broker** : si tes symboles s'appellent par exemple `XAUUSD.m`, mets `.m` dans `InpSymbolSuffix`.

### Le tester dans MT5 (étape obligatoire)

1. MetaEditor (F4) → ouvre `MultiBot_MT5` → **F7**. Ça doit afficher 0 erreur. Sinon, envoie-moi l'erreur.
2. Testeur de stratégie (Ctrl+R) → Expert : MultiBot_MT5. Symbole : n'importe lequel (ex. EURUSD), le bot trade tous ceux de sa config. Période **H1**. Dates **01/03/2022 → aujourd'hui**. Modélisation « OHLC sur M1 » (rapide) puis « ticks réels » (précis). Dépôt 10 000.
3. Envoie-moi le rapport, ou dis-moi quand c'est fini : je le lis directement dans ton dossier MT5.

**Résultats du vrai test 2022-2026 et du module indices : voir `RESULTATS_2022_2026.md`.**

## 5. Les limites

- Pas d'indices (S&P 500, Nasdaq, DAX), de pétrole ni de crypto : je n'ai pas leurs données ici. Ton MT5 les a. C'est la prochaine étape logique, et c'est là que l'étude AQR trouve le plus de tendance : la diversification entre classes d'actifs, pas seulement entre paires de devises.
- Le drawdown est mesuré trade par trade fermé : la baisse réelle en cours de trade peut être un peu plus forte.
- L'ordre haut/bas à l'intérieur d'une bougie H1 est inconnu : j'ai pris des hypothèses prudentes.
