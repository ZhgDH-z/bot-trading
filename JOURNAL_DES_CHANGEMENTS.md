# Journal des changements : du bot de la démo au bot final

Règle d'aurele (02/11/2026) : **on ne touche pas à la démo** tant qu'on n'a pas quelque chose de concret.
Le prochain bot déployé sera le bot **finalisé**. Ici, on note tout ce qu'on ajoute, retire ou rejette, avec la preuve.
Tous les résultats sont à 100 € de risque par trade, achat comme vente, en heure de Paris.
Journal semaine par semaine : https://claude.ai/artifact/Uko76BPScEdCUGMhJoGHo9

## Ce qui tourne en démo (ne pas modifier)
- Depuis le 03/11/2026 à 15h07 (Paris) : DayTrader_MT5 **v1.07** sur le graphique DE40 (magics 26110700 à 26110704) + TradeNotifier sur EURUSD H1, compte démo XXXXXXXX (masqué). Passage confirmé (voir l'entrée du 03/11 vers 15h en bas).
- 5 lignes : DAX 1re bougie (DAX1B), DAX supertrend (DAXST), or Initial Balance (ORIB), or tendance (ORTEND), or cassure de canal 200 bougies (ORBREAK), plus le filtre de tendance 20 jours. Mises : 200 € à l'achat et à la vente, perte max 600 €/jour, coupe-circuit −20 %.
- Copie de référence : sans_yen/DayTrader_MT5_v107.mq5 et sans_yen/deploy107/.
- Historique : v1.01 du 02/11 21h40 au 03/11 2h47, puis v1.06 du 03/11 2h47 au 03/11 15h07.
- Test de la v1.01 (30/12/2024 → 02/11/2026) : 593 trades, 220 gagnants / 373 perdants, +11 553 €, 45 % de semaines gagnantes.

## Candidats retenus pour le bot final (testés, pas déployés)
| Date | Changement | Preuve | Statut |
|---|---|---|---|
| 02/11/2026 | DAX1B : pas de trade si la 1re bougie dépasse 0,19 × ATR du jour | Tient sur des mois jamais vus : +1 298 € gagnés en 2025-26 | À AJOUTER |
| 02/11/2026 | DAX1B : pas de trade le lundi | Tient hors échantillon : +657 € en 2025-26 | À AJOUTER |
| 02/11/2026 | Nouvelle ligne or ORTEND : 1 trade par jour dans le sens de la tendance 20 jours (entrée 9h, sortie au plus tard 22h, heure de Paris) | 472 trades, +3 412 €, 54 % de semaines gagnantes. Fragile : dépend du spread de l'or | À AJOUTER, à surveiller |
| Total v1.02 | Démo + les 3 changements ci-dessus | 966 trades, 437 G / 529 P, +16 828 €, 55 % de semaines gagnantes, pire semaine −696 € | Code prêt dans sans_yen/DayTrader_MT5.mq5 (v1.02), NON déployé |

## Testés et rejetés
| Date | Idée | Pourquoi rejetée |
|---|---|---|
| 02/11/2026 | IA « chef d'orchestre » qui choisit la stratégie selon le marché | Ne bat pas le hasard ; aurele ne veut pas de chef d'orchestre |
| 02/11/2026 | 8 correctifs trouvés sur toute la période | Sur-apprentissage : pas mieux que retirer des trades au hasard sur des mois non vus. Seuls 2 tiennent (ci-dessus) |
| 02/11/2026 | Une seule stratégie DAX qui fusionne toutes les analyses (votes) | −2 098 € sur 2025-26, seulement 99 trades |
| 02/11/2026 | Labo : le bot invente ses règles (6 000 règles) | Apprend mieux que le hasard, mais −3 335 € après coûts |
| 02/11/2026 | Méthodes populaires sur l'or (cassure du range d'Asie, SMC sweep, ICT) | Perdent sur 14 ans |
| 02/11/2026 | Momentum de fin de séance | Perd sur tous les marchés après coûts |

## L'Apprenti : bot à setups qui apprend en continu (02/11/2026, demande d'aurele)
Scripts : robuste/apprenti.py (setups + mémoire), apprenti_sorties.py, apprenti2.py, apprenti_carnet.py.
- 95 454 setups observés sur 13 marchés sans yen, 8 familles. Mémoire = plus proches voisins, poids plus fort au récent, jamais de données futures.
- **Version 1** (trader si la chance de gain estimée ≥ 55-70 %, sortie 1:1) : REJETÉE. La mémoire annonce 60-70 % mais le vrai taux reste à 48 %, et chaque version perd (−718 € à −74 330 €).
- **Constat** : un taux de gain élevé (61 %) s'obtient avec un petit objectif, mais il perd de l'argent après coûts. Ce qui gagne, ce sont des stops serrés et des trades tenus jusqu'en fin de séance (environ 30-40 % de gagnants, gros gains).
- **Version 2** (la mémoire choisit aussi la sortie ; trade si le gain attendu est ≥ 0,10 R ; 1 trade par marché et par jour ; DAX, or, S&P 500, Nasdaq, Dow Jones) :
  - 2023-24 : +2 901 € ; 2025-26 : +14 271 € ; bat le hasard (p < 0,001) ; environ 4,3 trades par jour, au moins 3 trades 89 % des jours.
  - 2025-26 en détail : 2 007 trades, 785 G / 1 219 P (39 %), +14 096 €, 47 % de semaines gagnantes, pire semaine −1 660 €, sans les 5 meilleures semaines +852 €.
  - Fragile : le résultat change beaucoup selon le seuil (+4 416 € à +17 172 €). L'argent a été retiré après avoir vu les résultats (biais). Le S&P 500 perd sur 2025-26.
  - Statut : EN OBSERVATION, pas prêt pour le bot final.

## Analyse des pertes (03/11/2026, demande d'aurele : « 216 perdants pour 127 gagnants »)
Scripts : robuste/pertes.py (contexte + excursion de chaque trade), robuste/rectif.py (gestion du trade rejouée sur bougies 15 min).
Règle : un correctif trouvé sur la dernière année (03/11/2025 → 02/11/2026) doit AUSSI aider sur 2023 → 10/2025.
- **Pourquoi autant de perdants** : la ligne DAX 1re bougie gagne 26 % du temps (stop serré de l'autre côté de la 1re bougie, 74 % de ses trades touchent le stop), mais son gagnant moyen fait +322 € à +443 €. 37 des 216 perdants de la démo sont des petites pertes (moins de 30 €) en fin de journée.
- **Monter le taux de gain coûte de l'argent** (rejeté) : stop au prix d'entrée après +1 R → 42 % de gagnants mais −330 € (L) et −2 870 € (P) ; moitié à +1 R + stop à l'entrée → 52 % de gagnants mais −1 749 € (L) et −7 277 € (P).
- **Correctifs retenus (v1.03)**, tous sur l'or, vérifiés sur les deux périodes :
  - A. Or Initial Balance : fermer la moitié à +0,5 R. L +393 €, P +1 187 €.
  - B. Or Initial Balance : pas de trade si l'élan 5 jours va contre le trade. L +444 €, P +528 €.
  - C. Or tendance du jour : pas de trade quand la volatilité est agitée (ATR 14 / ATR 100 > 1,2). L +450 €, P +657 €.
  - v1.03 = v1.02 + A + B + C, dernière année : 444 trades (1,7/jour), 208 G / 235 P (47 %), +7 736 € (v1.02 : +6 526 €), 10 mois gagnants sur 12, pire mois −175 €, au plus 7 trades perdants de suite.
- **En option (D)** : pas de vente sur DAX 1re bougie. Neutre sur la dernière année, +1 541 € sur 2023-2025. La démo met déjà 50 € sur les ventes.

## Taille des positions (03/11/2026)
- Tests passés à 1 000 € risqués par trade (résultats × 10). v1.03 sur la dernière année : +77 360 €, pire baisse −12 440 €.
- **Règle « 1 trade sur 3 à 1 000 €, les 2 autres à 200 € »** (v1.03, dernière année) : de +25 240 € à +46 560 € selon le trade qui tombe à 1 000 €. Même risque moyen fixe (467 €/trade) : +36 102 €, pire baisse −5 805 € (contre −9 142 à −13 202 € avec la rotation). La rotation n'apporte que du hasard : NON RETENUE.
- DAX zone de bruit : le stop de secours est à 3 R (sortie normale vérifiée toutes les 30 min), donc une perte peut aller jusqu'à 3 fois la mise. Un stop à 1, 1,5 ou 2 R a été testé et fait pire sur les deux périodes : on garde 3 R.

## Recherche de lignes en plus pour atteindre 3 trades par jour (03/11/2026)
Méthode honnête : choisir sur 2023 → 02/11/2025, puis vérifier sur la dernière année (jamais vue pendant le choix).
- 224 combinaisons de setups sur l'or et le DAX (8 familles × 7 sorties × avec/sans filtre de tendance) : 2 seulement passent sur 2023-25 (DAX passage de la VWAP), et les 2 PERDENT sur la dernière année (−20 435 € et −23 359 € à 1 000 €/trade).
- 60 stratégies publiées (ORB 30 min DAX/US, Initial Balance indices, Londres or, chasse, Silver Bullet…) : les meilleures sur 2023-25 (ORB 30 min Nasdaq et S&P avec tendance) PERDENT sur la dernière année.
- L'Apprenti, marché par marché, varie trop d'une période à l'autre (DAX −18 680 € en 2023-24, puis +62 281 €, puis +30 288 €).
- Conclusion : aucune nouvelle ligne n'est validée. En ajouter maintenant ferait juste ajouter des trades perdants.

## Lignes DAX copiées sur d'autres marchés (03/11/2026, choix d'aurele)
Export M15 depuis le PC (script ExportM15_Indices, données dans data_m15b/, depuis 2022). Script robuste/nouveaux_marches.py. Même règles que la démo (filtre de tendance ; 1re bougie : pas le lundi, pas de grosse bougie). Résultats à 1 000 €/trade, P = jusqu'au 02/11/2025, L = dernière année.
- Indices européens (CAC 40, Euro Stoxx 50, AEX, Espagne, Suisse) : les 2 lignes PERDENT presque partout. Seule exception : la 1re bougie sur le CAC gagne sur P (+31 034 €) mais perd sur L (−6 925 €). DAX tech : frais trop élevés, inutilisable.
- Actions US (Nvidia, Tesla, Apple, AMD, Meta, Microsoft, Amazon, Google, Netflix) : la 1re bougie perd sur 7 actions sur 9. Seule la zone de bruit sur AMD gagne sur les deux périodes (+29 939 € puis +6 318 €), mais sur 30 essais un tel cas peut arriver par hasard.
- Conclusion : rien d'ajouté. Attention, le fait que les lignes DAX ne marchent nulle part ailleurs veut dire qu'une partie du résultat du DAX peut venir de la chance.

## À faire avant de finaliser
- Corriger le décalage horaire du DAX pendant les semaines où les heures d'été US/UE diffèrent (avant le 8 mars 2027).
- Comparer la démo réelle (journal.csv du PC) au test, semaine par semaine.
- Décision d'aurele avant tout remplacement de la démo.

## 03/11/2026 — Tri des skills « claude-trading-skills » (tradermonty)
- 74 skills lus et notés un par un : voir le Claude Doc https://claude.ai/artifact/24SgB9GJQpwg6nXpvM7PS1
- Repris sous forme adaptée, en français (proposés à l'installation) : « test-strategie-robuste » (d'après backtest-expert + edge-strategy-reviewer) et « revue-trades-bot » (d'après signal-postmortem + trade-performance-coach).
- Test des coûts ×2 sur la v1.03 : dernière année +68 454 €, période 2023-25 +100 880 € (à 1 000 €/trade). Robuste aux coûts.
- REJETÉ : coupe-circuit (drawdown-circuit-breaker) : pause de 24 h après 2 pertes fait tomber la dernière année de +77 360 € à +16 452 €.
- NON INSTALLÉ : mt5-robot-tester (ferme le terminal MT5 donc couperait la démo ; optimisation ±50 % = risque de sur-ajustement).
- Piste suivante : filtre « pas de trade autour des annonces US » (NFP, inflation, Fed) sur or et DAX, à tester sur P puis L.

## 03/11/2026 (vers 2h, heure de Paris) — Idées des skills testées sur la v1.03, puis robot v1.04
Toujours à 1 000 € de risque par trade. P = 2023 → 02/11/2025, L = dernière année.
- REJETÉ, filtre « annonces US » (emploi NFP, inflation CPI, Fed ; dates officielles FRED + Fed) : les trades qui traversent une annonce sont nos MEILLEURS (+0,75 R en moyenne sur P, +0,89 R sur L). Les retirer coûte −57 870 € sur P et −30 427 € sur L ; sortir juste avant l'annonce coûte −34 403 € / −15 581 €. Script robuste/news_filtre.py.
- REJETÉ, nouvelle ligne « réaction après l'annonce » (suivre ou contrer les 30 premières minutes, DAX et or) : DAX gagne sur P mais presque rien sur L (+384 € pour le meilleur réglage), or perd sur L. Moins de la moitié des réglages gagnent. Script robuste/news_reaction.py.
- REJETÉ, filtre COT (positions des fonds spéculatifs sur l'or, CFTC 088691) : toutes les variantes perdent ou ne changent rien sur L. Script robuste/cot_filtre.py, données cot_or.csv.
- ADOPTÉ (v1.04, preuve faible mais protection logique), garde-fou écart achat/vente : pas d'entrée si l'écart de la dernière bougie dépasse 2 × sa médiane des 20 jours. Ces trades perdent sur P (30 trades, −8 021 €) et sur L (2 trades, −1 598 €). Le retrait de 32 trades au hasard ferait aussi bien dans environ 5 % des cas seulement. Dans la réalité, ces trades coûteraient encore plus cher que dans le test (coûts fixes dans le test).
- AJOUTÉ (v1.04), alarme de dégradation sans arrêt automatique : message dans la notification de fermeture si les 60 derniers trades font moins de −16 × le risque (moins bien que 95 % du passé testé) ou moins de −31 × (pire que tout l'historique).
- Code : sans_yen/DayTrader_MT5_v104.mq5 = v1.02 + correctifs v1.03 (A moitié à +0,5 R sur ORIB, B élan 5 jours sur ORIB, C volatilité sur ORTEND) + D + E. Numéros magiques 26110400-403 (la démo reste en 261103xx). NON compilé, NON déployé : démo gelée.
- Estimation v1.04 : L environ +78 800 €, P environ +154 700 € (v1.03 : +77 186 € / +146 694 € dans ce calcul).
- Journal mensuel : v1.04 ajoutée (dernière année, 442 trades, +78 950 € à 1 000 €/trade ; 2 trades or tendance bloqués les 27 et 28/10/2026, −1 590 € évités).

## 03/11/2026 (vers 2h20, heure de Paris) — Dépôt finance-skills (himself65) testé, v1.05
26 skills lus, surtout des lecteurs de données sur les actions US et les réseaux sociaux. Idées testées, P puis L, 1 000 €/trade :
- REJETÉS (gagnent sur P, perdent sur L) : alignement H1/H4 (tradingview-mcp), sens de la nuit américaine (futures overnight), modèle de tendance Minervini (sepa-strategy). Script robuste/fs_filtres.py.
- 9 stratégies du backtest TradingView sur or et DAX, 15 min et 1 h (robuste/fs_strategies.py) : 11 réglages sur 72 gagnent sur les 2 périodes. Vérification des réglages voisins et des coûts ×2 (robuste/fs_robuste.py) : seul le SUPERTREND DAX 15 min tient (multiplicateur 3 à 4 et stop 1 à 2 ATR : 9 réglages sur 9 gagnants sur P et sur L ; la plupart tiennent aussi avec coûts ×2). Keltner, Donchian et croisement de moyennes : rejetés.
- ADOPTÉ (v1.05) : supertrend DAX 15 min, multiplicateur 4, stop 1,5 ATR (choisi sur P : +77 040 €), vérifié sur L : +23 037 € (223 trades, 32 % de gagnants). Prudence : test « sens au hasard » p = 0,07 sur P et 0,22 sur L. C'est un résultat prometteur, pas une preuve. Corrélation jour par jour avec la v1.03 : 0,39 sur L.
- v1.05 = v1.04 + supertrend DAX : dernière année +102 010 € (v1.04 : +78 950 €), 2,6 trades par jour, mais pire mois plus bas (environ −10 000 € au lieu de −1 800 €) et pire baisse −17 500 € (au lieu de −12 400 €).
- Code : sans_yen/DayTrader_MT5_v105.mq5 (ligne DAXST, magic 26110404). Ni compilé ni déployé.

## 03/11/2026 (vers 2h35, heure de Paris) — Dépôt trade-skills (himself65) testé : AUCUN ajout
Un seul skill (« trade ») : base de connaissances pour les options sur actions US, avec 38 « pièges » et des cas réels. Il demande des abonnements (Unusual Whales, Funda). Les règles applicables à notre bot ont été testées sur la v1.05 (P puis L, 1 000 €/trade) :
- Piège 31, limite de perte du jour (2 à 4 R) et arrêt après 2, 3 ou 4 pertes de suite (calcul exact, sans regarder l'avenir) : aucune variante ne gagne sur les 2 périodes. Rejeté. La limite actuelle du robot (300 € = 3 R à 100 €) est neutre : P −5 390 €, L +1 660 €.
- Piège 31, réduction de taille pendant les baisses (−5 % : ×0,75 ; −10 % : ×0,5) : P −25 393 €, L −24 962 €. Rejeté.
- Piège 31, risque cumulé (ne pas empiler 2 lignes DAX dans le même sens) : les trades empilés sont nos MEILLEURS. Les retirer coûte P −28 647 € et L −44 496 €. Rejeté.
- Piège 30, stop d'au moins 0,2 × ATR du jour sur la 1re bougie DAX : P −54 000 €, L −12 900 €. Rejeté : le stop serré EST l'avantage de cette ligne.
- Piège 4, se retourner après le stop (1re bougie DAX) : P +7 566 €, L −3 359 €. Rejeté.
- Piège 27, entrer sur le retest du milieu de la bougie : P −73 630 €, L −52 127 €. Rejeté.
Scripts : robuste/ts_tests.py, robuste/ts_dax1b.py. La v1.05 reste la meilleure version.

## 03/11/2026 (vers 2h40, heure de Paris) — Dépôt TradingAgents-AShare (KylinMountain) : AUCUN ajout
Ce dépôt n'a pas de stratégie de trading : c'est un système de 14 à 15 agents IA qui débattent (haussier contre baissier, puis les risques) pour conseiller l'achat ou la vente d'actions chinoises (A-shares) à quelques jours ou semaines. Il utilise des données chinoises (baostock), et chaque analyse coûte de nombreux appels à une IA payante. Un vrai test sur 3 ans est impossible sans biais, car l'IA connaît déjà l'historique. Son skill passe par leur service en ligne (app.510168.xyz) et le README fait de la publicité pour un revendeur d'API. Rien à intégrer. Sa « mémoire de réflexion » ressemble à notre Apprenti, déjà testé et perdant. La v1.05 reste la meilleure.

## 03/11/2026 (vers 2h50, heure de Paris) — Recherche de nouvelles stratégies + dépôt staskh/trading_skills : AUCUN ajout
- Supertrend 15 min avec les réglages du DAX FIGÉS (multiplicateur 4, stop 1,5 ATR), testé sur 19 autres marchés (robuste/st_marches.py). Il PERD sur les indices européens proches du DAX : CAC 40 −15 493 €, IBEX −32 433 €, SMI −34 956 €, AEX −15 399 € sur L. Il perd aussi sur l'or (−40 948 €) et sur la plupart des actions. Les indices US gagnent sur P mais presque plus sur L. Seul TSLA gagne sur les 2 périodes, avec les 9 réglages (+8 209 € sur P, +30 837 € sur L) : sur 20 marchés testés, ça peut être de la chance. TSLA est mis en observation.
- ALERTE sur la v1.05 : comme le supertrend ne marche pas sur les indices voisins, son résultat sur le DAX est peut-être en partie de la chance. À confirmer en démo avant d'y croire.
- Réduire les pertes du supertrend DAX (robuste/st_ameliore.py) : filtre ADX (scanner-bullish) : ADX ≥ 15 donne P −6 880 € et L +12 430 €, les autres seuils perdent. Tendance 20 jours : P −42 702 €. Stop suiveur (ib-trailing-stop), 6 variantes : toutes perdent sur les 2 périodes (de −8 791 € à −69 541 €). Tout est rejeté.
- Dépôt staskh/trading_skills : 29 skills pour actions et options US via le courtier Interactive Brokers (portefeuille, options, Greeks, stop-loss IB, scanner haussier SMA/RSI/MACD/ADX, calendrier économique). Rien pour MT5, DAX ou or. Les idées utilisables (ADX, stop suiveur, calendrier) sont testées ci-dessus et rejetées.

## 03/11/2026 vers 2h45 (Paris) : bot sur TOUS les marchés, stratégie adaptée à chaque marché (demande d'aurele)
- 26 marchés en plus du DAX et de l'or : 5 indices européens, 3 indices US, Nikkei, argent, 7 paires forex, 9 actions US.
- Menu fixé avant de regarder : 1re bougie, cassure 30 min, zone de bruit, tendance VWAP, Initial Balance, supertrend ×4 et ×3, chacun avec ou sans filtre de tendance 20 jours, et sur 2 sessions (Londres / New York) pour le forex, l'argent et le Nikkei.
- Choix sur P (2023 → 02/11/2025) : au moins 60 trades, gain moyen ≥ 0,03 R, les 2 moitiés de P gagnantes. Script robuste/tous_marches.py.
- Correction des données : Netflix divisé par 10 le 17/11/2025 (prix d'avant non ajustés dans l'export), coûts des actions = au moins 0,04 % du prix.
- Résultat : 8 marchés ont une stratégie valable sur P, 18 aucune. Sur la dernière année, ces 8 marchés font −83 013 € à 1 000 €/trade (GBP/USD −48 390 €, Dow −18 900 €, Nasdaq −16 400 €, S&P −4 360 €, EUR/USD −4 610 € ; Nikkei +7 540 €, Tesla +1 340 €, Netflix +710 €).
- Version « qui évolue » (chaque mois, meilleure stratégie des 6, 12 ou 24 derniers mois par marché ; robuste/tous_marches_wf.py) : perd encore plus, sur les 2 périodes (12 mois : −107 325 € avant, −144 434 € sur la dernière année).
- Journal mensuel : onglet « Tous les marchés (stratégie adaptée) » = v1.05 + les 8 marchés : +18 940 € sur la dernière année (v1.05 seule : +102 010 €), 8,8 trades par jour, 37 % de gagnants, 6 mois gagnants sur 12.
- Décision : RIEN d'intégré au bot. Adapter le choix au marché ne crée pas d'avantage : ces stratégies n'en ont pas, hors DAX et or, une fois les coûts payés.

## 03/11/2026 vers 2h50 (Paris) : journal nettoyé (demande d'aurele)
- Retirés du journal mensuel : L'Apprenti (−25 650 € à 1 000 €/trade), le Labo (−25 980 €), la stratégie unique DAX (−29 920 €), et les 6 marchés perdants de l'onglet « Tous les marchés ». Colonne « Confiance » retirée (elle ne servait qu'à l'Apprenti).
- Onglet devenu « v1.05 + Nikkei + Tesla (observation) » : +110 890 € sur la dernière année, 1 068 trades (4,2 par jour), 41 % de gagnants, 11 mois gagnants sur 12. Garder Nikkei et Tesla est un choix fait après avoir vu la dernière année : à confirmer en démo.
- Sauvegardes : robuste/carnet_1an_avant_tous.json, robuste/carnet_1an_avant_nettoyage.json.

## 03/11/2026 vers 3h (Paris) : stratégies faites pour le forex (robuste/fx_recherche.py)
- 7 paires sans yen, 4 familles, 26 réglages par paire : cassure de la fourchette asiatique à l'ouverture de Londres, retour à la moyenne pendant la nuit asiatique (les « scalpeurs de nuit »), retournement après le fixing de 16h à Londres (Melvin & Prins 2015, Evans 2018), effet heure du jour (Breedon & Ranaldo 2013).
- Avec les coûts habituels (écart prudent × 1,2) : AUCUN réglage ne passe sur 2023-25. Tout perd, sur les 2 périodes.
- AVANT coûts, il y a de vrais petits avantages : retour Asie EURCHF (9 réglages sur 9 gagnants sur les 2 périodes), cassure de Londres EURUSD (6 sur 6), fixing USDCHF. Mais ils gagnent 0,02 à 0,08 R par trade alors que les coûts en prennent 0,07 à 0,34 R.
- Il faudrait des coûts divisés par 2 (environ 0,6 pip tout compris) pour que la cassure de Londres EURUSD gagne (+4 498 € sur P, +5 115 € sur L) : pas réaliste en compte réel standard. Le compte démo MetaQuotes affiche presque 0 d'écart sur EURUSD, il serait donc trompeur.
- Décision : RIEN d'intégré au bot.

## 03/11/2026 vers 3h (Paris) : audit de la v1.05 ligne par ligne → v1.06 (demande d'aurele : « tout ce qui ne tient pas la route, enlève et corrige »)
Pour chaque ligne : P (2023 → 02/11/2025) et L (dernière année), en R ; frais ×2 ; comparaison au hasard (même trades, sens tiré au hasard, 5 000 tirages).
| Ligne | P | P frais ×2 | p hasard P | L | p hasard L | Verdict |
|---|---|---|---|---|---|---|
| Or Initial Balance | +22,9 R | +14,6 | 0,000 | +16,1 R | 0,002 | solide, gardée |
| Or tendance du jour | +40,1 R | +34,1 | 0,033 | +20,3 R | 0,034 | solide, gardée |
| DAX 1re bougie | +78,9 R | +64,2 | 0,036 | +25,3 R | 0,15 | gardée ; dépend de quelques gros gains (26 % de gagnants), c'est voulu |
| DAX supertrend | +77,0 R | +43,1 | 0,013 | +23,0 R | 0,12 | gardée ; 2023 légèrement négatif, à surveiller |
| DAX zone de bruit | +4,8 R (384 trades) | −12,0 | 0,26 | +15,5 R | 0,14 | **RETIRÉE** : ne tient pas sur P |
- v1.06 = v1.05 sans DAXBRUIT dans la config par défaut (code gardé), magic 26110600 à 26110603. Fichier sans_yen/DayTrader_MT5_v106.mq5. Ni compilée ni déployée.
- Dernière année à 1 000 €/trade : v1.06 +86 510 € (v1.05 : +102 010 €), 528 trades, 2,1 par jour, 43 % de gagnants, pire mois mai 2026 −14 310 € (v1.05 : −10 150 €). La zone de bruit gagnait cette année et amortissait mai, mais rien ne prouve que ça se répète.
- Onglet d'observation devenu « v1.06 + Nikkei + Tesla » : +95 390 €, pire mois mai 2026 −19 060 €. Tesla est presque à zéro sur la dernière année (+0,006 R par trade) : observation seulement.
- Vérifié et normal : mai 2026 vient surtout du supertrend DAX (−11 630 € en 17 trades), pas d'un bug.
- Sauvegarde : robuste/carnet_1an_avant_v106.json.

## 03/11/2026 vers 2h47 (Paris) : la v1.06 prend la main sur la démo (demande explicite d'aurele)
- DayTrader_MT5_v106.mq5 déposé dans MQL5\Experts et compilé : 0 erreur, 0 avertissement.
- Script MQL5\Scripts\PasseV106.mq5 : compte DEMO XXXXXXXX (masqué) vérifié, 0 position et 0 ordre ouverts. La v1.01 a été remplacée par la v1.06 sur le graphique DE40 M15 (modèle LanceDayTrader106.tpl). Lignes actives : DAX1B (magic 26110600), ORIB (26110601), ORTEND (26110602), DAXST (26110603).
- TradeNotifier v1.11 n'est pas touché (EURUSD H1). Il suit tous les magics.
- Réglages inchangés par rapport à la démo : risque 100 € à l'achat, 50 € à la vente, perte max 300 €/jour, coupe-circuit −20 %.
- ⚠️ Le bouton Algo Trading du terminal était COUPÉ au moment du remplacement : aurele doit le rallumer, sinon aucun trade.
- 03/11 vers 2h51 (Paris), choix d'aurele : risque 200 € à l'achat ET 200 € à la vente (InpRiskMoney=200, InpShortFactor=1.0). Limite de perte du jour montée à 600 € (3 × le risque, comme avant) pour ne pas couper le bot dès 2 pertes. v1.06 recompilée (0 erreur) et relancée sur DE40 M15 avec ces réglages par défaut. Algo Trading toujours COUPÉ à ce moment-là.

## 03/11/2026 vers 14h20 (Paris) : test du dépôt TradIA (juanserracasero-debug/TradIA)
- Le dépôt : bot Python de signaux pour BTC et ETH (Binance, données publiques), en simulation avec 10 € fictifs. Il tourne toutes les 15 min via GitHub Actions et envoie des emails (Mailjet). Score RSI 14 + croisement EMA 9/21 + MACD + Bollinger + volume, signal si score ≥ 3. Stop 0,75 %, objectif 1,5 %, clôture forcée à 22h45.
- Leur propre simulation (08 au 23/09/2026) : 13 trades, 5 gagnants, 8 perdants, −2,4 % au total.
- Nos marchés en M15, 2022-2026, 100 €/trade (robuste/tradia_test.py) : TOUT perd, sur les 7 marchés, en achat seul comme dans les 2 sens. Chiffres corrigés le 03/11 vers 14h25 (voir le bug plus bas) : DAX 2 sens −6 413 € (2 247 trades, −5,9 €/jour), or 2 sens −8 808 € (1 864 trades, −8,7 €/jour). Pas mieux que le hasard (p = 0,83 sur le DAX, 0,95 sur l'or).
- Rien intégré au bot. Idée retenue à part : un message « bot vivant » (heartbeat), pour savoir si le PC ou MT5 s'est arrêté.
- Trades : robuste/tradia_tous_trades.csv, et robuste/tradia_trades_oct2026.csv (DAX + or, depuis le 05/10).

## 03/11/2026 vers 14h25 (Paris) : test du dépôt iannini-DayTrade (iannini25)
- Le dépôt : application web brésilienne (React + Node) pour le Mini Índice WIN, avec signaux et code NTSL pour le logiciel Profit. Règle : achat si MM9 > MM21 ET clôture au-dessus du VWAP de la séance, vente dans le cas inverse. Stop 150 pts, objectif 250 pts, break-even à +100 pts, de 9h15 à 17h00 (heure de Brasília). Pas de résultats publiés.
- Rejoué sur nos 7 marchés M15, 2022-2026, 100 €/trade (robuste/iannini_test.py), 4 variantes : fidèle (stop/objectif en % du prix), + filtre RSI, stop en ATR avec break-even, stop 0,3 ATR / objectif 0,45 ATR sans break-even. TOUT perd. Fidèle : DAX −21 532 € (8,8 trades/jour), or −86 041 €. Meilleure variante : DAX −1 449 €, or −1 879 €.
- ⚠️ Bug trouvé et corrigé pendant ce test : après une sortie au stop ou à l'objectif EN COURS de bougie, le script ré-entrait à l'ouverture de cette même bougie, donc à un prix déjà passé. Avec ce bug, l'or donnait un faux +31 180 €. Corrigé dans iannini_test.py et tradia_test.py. À vérifier un jour dans nos anciens scripts de recherche à ré-entrée multiple dans la journée (les lignes de la v1.06 ne font qu'un trade par setup et par jour).
- Rien intégré. Trades : robuste/iannini_tous_trades.csv et robuste/iannini_trades_oct2026.csv.

## 03/11/2026 vers 14h35 (Paris) : test du skill Jakeschincariol/day-trader-skill
- Le dépôt : 11 skills Claude pour le day trading d'actions US (scanner, news, entrée, sortie, « Time Machine », risque, taille, ordres via Alpaca en papier, alertes, résultats d'entreprises, trades du Congrès). Données Yahoo gratuites. Une seule stratégie testable : la cassure du range d'ouverture de 15 min (ORB). Stop au milieu du range, objectif 2R par défaut (1R dans leur exemple), sortie à 15:55 New York, achat seulement.
- Rejoué sur 13 marchés M15 (4 indices dont le DAX + 9 actions US), 2022-2026, 100 €/trade, 4 variantes (achat ou 2 sens, 1R ou 2R), script robuste/dts_orb_test.py. Version fidèle (achat, 2R) : 8 942 trades, 3 643 gagnants, 5 299 perdants, −75 354 € (−61,9 €/jour, environ 7 trades/jour au total). DAX seul : −6 076 €. Sur 52 combinaisons, quelques-unes gagnent sur P et L (TSLA 2 sens 2R, AMD 1R), mais pas leurs réglages voisins : c'est ce que le hasard donne sur 52 essais.
- Rappel utile : notre ligne « DAX 1re bougie » est un ORB, et elle ne gagne qu'avec le filtre de tendance 20 jours et les 2 correctifs. Sans eux, l'ORB brut perd, ce qui est cohérent.
- Leur « Time Machine » (rejouer un setup sur son passé avant d'entrer) et le contrôle PASS/BLOCK existent déjà chez nous (tests contre le hasard, limites du robot). Rien intégré.
- ⚠️ NFLX : les pertes géantes viennent peut-être de mon ajustement de la division par 10, à vérifier avant tout test sur NFLX.
- Trades : robuste/dts_orb_tous_trades.csv, robuste/dts_orb_trades_oct2026.csv.

## 03/11/2026 vers 14h40 (Paris) : test de alpacahq/Momentum-Trading-Example
- Le dépôt : un exemple de code d'Alpaca (un seul script) pour petites actions US de 2 à 13 $ en bougies de 1 min. Achat entre 15 et 60 min après l'ouverture si : hausse de plus de 4 % depuis la veille, prix au-dessus du plus haut des 15 premières minutes, MACD positif et en hausse. Stop au dernier creux, objectif 3R, sortie si le MACD se retourne.
- Rejoué en M15 sur 13 marchés (robuste/alpaca_momentum_test.py), achat seulement, 100 €/trade. Fidèle (seuil 4 %) : 275 trades en presque 5 ans, 111 gagnants, 164 perdants, +76 € (P −250 €, L +326 €). Avec un seuil adapté (0,5 × ATR jour) : 1 692 trades, −1 803 €. Autour de zéro : aucun avantage. Le vrai terrain de cette stratégie (petites actions en 1 min) n'existe pas chez notre broker.
- À noter : AMD sort positif ici aussi (fidèle +505 € sur P, +154 € sur L ; p = 0,09), comme dans le test ORB. Ça fait deux fois. Ce n'est pas une preuve : AMD reste en observation, rien n'est intégré.
- Trades : robuste/alpaca_tous_trades.csv.

## 03/11/2026 vers 14h50 (Paris) : test de gianlucadetommaso/volatile
- Le dépôt : outil Python (TensorFlow, Yahoo) abandonné depuis mai 2023. Chaque jour, il trace une tendance (polynôme de degré 2 sur un an de prix) et note chaque action de « très sous la tendance » à « très au-dessus ». 4 bots d'exemple achètent selon la note et revendent à +3/−10 %, +10/−3 %, +10/−20 % ou +20/−10 %. Ce sont des positions de plusieurs semaines : PAS du day trading.
- Rejoué en journalier (robuste/volatile_test.py, tendance par moindres carrés à la place du modèle bayésien), 21 marchés, 100 € de risque par trade, financement de nuit compté. 2013-2021 : les 4 bots perdent (−197 €, −4 644 €, −1 663 €, −2 443 €). 2022-2026 : ils gagnent (+592 € à +5 357 €), mais des achats AU HASARD avec les mêmes sorties font autant par trade (p = 0,17 à 0,83). Le gain vient de la hausse des marchés (actions US, or), pas du modèle.
- Rien intégré. Trades : robuste/volatile_tous_trades.csv.

## 03/11/2026 vers 14h55 (Paris) : ⚠️ dépôt Blofin-Day-Trading/blofin-day-trading-bot = PIÈGE (logiciel malveillant)
- Le code n'a pas été exécuté. Lu seulement, puis supprimé de la machine de test.
- Le fichier caché .vscode/tasks.json se lance tout seul à l'ouverture du dossier dans VS Code ("runOn": "folderOpen", "task.allowAutomaticTasks": "on"). Il lit une adresse cachée en base64 dans .env.example (http://212.193.3.61:4873/, un serveur npm privé sur une simple adresse IP) et y installe le paquet « ioredis-om-typed », inconnu du registre officiel. C'est la méthode classique des voleurs de mots de passe et de portefeuilles crypto.
- Le README (4 langues, belles images de gains) sert d'appât. Aucune stratégie à tester.
- Règle : avant d'ouvrir un dépôt de « bot de trading » inconnu, vérifier .vscode/, package.json, les scripts d'installation et toute chaîne en base64.

## 03/11/2026 vers 14h45 (Paris) : test de censix/INTRADAY-PartAB → v1.07 (cassure de canal sur l'or)
- Le dépôt : chaîne d'exécution en R pour Interactive Brokers (2015), propre (aucun piège). 2 stratégies d'exemple prévues en bougies de 30-60 s : Bollinger (achat sous la bande basse, sortie à la moyenne) et cassure de canal (achat au-dessus du plus haut des N bougies, sortie au retour à la moyenne N ; N = 20 ou 200). Pas de stop, tout fermé le soir.
- Rejoué en M15 sur 7 marchés (robuste/censix_test.py). Bollinger : perd partout. Cassure N = 20 : perd partout. Cassure N = 200 : gagne seulement sur l'OR.
- Or, cassure 200 bougies, stop 0,6 ATR jour (100 € au stop) : 609 trades sur 2022-2026, +1 201 € sur 2022-24, +2 269 € sur 2025-26, pire baisse −1 193 €, p = 0,008 contre le hasard. 12 réglages voisins sur 12 (N 150-300, stop 0,45-0,75 ATR) gagnants sur 2022-25 ET sur la dernière année, encore gagnants avec frais doublés, à l'achat comme à la vente. Argent, DAX, indices US, forex : ne marche pas (ligne propre à l'or, à confirmer en démo).
- Corrélation journalière avec la v1.06 : 0,06 (avec « or tendance » : −0,04). Les deux lignes tradent ensemble 14 jours sur 120 seulement.
- **v1.07 = v1.06 + ligne ORBREAK** (sans_yen/DayTrader_MT5_v107.mq5), magics 26110700 à 26110704 (ORBREAK = 26110704). Réglages : InpOrBreakN = 200, InpOrBreakStopATR = 0,6. Entrées 10h00-22h45 serveur, tout fermé à 23h00 serveur. Compilée et mise en démo le 03/11 vers 15h (voir plus bas).
- Dernière année, à 1 000 €/trade : v1.07 +96 870 € (v1.06 : +86 510 €), soit +10 360 €. 652 trades (2,5 par jour), 288 gagnants, 362 perdants, 9 mois gagnants sur 12, pire mois −15 740 € (v1.06 : −14 310 €). ORBREAK seule : 124 trades, 62 gagnants, 61 perdants, +10 360 €, pire mois −2 320 €. Cette année, ses ventes ont gagné (+12 290 €) et ses achats un peu perdu (−1 930 €).
- Journal mensuel mis à jour (onglets v1.07 et « Or cassure de canal seule ») et republié. Sauvegarde : robuste/carnet_1an_avant_v107.json. Bandeau corrigé : la démo tourne en v1.06.

## 03/11/2026 vers 15h (Paris) : la v1.07 prend la main sur la démo (demande explicite d'aurele : « la V7 en démo et sur le dépôt GitHub »)
- Vérifié avant : aucune position ouverte sur les 4 lignes de la v1.06 (etat.txt à 14h54), entrées autorisées.
- DayTrader_MT5_v107.mq5 déposé dans MQL5\Experts et compilé dans MetaEditor : 0 erreur, 0 avertissement.
- Script MQL5\Scripts\PasseV107.mq5 compilé (0 erreur, 0 avertissement) avec le modèle Scripts\LanceDayTrader107.tpl. Il refuse un compte réel, refuse s'il reste une position ou un ordre des magics 26110300-302, 26110600-603 ou 26110700-704, remplace la v1.06 sur le graphique DE40 M15 et écrit le résultat dans MQL5\Files\passe_v107.txt.
- Réglages repris de la démo v1.06 : 200 € à l'achat et à la vente (InpRiskMoney=200, InpShortFactor=1.0), perte max 600 €/jour, coupe-circuit −20 %. TradeNotifier n'est pas touché.
- 15h07 (Paris) : aurele a lancé PasseV107 dans MT5 (Claude a seulement le droit de regarder MT5). Rapport passe_v107.txt : compte DEMO MetaQuotes-Demo, 0 position et 0 ordre ouverts, bouton Algo Trading ACTIVÉ, « OK : DayTrader_MT5_v107 (re)lancé sur DE40 » à la place de DayTrader_MT5_v106. TradeNotifier toujours sur EURUSD H1.
- etat.txt mis à jour par la v1.07 à 15h07 : capital 100 000, entrées autorisées, 5 lignes listées (DAX1B, ORIB, ORTEND, DAXST, ORBREAK), aucune position.
- À savoir : le graphique DE40 est en H1 (depuis le 03/11 vers 12h32). Sans effet sur les trades : le robot lit toujours les bougies M15 (et D1) en interne.
- Le suivi des trades réels (suivi_demo/journal_demo.py) compte déjà les magics de la v1.07.
- Fichiers : sans_yen/deploy107/ (robot, script, modèle de graphique).

## 03/11/2026 vers 16h30 (Paris) : audit de Melvin + Claude → v1.08 (branche `ameliorations`, NON déployée)
Aucun changement de stratégie. Deux correctifs de sécurité, un rapport de suivi. La démo v1.07 n'est pas touchée.
- **I. Protections sauvegardées.** Avant : le capital du début de journée, le plus haut du capital et le coupe-circuit n'existaient qu'en mémoire. Chaque redémarrage du robot ou de MT5 (3 changements de version le 03/11) remettait la perte max de 600 €/jour et le −20 % à zéro. v1.08 : sauvegarde dans les variables globales du terminal MT5 (une clé par compte et par version, rien dans le dépôt), relues au démarrage. Le coupe-circuit reste actif après un redémarrage ; `InpResetGuards = true` le remet à zéro (une fois, puis remettre `false`). Aurel corrige aussi ce bug de son côté : comparer les deux avant de choisir.
- **J. Fermeture de l'or.** Constat dans les données M15 (`robuste/ecart_horaire.py`) : depuis fin mars 2026, la dernière bougie de l'or est 22h45 tous les jours, le marché ferme donc à 23h00 serveur. La v1.07 ferme ORIB, ORTEND et ORBREAK à 23h00 : trop tard. Très probablement, une position or encore ouverte le soir passe la nuit et n'est fermée qu'à l'ouverture du lendemain (risque de nuit jamais testé). Le backtest, lui, sort au dernier prix du jour. v1.08 : or fermé à 22h50, ou 10 min avant la fin de séance annoncée par le broker si elle est plus tôt ; dernière entrée ORBREAK inchangée (bougie de 22h30). À vérifier dans le journal.csv de la démo : des trades or fermés le lendemain vers 1h serveur confirmeraient le bug.
- **Décalage horaire : le README avait le diagnostic à l'envers.** Le serveur MetaQuotes-Demo suit l'heure d'été européenne (serveur = Paris + 1 h toute l'année). Le DAX ouvre à 10h00 serveur même pendant les semaines décalées : il est bien calé. Ce sont les heures de New York qui glissent (ouverture US à 15h30 serveur au lieu de 16h30 ; amplitude S&P 500 de 17,2 points à 15h30 contre 13,0 à 16h30 pendant ces semaines). Testé : recaler l'Initial Balance de l'or sur New York pendant ces semaines (100 €/trade, depuis 08/2022) donne −142 € sur 42 trades, contre +839 € sur 38 trades avec les heures fixes. Rien de prouvé dans un sens ni dans l'autre : **non retenu**, les heures d'entrée restent celles de la v1.07.
- Magics 26110800 à 26110804. Fichier `sans_yen/DayTrader_MT5_v108.mq5`. **Pas encore compilé** (pas de MetaEditor côté Claude) : à compiler dans MetaEditor avant tout essai. Déploiement : décision d'Aurel et Melvin.
- **Rapport démo contre backtest** : `suivi_demo/demo_vs_test.py`. Lit le journal.csv du robot, regroupe les demi-sorties ORIB, ramène tout à 100 €/trade, et compare chaque semaine (fourchette des 8 semaines sur 10 du backtest v1.07 : −468 € à +1 105 €, moyenne +183 €/semaine, 12,3 trades/semaine) et chaque ligne (verdict seulement à partir de 30 trades). Il signale aussi les positions qui ont passé la nuit. Vérifié sur un faux journal construit avec 4 semaines du backtest : totaux exacts.
- Règle proposée : ne plus changer la stratégie de la démo pendant 8 à 12 semaines (environ 100 à 150 trades) pour que la démo mesure enfin quelque chose. Seuls les correctifs de sécurité (comme la v1.08) peuvent passer avant.
