"""Journal limite a la derniere annee (demande d'aurele 02/11/2026 : tests max sur un an)."""
import json, numpy as np, pandas as pd
D = json.load(open("carnet2_data.json"))
DEB = "2025-11-03"
weeks = [w for w in D["weeks"] if w >= DEB]
trades = [t for t in D["trades"] if t[6] >= DEB]
summ = []
for s in D["summary"]:
    tt = [t for t in trades if t[0] == s["id"]]
    e = np.array([t[5] for t in tt]) if tt else np.zeros(0)
    W = pd.Series(0.0, index=weeks)
    for t in tt: W[t[6]] += t[5]
    days = len({t[3][:10] for t in tt})
    summ.append(dict(s, trades=len(tt), gagnants=int((e > 0).sum()), perdants=int((e < 0).sum()), total=int(e.sum()),
                     moy_trade=float(round(e.mean(), 1)) if len(e) else 0, sem_pos=int(round(100 * (W > 0).mean())),
                     moy_sem=int(round(W.mean())), pire_sem=int(W.min()), meilleure_sem=int(W.max()),
                     par_jour=round(len(tt) / 256, 2), sans5=int(W.sum() - W.nlargest(5).sum()),
                     sem_g=int((W > 0).sum()), sem_p=int((W < 0).sum())))
out = dict(weeks=weeks, summary=summ, trades=trades)
json.dump(out, open("carnet_1an.json", "w"), ensure_ascii=False)
for s in summ:
    print(s["id"], s["trades"], s["par_jour"], s["gagnants"], s["perdants"], s["total"], s["moy_trade"], s["sem_g"], s["sem_p"], s["pire_sem"], s["meilleure_sem"], s["sans5"])
