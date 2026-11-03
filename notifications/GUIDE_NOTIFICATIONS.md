# TradeNotifier : une notification à chaque trade

`TradeNotifier.mq5` est un robot **compagnon**. Il ne trade pas : il lit l'historique du compte et t'envoie un message à chaque ouverture et à chaque fermeture de trade. Il marche avec le MultiBot, avec la future stratégie sans yen et même avec tes trades manuels, sans toucher au code de la stratégie.

## Ce que tu reçois

**À l'ouverture d'un trade :**
```
▶ TRADE OUVERT : ACHAT GBPUSD
0.12 lot a 1.27345
Stop 1.26800 | Objectif aucun (stop suiveur)
Risque 50.00 EUR (0.50 % du capital)
Strategie MM | 02/11 14h05 (Paris)
```

**À la fermeture d'un trade, gagnant ou perdant :**
```
✅ TRADE GAGNANT +23.40 EUR (+0.23 %)
ACHAT GBPUSD 0.12 lot : 1.27345 -> 1.27755 (+41.0 pips)
Sortie : stop touche | duree 6h12
Strategie MM | 02/11 20h17 (Paris)
Aujourd'hui : 3 trade(s), 2 gagnant(s), +45.10 EUR
Solde : 10045.10 EUR
```

**Chaque soir à 22h30 (heure de Paris), du lundi au vendredi, un récap avec :**
- l'état du robot : bouton Algo Trading activé ou non, connexion au broker ;
- le solde, le capital et le gain ou la perte latente ;
- le résultat du jour, de la semaine et depuis le lancement de la démo, avec le % de trades gagnants ;
- la baisse depuis le plus haut ;
- les positions ouvertes ;
- l'état du marché pour chaque symbole : prix, variation du jour, tendance (au-dessus ou en dessous de la MM200 journalière), journée calme, normale ou agitée, et un signal « repli à l'achat » quand le RSI(2) passe sous 10.

Le vendredi, le récap ajoute le bilan de la semaine.

**Alertes de surveillance :**
- le bouton Algo Trading est coupé, donc le robot ne peut plus trader ;
- le capital perd plus de 2 % dans la journée ;
- la connexion au broker revient après une coupure d'au moins une minute (les trades fermés pendant la coupure sont envoyés juste après) ;
- aucun trade depuis 3 jours, signalé dans le récap.

Chaque trade est aussi écrit dans `MQL5\Files\TradeNotifier_journal.csv`, que tu peux ouvrir dans Excel.

## Quel canal choisir

| Canal | Ce qu'il faut faire | Avantages | Limites |
|---|---|---|---|
| **Push MT5 (recommandé)** | Appli MetaTrader 5 sur le téléphone + ton MetaQuotes ID | Gratuit, intégré, rien à installer d'autre, 5 minutes de réglage | 255 caractères par message (le récap arrive en 3 ou 4 morceaux), 10 messages par minute max |
| Telegram (en plus) | Créer un bot avec @BotFather, autoriser l'adresse dans MT5 | Messages longs, historique facile à relire, consultable sur PC | 10 minutes de réglage de plus |
| E-mail | Régler un serveur SMTP dans MT5 | Archive | Lent, finit souvent dans les spams |

Ma recommandation : commence par le **push MT5** seul. C'est le plus simple et ça suffit pour être prévenu à chaque trade. Ajoute Telegram ensuite si tu veux relire les récaps en entier.

## Installation : le push MT5 (5 minutes)

1. Sur ton téléphone, installe l'appli **MetaTrader 5** (App Store ou Google Play).
2. Dans l'appli, va dans **Paramètres > Messages** (ou **Chat et messages**) et copie ton **MetaQuotes ID** : 8 caractères, par exemple `1A2B3C4D`.
3. Sur le PC, dans MT5 : **Outils > Options > Notifications**. Coche **Activer les notifications push**, colle ton MetaQuotes ID, puis clique sur **Test**. Tu dois recevoir un message sur le téléphone.
4. Dans le Navigateur de MT5, glisse **TradeNotifier** sur **un seul graphique**, par exemple EURUSD. Mets-le sur un autre graphique que le robot de trading.
5. Laisse les réglages par défaut et clique sur **OK**. Tu reçois tout de suite « TradeNotifier lancé ». En haut à gauche du graphique, un panneau affiche l'état du suivi.

## En option : Telegram

1. Dans Telegram, écris à **@BotFather**, envoie `/newbot` et choisis un nom. Il te donne un **token**.
2. Écris un message à ton nouveau bot, puis ouvre `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` dans un navigateur. Le nombre après `"chat":{"id":` est ton **chat_id**.
3. Dans MT5 : **Outils > Options > Expert Advisors**, coche **Autoriser WebRequest pour les URL listées** et ajoute `https://api.telegram.org`.
4. Dans les réglages de TradeNotifier, mets `InpTelegram = true` et colle le token et le chat_id.

Ne partage jamais ce token : avec, n'importe qui peut écrire avec ton bot.

## Avec le nouveau robot SansYen : éviter les doublons

SansYen_MT5 envoie déjà sa propre notification à chaque trade (réglage `InpPush`). Si tu laisses les deux robots allumés, tu reçois chaque trade en double, et MT5 bloque au-delà de 10 notifications par minute. Choisis l'une des deux pistes :

1. **Recommandé :** mets `InpPush = false` dans SansYen et laisse TradeNotifier tout envoyer. Ses messages sont plus complets (pips, raison de la sortie, durée, risque, total du jour, heure de Paris), ils sont espacés pour ne jamais dépasser la limite, et les trades fermés pendant une coupure sont rattrapés.
2. Garde `InpPush = true` dans SansYen et mets `InpTradeAlerts = false` dans TradeNotifier. Tu gardes alors seulement le récap du soir et les alertes de TradeNotifier.

TradeNotifier suit aussi les lignes de day trading de SansYen v2.10 (magic 26110207 à 26110211, stratégies ORB30US, ORB15US et ORB30DAX) : la stratégie s'affiche dans chaque message. Le récap passe à 22h30 pour que les trades du jour, fermés vers 22h, y soient comptés. Les marchés du récap sont réglés par défaut sur ceux de SansYen : EURCHF, XAGUSD, US30, US500, USTECH100M et DE40 (le DAX), plus EURUSD et l'or pour avoir le contexte.

## Analyse du marché chaque jour (version 1.11)

TradeNotifier envoie aussi une **analyse du marché**, à partir des fichiers que le robot **DayTrader** écrit dans `MQL5\Files\DayTrader\outbox\` :

- **le matin à 8h45 (heure de Paris)**, avant l'ouverture du DAX : ce qui monte, ce qui baisse, la tendance sur 20 jours, la volatilité de chaque marché (DAX, or, indices US, EURUSD, pétrole…), le plan de chaque stratégie pour la journée et les annonces économiques importantes avec leur heure (calendrier intégré à MT5) ;
- **le soir vers 22h05** : le bilan du jour, les résultats du robot, et les annonces publiées comparées aux prévisions (« plus haut que prévu »…) ;
- **avant chaque trade** : pourquoi le robot entre, le prix, le stop, le risque, le contexte du marché et les annonces des 3 prochaines heures ;
- **après chaque trade** : le résultat en euros et en R, la raison de la sortie, jusqu'où le trade est allé pour et contre toi, une lecture du trade (« il était gagnant de 1,2 R avant de se retourner »…) et les annonces publiées pendant le trade.

Si DayTrader n'a pas envoyé son rapport, TradeNotifier en fait un de secours à 9h15 et à 22h30 sur les marchés de `InpMarketSymbols` (réglage `InpOwnReports`).

### Deux niveaux d'analyse

1. **Automatique (gratuit, par défaut)** : TradeNotifier met les chiffres en phrases et ajoute les annonces économiques. Il dit *ce qui* bouge, mais il ne peut pas expliquer *pourquoi* au-delà des annonces du calendrier.
2. **Rédigée par l'IA Claude (en option)** : Claude reçoit les mêmes chiffres, cherche les news du jour sur le web et écrit en français ce qui monte, ce qui baisse et **pourquoi**, avec la source. Si l'IA ne répond pas, tu reçois le commentaire automatique à la place.

Pour activer l'IA :

1. Crée un compte sur **console.anthropic.com**, ajoute un moyen de paiement et crée une **clé API**. Mets tout de suite une **limite de dépense mensuelle**, par exemple 20 $, dans *Settings > Limits*.
2. Dans MT5 : **Outils > Options > Expert Advisors > Autoriser WebRequest**, ajoute `https://api.anthropic.com`.
3. Dans les réglages de TradeNotifier : `InpAI = true` et colle la clé dans `InpAiKey`.
4. Pour tester tout de suite, mets `InpTestAnalysis = true` : un rapport d'essai part 15 secondes après le lancement.

**Coût estimé** avec le modèle par défaut (`claude-opus-5-5`) : environ 0,10 à 0,15 $ par rapport avec recherche de news, et environ 0,05 $ par analyse de trade. Avec 2 rapports et 4 trades par jour, ça fait environ 10 à 20 $ par mois. Avec `claude-sonnet-5-5`, c'est à peu près deux fois moins cher. `InpAiMaxPerDay` (20 par défaut) plafonne le nombre d'analyses par jour. Ce sont des estimations : le vrai coût s'affiche dans la console.

Si la recherche web est refusée, TradeNotifier réessaie sans elle. Dans ce cas, active la recherche web dans les réglages de ton organisation sur la console.

**Garde ta clé secrète.** Elle est enregistrée en clair dans les réglages du robot sur ton PC. Ne partage jamais une capture d'écran de ces réglages. Le plafond de dépense te protège si la clé fuit.

**Telegram fortement conseillé avec l'analyse.** Une notification push MT5 fait 255 caractères au maximum. Avec Telegram, le téléphone reçoit un résumé en push et l'analyse complète sur Telegram. Sans Telegram, l'analyse arrive coupée en 3 ou 4 notifications.

## Réglages utiles

- `InpMagicMin` / `InpMagicMax` : laisse 0 et 0 pour suivre **tous** les trades du compte. Pour ne suivre que SansYen, mets 26110200 et 26110299.
- `InpRecapHour` / `InpRecapMinute` : heure du récap, en heure de Paris (le changement d'heure est géré).
- `InpMarketSymbols` : la liste des marchés décrits dans le récap. Elle reprend par défaut les marchés de SansYen, sans yen.
- `InpDailyLossAlertPct` : seuil de l'alerte de perte du jour.

## Ce qu'il faut savoir franchement

- **Si le PC est éteint ou en veille, il n'y a ni trades ni notifications.** Le robot et le compagnon tournent dans MT5 sur ton PC. Pendant la démo, deux pistes :
  1. **Garder le PC allumé.** Dans Windows, va dans **Paramètres > Système > Alimentation** et mets la mise en veille sur **Jamais**. C'est gratuit.
  2. **Louer un VPS.** Le VPS MetaQuotes coûte environ 10 à 15 $ par mois et se loue depuis MT5 (clic droit sur le compte > Enregistrer un serveur virtuel). Il tourne 24h/24 et copie tes robots et leurs réglages. C'est la solution propre pour plus tard.
- Si MT5 s'arrête complètement, personne ne peut te prévenir : le compagnon s'arrête avec lui. Le récap du soir sert de **signe de vie**. Si tu ne le reçois pas, c'est que quelque chose est arrêté.
- Les notifications ne marchent pas dans le testeur de stratégie, seulement sur un graphique en démo ou en réel.
- Au premier lancement, les anciens trades ne sont pas renvoyés. Après un redémarrage de MT5, les trades faits pendant l'arrêt sont envoyés (le dernier trade traité est mémorisé).
