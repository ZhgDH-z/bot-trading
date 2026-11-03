# Les 3 gagnantes de 2025-2026 : d'où viennent les pertes, et comment les corriger (02/11/2026)

Les 3 stratégies :

- **1re bougie de 15 min du DAX** : on entre dans le sens de la 1re bougie après l'ouverture du DAX.
- **Zone de bruit du DAX** (Zarattini et al. 2024).
- **Initial Balance sur l'or** : cassure de la 1re heure de New York.

Les montants sont calculés à 100 € de risque par trade, sur l'historique 15 min de ton MT5.

## 1. Où sont les pertes

| Cause | Ce que montrent les chiffres | Vrai problème ou hasard ? |
|---|---|---|
| **Trades contre la tendance** (vendre quand le marché monte depuis 20 jours, ou l'inverse) | La moitié des trades. Sur 2025-2026 : −762 € (1re bougie DAX), −1 027 € (zone de bruit). Ils perdaient **aussi sur 2022-2024** pour les 3 stratégies. | **Vrai problème**, et le même sur 3 stratégies et 2 périodes |
| **Les ventes** | Elles perdent même dans le sens de la tendance : −0,09 R par trade sur 2022-24, −0,05 R sur 2025-26. Le DAX et l'or ont beaucoup monté. | Réel sur la période, mais lié à un marché haussier : ça peut changer |
| **Stop serré** de la 1re bougie DAX | 69 % des trades touchent le stop. Les gains viennent de 90 gros trades (sur 417). Série de 17 pertes d'affilée. | C'est le prix de ce type de stratégie, pas une erreur |
| Jeudi (zone de bruit) ou vendredi (or) perdants | −923 € et −712 € | **Hasard probable** : ça change d'une stratégie à l'autre, je ne filtre pas dessus |
| Volatilité haute ou basse | Effets contradictoires d'une stratégie à l'autre | **Hasard**, pas de filtre |

## 2. Les correctifs testés

| Version | 2022-2024 (avant) | 2025 | 2026 (jan-oct) | Pire baisse 2025-26 |
|---|---|---|---|---|
| Trio de base | −7 214 € | +8 297 € | +1 586 € | −4 941 € |
| **Correctif 1 : seulement dans le sens de la tendance 20 jours** | **+926 €** | **+9 683 €** | **+1 870 €** | **−3 044 €** |
| Correctif 2 : « évolutif », mise divisée par 2 après 20 mauvais trades | −6 493 € | +8 026 € | −226 € | −3 182 € |
| Correctifs 1 + 2 | −422 € | +7 744 € | +1 631 € | −2 444 € |

- **Le filtre de tendance est le bon correctif.** C'est lui qui rend le bot évolutif : il achète quand le marché monte et vend quand il baisse. Il améliore les 3 périodes, y compris 2022-2024, qui n'a pas servi à le choisir.
- **Réduire la mise après une série de pertes n'aide pas** : en 2026, ça transforme +1 586 € en −226 €. Je ne le garde pas.

## 3. Réglage des ventes (avec le filtre de tendance)

| Réglage | 2022-2024 | 2025-2026 | Pire baisse 2025-26 | Jours avec un trade |
|---|---|---|---|---|
| A. Achat et vente à 100 € | +926 € | +11 553 € | −3 044 € | 66 % |
| **C. Achat 100 €, vente 50 €** | **+2 703 €** | **+12 123 €** | **−2 632 €** | **66 %** |
| B. Achat seul | +4 479 € | +12 694 € | −2 220 € | 42 % |

En 2025-2026, la version C fait environ 1,2 trade par jour et 57 % de mois positifs. Sans sa meilleure semaine (+3 660 €), elle reste à environ +8 000 €. La pire série est de 19 pertes d'affilée : il faut le savoir avant de lancer la démo.

Scripts : `analyse3.py`, `correctifs.py`.
