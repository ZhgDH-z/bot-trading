# Bot sans yen : ce que j'ai testé et ce que ça donne (02/11/2026)

Données : l'historique H1 de ton MT5 (MetaQuotes-Demo), de 2012 à octobre 2026. Aucune paire en yen.

## La méthode (pour ne pas se mentir)

1. **Conception, 2012-2017** : je teste chaque stratégie sur chaque marché.
2. **Validation, 2018-2021** : je garde seulement les couples qui gagnent sur les DEUX périodes. Cette règle est fixée d'avance.
3. **Test final, mars 2022 → octobre 2026** : je ne l'ai jamais regardé pour choisir. C'est le chiffre qui compte.

Tous les réglages sont des valeurs classiques publiées. Je n'ai rien optimisé. Les coûts comptés sont le spread (plus large que celui de ton broker), le glissement et le financement de nuit.

## Les 8 familles testées (sur 13 marchés sans yen)

| Stratégie | Idée | Verdict |
|---|---|---|
| RSI(2) journalier (Connors) | acheter un repli dans une tendance haussière | marche sur les **indices US**, pas sur le forex |
| RSI(2) élargi (seuil 25) | pareil, plus de trades | marche sur les indices US |
| ASIE | retour à la moyenne en H1 pendant la nuit asiatique | **marche sur EURCHF**, perd ailleurs |
| REPLI | acheter une baisse pendant la séance US, revendre le soir | à peu près 0 |
| Donchian 20 jours | suivre la tendance | perd partout, sauf peut-être l'argent |
| Nuit sur indices | acheter le soir, revendre le matin | perd après coûts |
| Momentum intraday (Gao et al. 2018) | la 1re heure prédit la dernière | perd : le spread mange tout |
| Tournant du mois | acheter les indices fin de mois | petit, pas retenu en 2012-17 |

## Le résultat sur le test final (2022-2026)

À 0,5 % de risque par trade sur le forex et les métaux, et 1 % sur les indices :

| Ligne | Trades | R moyen | Au hasard (même marché, même durée) |
|---|---|---|---|
| **EURCHF : ASIE** | 113 | **+0,19** | −0,16 : le hasard ne fait jamais mieux |
| **US500 : DIP** | 90 | **+0,10** | +0,02 : le hasard fait mieux 10 % du temps |
| USTECH100M : DIP | 81 | +0,06 | +0,03 |
| US30 : DIP | 89 | +0,04 | +0,00 |
| US30 : REPLI | 254 | +0,01 | −0,01 |
| XAGUSD : DONCH | 54 | +0,02 | +0,04 : le hasard fait mieux |
| DE40 : DIP | 94 | −0,00 | +0,02 : le hasard fait mieux |

**Le bot complet sans yen :**

- **+6,7 % par an**, pire baisse **−12 %** ;
- 68 % de mois positifs, pire mois −6 % ;
- toutes les années positives : 2022 +1,7 %, 2023 +4,7 %, 2024 +10,3 %, 2025 +3,7 %, 2026 +11,1 % ;
- octobre 2026 : **+0,6 %**, alors que l'ancien bot y perdait environ −7 % à cause du yen.

## Ce qu'il faut dire franchement

- **Le rendement baisse fortement.** L'ancien bot (yen + indices) faisait +19 % par an sur la même période. Le nouveau fait +7 %. La différence, c'était la tendance du yen, et cette tendance s'est retournée en octobre.
- **Un trade par jour sans yen, ça n'existe pas avec un vrai avantage.** Le bot ouvre environ **3 trades par semaine** (un trade 43 % des jours), mais il est **en position 88 % des jours**.
- J'ai testé une version « fréquente » qui ajoute des lignes proches de zéro. Elle trade 64 % des jours et fait +9 % par an, mais sa pire baisse passe à **−22 %** et 2023 fait à elle seule +24 %, ce qui ressemble à de la chance. Trader plus souvent, c'est surtout payer plus de spread.
- Les 2 vraies pépites sont **EURCHF la nuit** et **le S&P 500 sur repli**. 3 lignes (argent, DAX, US30 REPLI) ne battent pas le hasard sur le test final. Je les ai gardées parce que c'était la règle fixée d'avance : les retirer maintenant, ce serait choisir en connaissant le résultat.

## Le bot : `SansYen_MT5.mq5`

- **Config par défaut** : `EURCHF:ASIE,XAGUSD:DONCH,US30:REPLI,US500:DIP,US30:DIP,USTECH100M:DIP,DE40:DIP`.
- **Magic numbers** : 26110200 à 26110206, un par ligne dans l'ordre de la config.
- **Une paire en yen dans la config est refusée automatiquement.**
- **Suivi** :
  - une notification sur ton téléphone à **chaque ouverture et chaque fermeture**, avec gagnant/perdant, le montant et le capital ;
  - un journal `MQL5\Files\SansYen\journal.csv` ;
  - un état `MQL5\Files\SansYen\etat.txt` mis à jour toutes les 5 minutes.
- **Notifications** : `TradeNotifier` (déjà installé sur ton PC) envoie les alertes de trades. Pour éviter les doublons, `InpPush` est donc sur `false` par défaut. Si tu veux plutôt utiliser celles de SansYen, mets `InpPush = true`. Dans ce cas : dans l'appli MetaTrader 5 du téléphone, va dans Messages et copie ton MetaQuotes ID. Ensuite, sur le PC : Outils → Options → Notifications, coche « Activer les notifications push » et colle l'ID.
- **Protections** (comme avant) : 10 positions maximum, arrêt des entrées après −3 % sur la journée, coupe-circuit à −20 % depuis le plus haut, filtre de spread, blocage sur compte réel.

Scripts : `recherche.py`, `recherche2.py`, `portefeuille.py`. Trades du test final : `trades_test_final_qualite.csv`.
