# Bot trading (MetaTrader 5)

Projet d'aurele : un robot de trading qui surveille les marchés, envoie une notification à chaque trade et passe ses trades tout seul, comme un day trader (achat et vente, chaque jour). Tout est en MQL5 pour MetaTrader 5, et les tests sont faits en Python sur des données exportées de MT5.

> ⚠️ Rien ici n'est un conseil financier. Tous les résultats sont des **backtests** (tests sur le passé). Le robot tourne **uniquement sur un compte démo**. Il refuse de tourner sur un compte réel tant que `InpAllowRealAccount = false`.

## 1. Où on en est (03/11/2026)

- **Robot en démo : `sans_yen/DayTrader_MT5_v107.mq5` (v1.07)** sur DE40 (DAX) en 15 minutes, en démo depuis le 03/11/2026 à 15h07 (heure de Paris), à la place de la v1.06. Magic numbers 26110700 à 26110704.
- Réglages de la démo : 200 € risqués par trade à l'achat et à la vente, perte max de 600 € par jour, coupe-circuit à −20 %.
- **Prête sur la branche `ameliorations`, pas déployée : `sans_yen/DayTrader_MT5_v108.mq5` (v1.08)**. Même stratégie que la v1.07, deux correctifs de sécurité : protections sauvegardées (elles survivent à un redémarrage) et fermeture de l'or à 22h50 au lieu de 23h00 (le marché de l'or ferme à 23h00 serveur depuis fin mars 2026). Magic numbers 26110800 à 26110804. Détail dans `JOURNAL_DES_CHANGEMENTS.md`.
- **Suivi de la démo : `suivi_demo/demo_vs_test.py`** compare le `journal.csv` du robot au backtest, semaine par semaine et ligne par ligne.
- **Notifications : `notifications/TradeNotifier.mq5`** (sur un graphique EURUSD) envoie une alerte à chaque trade et un récap à 22h. Le robot lui passe les infos par des fichiers « outbox » (format dans `sans_yen/FORMAT_OUTBOX.md`).
- Pas de paire en yen (choix d'aurele).
- **Règle : on ne touche pas à la démo en cours.** Les améliorations se préparent à côté, se notent dans `JOURNAL_DES_CHANGEMENTS.md`, et ne remplacent la démo qu'avec l'accord d'aurele.

## 2. Ce que fait la v1.07

Une seule stratégie intraday qui combine plusieurs « lignes » :

| Ligne | Marché | Idée |
|---|---|---|
| DAX 1re bougie | DE40 M15 | cassure de la 1re bougie de 15 min de l'ouverture, dans le sens de la tendance |
| DAX Supertrend | DE40 M15 | Supertrend (multiplicateur 4, stop 1,5 ATR) |
| Or Initial Balance | XAUUSD | cassure de la 1re heure de séance, demi-sortie à +0,5 R |
| Or tendance | XAUUSD | suivi de tendance, coupé quand la volatilité est agitée |
| Or cassure de canal (nouvelle en v1.07) | XAUUSD M15 | achat si la clôture passe au-dessus du plus haut des 200 dernières bougies de 15 min, vente si elle passe sous le plus bas ; stop 0,6 ATR jour, sortie au retour sur la moyenne 200 bougies, tout fermé à 23h serveur |

Filtres communs : filtre de tendance (achat seulement si la clôture d'hier est au-dessus de la moyenne 20 jours, vente seulement en dessous), pas de trade le lundi sur la 1re bougie DAX, pas de trade si la 1re bougie est trop grosse (> 0,19 × ATR jour), garde-fou si l'écart achat/vente dépasse 2 fois sa médiane, alarme de dégradation sur les 60 derniers trades (elle prévient, elle n'arrête rien).

## 3. Résultats des tests (backtest)

Sur la dernière année, en risquant 1 000 € par trade (diviser par 10 pour 100 €) :

| Version | Résultat | Pire mois | Remarque |
|---|---|---|---|
| v1.03 | +68 454 € (coûts ×2) | | 3 correctifs sur l'or |
| v1.04 | +78 950 € | | + garde-fou écart + alarme |
| v1.05 | +102 010 € | −10 150 € | + Supertrend DAX, 2,6 trades/jour |
| v1.06 | +86 510 € | −14 310 € | zone de bruit DAX retirée après audit (avantage non prouvé) |
| **v1.07** | **+96 870 €** | −15 740 € | + cassure de canal sur l'or : 652 trades (2,5 par jour), 288 gagnants, 362 perdants, 9 mois gagnants sur 12 |

À savoir franchement :
- La cassure de canal sur l'or (idée du dépôt censix/INTRADAY-PartAB) bat le hasard (p = 0,008) et tient sur 12 réglages voisins sur 12, frais doublés compris, mais elle ne marche que sur l'or : à confirmer en démo.
- Le Supertrend DAX tient sur 9 réglages voisins sur 9, mais il perd quand on le copie sur les autres indices européens. Il est peut-être chanceux : la démo doit le confirmer.
- Les lignes ont été choisies en regardant 2025-2026 : il y a un biais de sélection. Seule la démo dira la vérité.
- Ce qui a été testé et **rejeté** (ça perd ou ça ne bat pas le hasard) : IA « chef d'orchestre » qui choisit la stratégie, bot « Apprenti » (mémoire de setups), laboratoire de règles inventées au hasard, forex intraday (mangé par les coûts), bot sur 26 marchés avec une stratégie par marché, filtre des annonces US, filtre COT sur l'or, coupe-circuit après 2 pertes, momentum de fin de séance.

Le détail de chaque test et de chaque changement est dans `JOURNAL_DES_CHANGEMENTS.md`. Les journaux hebdo et mensuel des trades sont dans `robuste/journal_hebdo.html` et `robuste/journal_mensuel.html` (à ouvrir dans un navigateur).

## 4. Les dossiers

| Dossier / fichier | Contenu |
|---|---|
| `sans_yen/` | **Le robot actuel** : DayTrader v1.01 à v1.07, scripts de recherche day trading, scripts d'export M5/M15, analyse des pertes |
| `sans_yen/deploy106/`, `sans_yen/deploy107/` | ce qui a servi à passer la démo en v1.06 puis en v1.07 (script + modèle de graphique) |
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
2. Fichier → Ouvrir le dossier des données → `MQL5/Experts` : copie `sans_yen/DayTrader_MT5_v107.mq5` (et `notifications/TradeNotifier.mq5` si tu veux les alertes).
3. Ouvre MetaEditor (F4), ouvre le fichier, **Compiler** (F7) : 0 erreur attendu. Piège : si un ancien onglet du même fichier est ouvert dans MetaEditor, ferme-le avant de remplacer le fichier, sinon il réécrit l'ancienne version.
4. Glisse DayTrader sur un graphique **DE40 M15** (le nom du symbole peut changer selon le broker ; le robot trade aussi l'or XAUUSD depuis ce graphique), TradeNotifier sur n'importe quel graphique, et active **Algo Trading**.
5. Les heures sont en heure serveur MetaQuotes-Demo (DAX à 10:00 serveur). Le serveur suit l'heure d'été **européenne** (serveur = Paris + 1 h toute l'année) : le DAX est bien calé toute l'année. Pendant les semaines où seuls les États-Unis ont changé d'heure (mi-mars → fin mars, fin octobre → début novembre), ce sont les heures de New York qui glissent d'1 h (ouverture US à 15h30 serveur au lieu de 16h30). Recaler l'Initial Balance de l'or sur ces semaines n'a rien prouvé (40 trades) : non fait. Preuves : `robuste/ecart_horaire.py` (Melvin).

## 6. Refaire les tests

Suivi de la démo contre le backtest : `python suivi_demo/demo_vs_test.py CHEMIN\journal.csv --html rapport.html` (le fichier est dans `MQL5\Files\DayTrader\` du PC). Rapport par semaine et par ligne, à 100 €/trade, et liste des positions qui ont passé la nuit (Melvin).

Python 3 avec `pandas` et `numpy` (et `matplotlib` pour les graphiques). Les scripts se lancent depuis leur dossier, par exemple `python robuste/boucle.py`. Format des résultats demandé par aurele : 100 € par trade, résultats par semaine et par jour, avec le nombre de trades, de gagnants, de perdants et le gain ou la perte de chaque trade.

## 7. Travailler à deux

- Ne mets jamais d'identifiant, de mot de passe, de numéro de compte, de MetaQuotes ID ni de token Telegram dans ce dépôt.
- Une amélioration = une branche + une pull request, avec le résultat du test (sur des mois non vus et contre le hasard) et une ligne dans `JOURNAL_DES_CHANGEMENTS.md`.
- Le fichier `CLAUDE.md` donne le contexte à Claude : ouvre ce dépôt avec Claude Code et il saura où on en est.
