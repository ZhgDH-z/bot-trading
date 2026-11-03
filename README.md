# Bot trading (MetaTrader 5)

Projet d'aurele : un robot de trading qui surveille les marchés, envoie une notification à chaque trade et passe ses trades tout seul, comme un day trader (achat et vente, chaque jour). Tout est en MQL5 pour MetaTrader 5, et les tests sont faits en Python sur des données exportées de MT5.

> ⚠️ Rien ici n'est un conseil financier. Tous les résultats sont des **backtests** (tests sur le passé). Le robot tourne **uniquement sur un compte démo**. Il refuse de tourner sur un compte réel tant que `InpAllowRealAccount = false`.

## 1. Où on en est (03/11/2026)

- **Robot en démo : `sans_yen/DayTrader_MT5_v106.mq5` (v1.06)** sur DE40 (DAX) en 15 minutes, depuis le 03/11/2026 vers 2h47 (heure de Paris). Magic numbers 26110600 à 26110603.
- Réglages de la démo : 200 € risqués par trade à l'achat et à la vente, perte max de 600 € par jour, coupe-circuit à −20 %.
- **Notifications : `notifications/TradeNotifier.mq5`** (sur un graphique EURUSD) envoie une alerte à chaque trade et un récap à 22h. Le robot lui passe les infos par des fichiers « outbox » (format dans `sans_yen/FORMAT_OUTBOX.md`).
- Pas de paire en yen (choix d'aurele).
- **Règle : on ne touche pas à la démo en cours.** Les améliorations se préparent à côté, se notent dans `JOURNAL_DES_CHANGEMENTS.md`, et ne remplacent la démo qu'avec l'accord d'aurele.

## 2. Ce que fait la v1.06

Une seule stratégie intraday qui combine plusieurs « lignes » :

| Ligne | Marché | Idée |
|---|---|---|
| DAX 1re bougie | DE40 M15 | cassure de la 1re bougie de 15 min de l'ouverture, dans le sens de la tendance |
| DAX Supertrend | DE40 M15 | Supertrend (multiplicateur 4, stop 1,5 ATR) |
| Or Initial Balance | XAUUSD | cassure de la 1re heure de séance, demi-sortie à +0,5 R |
| Or tendance | XAUUSD | suivi de tendance, coupé quand la volatilité est agitée |

Filtres communs : filtre de tendance (achat seulement si la clôture d'hier est au-dessus de la moyenne 20 jours, vente seulement en dessous), pas de trade le lundi sur la 1re bougie DAX, pas de trade si la 1re bougie est trop grosse (> 0,19 × ATR jour), garde-fou si l'écart achat/vente dépasse 2 fois sa médiane, alarme de dégradation sur les 60 derniers trades (elle prévient, elle n'arrête rien).

## 3. Résultats des tests (backtest)

Sur la dernière année, en risquant 1 000 € par trade (diviser par 10 pour 100 €) :

| Version | Résultat | Pire mois | Remarque |
|---|---|---|---|
| v1.03 | +68 454 € (coûts ×2) | | 3 correctifs sur l'or |
| v1.04 | +78 950 € | | + garde-fou écart + alarme |
| v1.05 | +102 010 € | −10 150 € | + Supertrend DAX, 2,6 trades/jour |
| **v1.06** | **+86 510 €** | −14 310 € | zone de bruit DAX retirée après audit (avantage non prouvé) |

À savoir franchement :
- Le Supertrend DAX tient sur 9 réglages voisins sur 9, mais il perd quand on le copie sur les autres indices européens. Il est peut-être chanceux : la démo doit le confirmer.
- Les lignes ont été choisies en regardant 2025-2026 : il y a un biais de sélection. Seule la démo dira la vérité.
- Ce qui a été testé et **rejeté** (ça perd ou ça ne bat pas le hasard) : IA « chef d'orchestre » qui choisit la stratégie, bot « Apprenti » (mémoire de setups), laboratoire de règles inventées au hasard, forex intraday (mangé par les coûts), bot sur 26 marchés avec une stratégie par marché, filtre des annonces US, filtre COT sur l'or, coupe-circuit après 2 pertes, momentum de fin de séance.

Le détail de chaque test et de chaque changement est dans `JOURNAL_DES_CHANGEMENTS.md`. Les journaux hebdo et mensuel des trades sont dans `robuste/journal_hebdo.html` et `robuste/journal_mensuel.html` (à ouvrir dans un navigateur).

## 4. Les dossiers

| Dossier / fichier | Contenu |
|---|---|
| `sans_yen/` | **Le robot actuel** : DayTrader v1.01 à v1.06, scripts de recherche day trading, scripts d'export M5/M15, analyse des pertes |
| `sans_yen/deploy106/` | ce qui a servi à passer la démo en v1.06 (script + modèle de graphique) |
| `notifications/` | TradeNotifier (alertes MT5 / Telegram) et son guide |
| `robuste/` | tests de robustesse : diagnostic, boucle de correctifs, Apprenti, labo, Supertrend, tous les marchés, carnets de trades |
| `or/` | recherche sur l'or (sessions, version évolutive) |
| `data/`, `data_export/`, `data_m15/`, `data_m15b/` | bougies historiques (H1, D1, M15) exportées de MT5 ou de sources publiques |
| `results/` | résultats des premiers tests (stratégie de la vidéo, MultiBot, indices US) |
| `MA_Cross_USDJPY.mq5`, `MultiBot_MT5.mq5` | anciens robots (stratégie de la vidéo Impact Trading, puis multi-marchés). Voir `README_VIDEO_ORIGINE.md` |
| `pc/Reveil_MT5_bot.xml` | tâche Windows qui sort le PC de veille et lance MT5 du lundi au vendredi à 8h15 |

Les fichiers `.pkl` sont des résultats intermédiaires Python (pandas). Ne charge que ceux de ce dépôt : un `.pkl` peut exécuter du code à l'ouverture.

## 5. Installer le robot sur ton MT5 (compte démo)

1. Ouvre MT5 sur un **compte démo**.
2. Fichier → Ouvrir le dossier des données → `MQL5/Experts` : copie `sans_yen/DayTrader_MT5_v106.mq5` (et `notifications/TradeNotifier.mq5` si tu veux les alertes).
3. Ouvre MetaEditor (F4), ouvre le fichier, **Compiler** (F7) : 0 erreur attendu. Piège : si un ancien onglet du même fichier est ouvert dans MetaEditor, ferme-le avant de remplacer le fichier, sinon il réécrit l'ancienne version.
4. Glisse DayTrader sur un graphique **DE40 M15** (le nom du symbole peut changer selon le broker), TradeNotifier sur n'importe quel graphique, et active **Algo Trading**.
5. Les heures sont en heure serveur MetaQuotes-Demo (DAX à 10:00 serveur). Limite connue : quand les heures d'été US et Europe sont décalées (mi-mars → fin mars, dernière semaine d'octobre), le DAX est mal calé. À corriger avant le 8 mars 2027.

## 6. Refaire les tests

Python 3 avec `pandas` et `numpy` (et `matplotlib` pour les graphiques). Les scripts se lancent depuis leur dossier, par exemple `python robuste/boucle.py`. Format des résultats demandé par aurele : 100 € par trade, résultats par semaine et par jour, avec le nombre de trades, de gagnants, de perdants et le gain ou la perte de chaque trade.

## 7. Travailler à deux

- Ne mets jamais d'identifiant, de mot de passe, de numéro de compte, de MetaQuotes ID ni de token Telegram dans ce dépôt.
- Une amélioration = une branche + une pull request, avec le résultat du test (sur des mois non vus et contre le hasard) et une ligne dans `JOURNAL_DES_CHANGEMENTS.md`.
- Le fichier `CLAUDE.md` donne le contexte à Claude : ouvre ce dépôt avec Claude Code et il saura où on en est.
