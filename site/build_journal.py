"""Construit site/journal_melvin.html (le site de Melvin) a partir de robuste/journal_mensuel.html : on garde le style et les
donnees du backtest, on remplace la page et le script. Usage : python site/build_journal.py robuste/journal_mensuel.html site/journal_melvin.html"""
import json, sys

src, out = sys.argv[1], sys.argv[2]
h = open(src, encoding="utf-8").read()
style = h[h.index("<style>") + 7:h.index("</style>")]
i = h.index("const D=") + 8
D, _ = json.JSONDecoder().raw_decode(h, i)

# v1.08 = meme strategie que la v1.07 (seuls 2 correctifs de securite) : meme backtest
for s in D["summary"]:
    if s["id"] == "V107":
        s["nom"] = "v1.07 / v1.08 (en démo)"
        s["desc"] = ("DAX 1re bougie, DAX supertrend, or Initial Balance, or tendance, or cassure de canal 200 bougies, "
                     "filtre de tendance 20 jours. La v1.08 a la même stratégie : elle ajoute seulement des protections "
                     "qui survivent à un redémarrage et ferme l'or à 22h50 (le marché ferme à 23h00).")

CSS = style + """
.tabs{display:flex;gap:8px;margin:14px 0 4px;flex-wrap:wrap}
.tab{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:9px 16px;font:inherit;font-size:15px;font-weight:600;cursor:pointer}
.tab[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.warn{border-left:4px solid var(--neg)}
.ok{border-left:4px solid var(--pos)}
.curve{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-top:10px}
.curve svg{width:100%;height:auto;display:block}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:8px}
.seg button{border:0;background:var(--card);color:var(--ink);font:inherit;font-size:13.5px;padding:6px 12px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--acc);color:#fff}
.drop{display:block;background:var(--card);border:2px dashed var(--line);border-radius:12px;padding:22px;text-align:center;cursor:pointer}
.drop.over{border-color:var(--acc)}
.drop input{display:none}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:10px 0}
.row input[type=datetime-local]{font:inherit;font-size:14px;padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
.btn{font:inherit;font-size:14px;padding:7px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.hidden{display:none}
"""

BODY = """<main>
<h1>Journal des bots</h1>
<div class="mut small">Backtest : dernière année, du 03/11/2025 au 02/11/2026 · démo réelle : depuis le 03/11/2026 · heures de Paris · coûts inclus</div>
<div class="tabs" id="tabs"><button class="tab" data-t="bt">📊 Backtest</button><button class="tab" data-t="demo">🔴 Démo réelle</button></div>

<div class="note"><b><span id="mise">1 000</span> € risqués par trade</b> (achat comme vente) : c'est ce que tu perds si le stop est touché. Un gagnant peut rapporter plus.</div>
<div class="chips" id="fx"><button class="chip" data-f="1">100 €</button><button class="chip" data-f="2">200 €</button><button class="chip" data-f="10">1 000 €</button><button class="chip" data-f="3">1 trade sur 3 à 1 000 €, les autres à 200 €</button></div>
<label class="amt" for="amt">✏️ <b>Ton montant :</b> <input id="amt" type="text" inputmode="decimal" autocomplete="off" aria-label="Montant risqué par trade en euros"> € risqués par trade <span class="mut small">(tout se recalcule)</span></label>

<section id="bt">
<div class="note warn">⚠️ <b>À lire avant de croire les chiffres.</b> Ce sont des tests sur le passé, et les stratégies ont été choisies en regardant cette même année : la réalité sera plus faible. Le seul vrai juge, c'est l'onglet <b>Démo réelle</b>, sur plusieurs semaines.</div>
<div class="chips" id="chips"></div>
<p class="desc" id="desc"></p>
<h2>Sur l'année</h2>
<div class="grid" id="tot"></div>
<div class="curve"><div class="mut small" id="ctitle">Évolution du résultat, trade après trade (rouge : baisse depuis le plus haut)</div><div id="curve"></div></div>
<h2>Meilleures et pires périodes</h2>
<div class="two"><div class="list" id="best"></div><div class="list" id="worst"></div></div>
<h2>D'affilée</h2>
<div class="grid" id="streak"></div>
<h2 id="ptitle">Mois par mois</h2>
<div class="seg" id="view"><button data-v="mois">Par mois</button><button data-v="sem">Par semaine</button></div>
<div class="mut small" style="margin-bottom:8px">Clique une ligne pour voir ses trades.</div>
<div class="tw"><table><thead><tr><th id="pcol">Mois</th><th class="n">Trades</th><th class="n">/ jour</th><th class="n">G</th><th class="n">P</th><th class="n">Résultat</th><th></th><th class="n">Cumul</th></tr></thead><tbody id="months"></tbody></table></div>
<h2 id="mtitle">Trades</h2>
<div class="grid" id="mk" style="margin-bottom:10px"></div>
<div class="tw scroll"><table><thead><tr><th>Entrée</th><th>Sortie</th><th>Ligne / marché</th><th>Sens</th><th class="n">Risqué</th><th class="n">Résultat</th></tr></thead><tbody id="trs"></tbody></table></div>
</section>

<section id="demo" class="hidden">
<div class="note">La démo tourne sur le PC d'Aurel. Le robot écrit chaque trade fermé dans <b>journal.csv</b> : dans MT5, Fichier → Ouvrir le dossier des données → <b>MQL5\\Files\\DayTrader\\journal.csv</b>. Dépose ce fichier ici, chaque semaine. Il est lu dans ton navigateur, il ne part nulle part. Comparaison avec le backtest de la <b>v1.07 / v1.08</b>.</div>
<label class="drop" id="drop">📂 <b>Clique ou dépose journal.csv ici</b><br><span class="mut small" id="fname">aucun fichier chargé</span><input type="file" id="file" accept=".csv,text/csv,text/plain"></label>
<div class="row"><span class="small">Compter les trades depuis :</span><input type="datetime-local" id="since" value="2026-11-03T15:07"><span class="mut small">(heure de Paris ; 03/11/2026 15h07 = début de la v1.07)</span><button class="btn" id="clear">Oublier le fichier</button></div>
<div id="dout"></div>
</section>
</main>"""

JS = r"""
const $=id=>document.getElementById(id);
const MOIS=['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'];
const JOURS=['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'];
const fe=v=>{const s=Math.round(v).toLocaleString('fr-FR');return (v>0?'+':'')+s+' €'};
const fn=v=>Math.round(v).toLocaleString('fr-FR')+' €';
const cl=v=>v>0?'pos':v<0?'neg':'';
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fdt=s=>s?s.slice(8,10)+'/'+s.slice(5,7)+' '+s.slice(11,16):'—';
const ml=m=>MOIS[+m.slice(5,7)-1]+' '+m.slice(0,4)+(m==='2026-11'?' (2 jours)':'');
const wl=w=>'sem. du '+w.slice(8,10)+'/'+w.slice(5,7)+'/'+w.slice(0,4);
const LS={get(k){try{return localStorage.getItem(k)}catch(e){return null}},set(k,v){try{localStorage.setItem(k,v)}catch(e){}},del(k){try{localStorage.removeItem(k)}catch(e){}}};
let TAB=LS.get('jm_tab')==='demo'?'demo':'bt';
let strat=LS.get('jm_strat');if(!D.summary.some(x=>x.id===strat))strat=D.summary[0].id;
let VIEW=LS.get('jm_view')==='sem'?'sem':'mois',mi=null;
let RISK=1000,TIERS=false;{const r=parseFloat(LS.get('jm_risk'));if(r>0)RISK=r;TIERS=LS.get('jm_tiers')==='1'}
function save(){LS.set('jm_risk',String(RISK));LS.set('jm_tiers',TIERS?'1':'0')}
let byS={};function build(){byS={};for(const t of D.trades){(byS[t[0]]=byS[t[0]]||[]).push(t.slice())}for(const k in byS){byS[k].sort((a,b)=>a[3]<b[3]?-1:1);byS[k].forEach((u,i)=>{const m=TIERS?(i%3===0?10:2):RISK/100;u[5]=u[5]*m;u.push(m*100)})}}
build();
function st(l){let n=l.length,g=0,p=0,e=0;for(const t of l){e+=t[5];if(t[5]>0)g++;else if(t[5]<0)p++}return{n,g,p,e,days:new Set(l.map(t=>t[3].slice(0,10))).size}}
function run(arr,f){let best=0,cur=0;arr.forEach(x=>{if(f(x)){cur++;if(cur>best)best=cur}else cur=0});return best}
function k(label,val,c){return `<div class="k"><b class="${c||''}">${val}</b><span>${label}</span></div>`}
function drawdown(vals){let c=0,pk=0,dd=0;const cum=[],pks=[];for(const v of vals){c+=v;pk=Math.max(pk,c);dd=Math.min(dd,c-pk);cum.push(c);pks.push(pk)}return{cum,pks,dd}}
function curve(cum,pks,labels){
 const W=940,H=170,P=4,n=cum.length;if(n<2)return '<div class="mut small">Pas assez de trades.</div>';
 const lo=Math.min(0,...cum),hi=Math.max(0,...pks),sy=v=>P+(H-2*P)*(1-(v-lo)/((hi-lo)||1)),sx=i=>P+(W-2*P)*i/(n-1);
 let line='',dd='';cum.forEach((v,i)=>{line+=(i?'L':'M')+sx(i).toFixed(1)+' '+sy(v).toFixed(1)});
 dd='M'+sx(0)+' '+sy(pks[0]);pks.forEach((v,i)=>dd+='L'+sx(i).toFixed(1)+' '+sy(v).toFixed(1));for(let i=n-1;i>=0;i--)dd+='L'+sx(i).toFixed(1)+' '+sy(cum[i]).toFixed(1);dd+='Z';
 const ticks=labels.map(([i,t])=>{const x=sx(i),a=x<40?'start':x>W-40?'end':'middle';return `<text x="${x}" y="${H+14}" font-size="11" fill="var(--mut)" text-anchor="${a}">${t}</text>`}).join('');
 return `<svg viewBox="0 0 ${W} ${H+18}" role="img" aria-label="Courbe du résultat cumulé"><line x1="${P}" x2="${W-P}" y1="${sy(0)}" y2="${sy(0)}" stroke="var(--line)"/><path d="${dd}" fill="var(--negbg)"/><path d="${line}" fill="none" stroke="var(--acc)" stroke-width="2"/>${ticks}</svg>`}

function renderTop(){
 document.querySelectorAll('#tabs .tab').forEach(b=>b.setAttribute('aria-pressed',b.dataset.t===TAB));
 $('bt').classList.toggle('hidden',TAB!=='bt');$('demo').classList.toggle('hidden',TAB!=='demo');
 document.querySelectorAll('#fx .chip').forEach(b=>{const f=b.dataset.f;b.setAttribute('aria-pressed',f==='3'?TIERS:(!TIERS&&RISK===100*f))});
 $('mise').textContent=TIERS?'1 000 € (1 trade sur 3) ou 200':RISK.toLocaleString('fr-FR',{maximumFractionDigits:2});
 const ai=$('amt');if(document.activeElement!==ai)ai.value=TIERS?'':String(RISK).replace('.',',');ai.placeholder=TIERS?'ex. 500':'';
}

function render(){
 renderTop();
 if(TAB==='demo'){renderDemo();return}
 const S=D.summary.find(x=>x.id===strat);const T=byS[strat]||[];
 $('chips').innerHTML=D.summary.map(s=>`<button class="chip" aria-pressed="${s.id===strat}" data-id="${s.id}">${esc(s.nom)}</button>`).join('');
 $('desc').textContent=S.desc;
 const months=[...new Set(D.weeks.map(w=>w.slice(0,7)).concat(T.map(t=>t[3].slice(0,7))))].filter(m=>m>='2025-11').sort();
 const MM=months.map(m=>{const l=T.filter(t=>t[3].slice(0,7)===m);return{key:m,lab:ml(m),l,s:st(l)}});
 const full=MM.filter(x=>x.key!=='2026-11');
 const WK=D.weeks.filter(w=>w>='2025-11-03').map(w=>{const l=T.filter(t=>t[6]===w);return{key:w,lab:wl(w),l,s:st(l)}});
 const a=st(T);const {cum,pks,dd}=drawdown(T.map(t=>t[5]));
 const cap=Math.ceil(-dd/0.2/100)*100;
 $('tot').innerHTML=k('trades',a.n)+k('trades par jour de bourse',(a.n/256).toFixed(1).replace('.',','))+k('gagnants / perdants',a.g+' / '+a.p)+k('taux de gain',a.n?Math.round(100*a.g/a.n)+' %':'—')+k('résultat sur l\'année',fe(a.e),cl(a.e))+k('moyenne par trade',a.n?fe(a.e/a.n):'—',cl(a.e))+k('mois gagnants',full.filter(x=>x.s.e>0).length+' sur '+full.length)+k('moyenne par mois',fe(full.reduce((s,x)=>s+x.s.e,0)/full.length),cl(a.e))
  +k('pire baisse depuis un plus haut',fe(dd),'neg')+k('capital minimum pour que cette baisse reste sous 20 %',TIERS?'—':fn(cap))+k('semaines gagnantes',WK.filter(x=>x.s.e>0).length+' sur '+WK.length);
 const lab=[];let lastM='';T.forEach((t,i)=>{const m=t[3].slice(0,7);if(m!==lastM&&+m.slice(5,7)%3===2){lab.push([i,['janv.','févr.','mars','avr.','mai','juin','juil.','août','sept.','oct.','nov.','déc.'][+m.slice(5,7)-1]+' '+m.slice(0,4)])}lastM=m});
 $('curve').innerHTML=curve(cum,pks,lab);
 const P=VIEW==='sem'?WK:MM, Pfull=VIEW==='sem'?WK:full;
 document.querySelectorAll('#view button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.v===VIEW));
 $('ptitle').textContent=VIEW==='sem'?'Semaine par semaine':'Mois par mois';$('pcol').textContent=VIEW==='sem'?'Semaine':'Mois';
 const srt=Pfull.slice().sort((x,y)=>y.s.e-x.s.e);const u=VIEW==='sem'?'semaines':'mois';
 const li=(x,i)=>`<div><span>${i+1}. ${x.lab} <span class="mut small">· ${x.s.n} trades</span></span><b class="${cl(x.s.e)}">${fe(x.s.e)}</b></div>`;
 $('best').innerHTML=`<h3>🏆 Meilleur${VIEW==='sem'?'e':''}s ${u}</h3>`+srt.slice(0,3).map(li).join('');
 $('worst').innerHTML=`<h3>📉 Pires ${u}</h3>`+srt.slice(-3).reverse().map(li).join('');
 const dmap={};for(const t of T){const d=t[3].slice(0,10);dmap[d]=(dmap[d]||0)+t[5]}
 const dv=Object.keys(dmap).sort().map(d=>dmap[d]);
 const sv=x=>x?x:'0';
 $('streak').innerHTML=k('mois gagnants de suite (record)',sv(run(full,x=>x.s.e>0))+' mois','pos')+k('mois perdants de suite (record)',sv(run(full,x=>x.s.e<0))+' mois','neg')+k('semaines perdantes de suite',sv(run(WK,x=>x.s.e<0))+' sem.','neg')+k('jours gagnants de suite',run(dv,x=>x>0)+' jours','pos')+k('jours perdants de suite',run(dv,x=>x<0)+' jours','neg')+k('trades gagnants de suite',run(T,t=>t[5]>0)+' trades','pos')+k('trades perdants de suite',run(T,t=>t[5]<0)+' trades','neg');
 if(mi===null||mi>=P.length)mi=Math.max(0,P.length-2);
 let c=0;const mx=Math.max(1,...P.map(x=>Math.abs(x.s.e)));
 $('months').innerHTML=P.map((x,i)=>{c+=x.s.e;return `<tr class="click ${i===mi?'sel':''}" data-i="${i}"><td>${x.lab}</td><td class="n">${x.s.n}</td><td class="n">${x.s.days?(x.s.n/x.s.days).toFixed(1).replace('.',','):'—'}</td><td class="n">${x.s.g}</td><td class="n">${x.s.p}</td><td class="n ${cl(x.s.e)}">${x.s.n?fe(x.s.e):'—'}</td><td><span class="bar" style="width:${Math.round(70*Math.abs(x.s.e)/mx)}px;background:var(--${x.s.e>=0?'pos':'neg'})"></span></td><td class="n ${cl(c)}">${fe(c)}</td></tr>`}).join('');
 const cur=P[mi];
 $('mtitle').textContent='Trades : '+cur.lab;
 $('mk').innerHTML=k('trades',cur.s.n)+k('gagnants',cur.s.g,'pos')+k('perdants',cur.s.p,'neg')+k('résultat',fe(cur.s.e),cl(cur.s.e))+k('par trade',cur.s.n?fe(cur.s.e/cur.s.n):'—',cl(cur.s.e));
 $('trs').innerHTML=cur.l.length?cur.l.map(t=>`<tr><td>${JOURS[(new Date(t[3].slice(0,10)+'T12:00:00').getDay()+6)%7]} ${fdt(t[3])}</td><td>${fdt(t[4])}</td><td>${esc(t[1])}</td><td><span class="tag ${t[2]>0?'a':'v'}">${t[2]>0?'Achat':'Vente'}</span></td><td class="n">${t[t.length-1].toLocaleString('fr-FR',{maximumFractionDigits:2})} €</td><td class="n ${cl(t[5])}">${fe(t[5])}</td></tr>`).join(''):'<tr><td colspan="6" class="mut">Aucun trade sur cette période.</td></tr>';
}

/* ---------------- Démo réelle ---------------- */
const NOMS={'DAX1B':'DAX 1re bougie','DAXST':'DAX supertrend 15 min','ORIB':'Or Initial Balance','ORTEND':'Or tendance du jour','ORBREAK':'Or cassure de canal 200 bougies','DAXBRUIT':'DAX zone de bruit'};
let CSV=LS.get('jm_csv')||'',CSVNAME=LS.get('jm_csvname')||'';
const num=s=>{const v=parseFloat(String(s||'').replace('+','').replace(',','.'));return isNaN(v)?0:v};
function parisOf(s){ // heure serveur MetaQuotes = Paris + 1 h
 const m=String(s||'').match(/(\d{4})[.\-](\d{2})[.\-](\d{2})[ T](\d{2}):(\d{2})/);if(!m)return null;
 const d=new Date(Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5])-3600e3);return d.toISOString().slice(0,16).replace('T',' ')}
function mondayOf(day){const d=new Date(day+'T12:00:00Z');const k=(d.getUTCDay()+6)%7;d.setUTCDate(d.getUTCDate()-k);return d.toISOString().slice(0,10)}
function parseJournal(txt){
 const lines=txt.split(/\r?\n/).filter(x=>x.trim());if(lines.length<2)return{err:'Fichier vide.'};
 const H=lines[0].split(';').map(x=>x.trim());const ix=n=>H.indexOf(n);
 for(const n of ['ouverture_serveur','fermeture_serveur','position','strategie','sens','risque','resultat'])if(ix(n)<0)return{err:'Ce n\'est pas le journal.csv du robot (colonne « '+n+' » absente).'};
 const pos={};
 for(const l of lines.slice(1)){const c=l.split(';');const id=c[ix('position')];if(!id)continue;
  const p=pos[id]||(pos[id]={id,strat:c[ix('strategie')],sym:c[ix('symbole')]||'',sens:c[ix('sens')],op:null,cl:null,risk:0,res:0,n:0});
  const o=parisOf(c[ix('ouverture_serveur')]),f=parisOf(c[ix('fermeture_serveur')]);
  if(o&&(!p.op||o<p.op))p.op=o;if(f&&(!p.cl||f>p.cl))p.cl=f;
  p.risk=Math.max(p.risk,num(c[ix('risque')]));p.res+=num(c[ix('resultat')]);p.n++}
 const out=Object.values(pos).filter(p=>p.op&&p.risk>0).map(p=>({...p,e100:p.res/p.risk*100,week:mondayOf(p.op.slice(0,10))}));
 out.sort((a,b)=>a.op<b.op?-1:1);return{trades:out}}
function quant(a,q){const s=a.slice().sort((x,y)=>x-y);const i=(s.length-1)*q,lo=Math.floor(i);return s[lo]+(s[Math.ceil(i)]-s[lo])*(i-lo)}
function renderDemo(){
 $('fname').textContent=CSV?(CSVNAME||'journal.csv')+' chargé':'aucun fichier chargé';
 if(!CSV){$('dout').innerHTML='<div class="note">Pas encore de fichier. Le robot ne crée journal.csv qu\'après son premier trade fermé.</div>';return}
 const r=parseJournal(CSV);if(r.err){$('dout').innerHTML=`<div class="note warn">${esc(r.err)}</div>`;return}
 const since=($('since').value||'2026-11-03T15:07').replace('T',' ');
 const m=TIERS?2:RISK/100;
 const T=r.trades.filter(t=>t.op>=since).map(t=>({...t,e:t.e100*m}));
 const BT=(D.trades.filter(t=>t[0]==='V107'));
 const weeks=D.weeks.filter(w=>w>='2025-11-03');
 const wsum={};weeks.forEach(w=>wsum[w]=0);BT.forEach(t=>{if(t[6] in wsum)wsum[t[6]]+=t[5]*m});
 const wv=Object.values(wsum),wmean=wv.reduce((a,b)=>a+b,0)/wv.length,wlo=quant(wv,0.1),whi=quant(wv,0.9);
 let h='';
 if(!T.length){$('dout').innerHTML=`<div class="note">Aucun trade depuis le ${esc(since)} dans ce fichier (${r.trades.length} trades au total).</div>`;return}
 const a=st(T.map(t=>[0,0,0,t.op,0,t.e]));const W=[...new Set(T.map(t=>t.week))].sort();
 const exp=wmean*W.length;
 h+=`<h2>Depuis le ${fdt(since)}</h2><div class="grid">${k('trades',a.n)+k('gagnants / perdants',a.g+' / '+a.p)+k('résultat de la démo',fe(a.e),cl(a.e))+k('attendu par le backtest ('+W.length+' sem.)',fe(exp),cl(exp))+k('écart démo − backtest',fe(a.e-exp),cl(a.e-exp))+k('trades par semaine (backtest : '+(BT.length/weeks.length).toFixed(1).replace('.',',')+')',(a.n/W.length).toFixed(1).replace('.',','))}</div>`;
 h+=`<div class="note">En backtest, 8 semaines sur 10 finissent entre <b>${fe(wlo)}</b> et <b>${fe(whi)}</b> (moyenne ${fe(wmean)}). Une semaine hors de cette fourchette arrive : c'est la répétition qui compte.</div>`;
 // semaines
 let c=0;h+=`<h2>Semaine par semaine</h2><div class="tw"><table><thead><tr><th>Semaine</th><th class="n">Trades</th><th class="n">G</th><th class="n">P</th><th class="n">Démo</th><th class="n">Cumul</th><th>Par rapport au backtest</th></tr></thead><tbody>`;
 for(const w of W){const l=T.filter(t=>t.week===w);const s=st(l.map(t=>[0,0,0,t.op,0,t.e]));c+=s.e;
  const etat=s.e<wlo?'<span class="neg">sous la fourchette</span>':s.e>whi?'<span class="pos">au-dessus</span>':'normale';
  h+=`<tr><td>${wl(w)}</td><td class="n">${s.n}</td><td class="n">${s.g}</td><td class="n">${s.p}</td><td class="n ${cl(s.e)}">${fe(s.e)}</td><td class="n ${cl(c)}">${fe(c)}</td><td>${etat}</td></tr>`}
 h+='</tbody></table></div>';
 // lignes
 h+=`<h2>Ligne par ligne</h2><div class="tw"><table><thead><tr><th>Ligne</th><th class="n">Trades démo</th><th class="n">/ sem. démo</th><th class="n">/ sem. test</th><th class="n">% gagnants démo</th><th class="n">% gagnants test</th><th class="n">€ / trade démo</th><th class="n">€ / trade test</th><th>Verdict</th></tr></thead><tbody>`;
 for(const s of ['DAX1B','DAXST','ORIB','ORTEND','ORBREAK']){
  const d=T.filter(t=>t.strat===s),b=BT.filter(t=>t[1]===NOMS[s]).map(t=>t[5]*m);if(!d.length&&!b.length)continue;
  const mb=b.reduce((x,y)=>x+y,0)/(b.length||1),sd=Math.sqrt(b.reduce((x,y)=>x+(y-mb)**2,0)/Math.max(1,b.length-1))||1;
  const md=d.length?d.reduce((x,t)=>x+t.e,0)/d.length:0;let v='trop tôt (moins de 30 trades)';
  if(d.length>=30){const z=(md-mb)/(sd/Math.sqrt(d.length));v=z<-2.5?'<span class="neg">ALERTE : nettement sous le test</span>':z<-1.5?'<span class="neg">à surveiller</span>':z>2.5?'au-dessus du test : vérifier':'<span class="pos">dans la norme</span>';v+=` <span class="mut small">(${z>0?'+':''}${z.toFixed(1)})</span>`}
  h+=`<tr><td>${NOMS[s]}</td><td class="n">${d.length}</td><td class="n">${(d.length/W.length).toFixed(1).replace('.',',')}</td><td class="n">${(b.length/weeks.length).toFixed(1).replace('.',',')}</td><td class="n">${d.length?Math.round(100*d.filter(t=>t.e>0).length/d.length)+' %':'—'}</td><td class="n">${b.length?Math.round(100*b.filter(x=>x>0).length/b.length)+' %':'—'}</td><td class="n ${cl(md)}">${d.length?fe(md):'—'}</td><td class="n ${cl(mb)}">${fe(mb)}</td><td>${v}</td></tr>`}
 h+='</tbody></table></div>';
 // anomalies
 const nuit=T.filter(t=>t.cl&&t.cl.slice(0,10)!==t.op.slice(0,10));
 const inconnu=T.filter(t=>!NOMS[t.strat]);
 h+=`<h2>Contrôles</h2><div class="note ${nuit.length?'warn':'ok'}">${nuit.length?`⚠️ <b>${nuit.length} position(s) ont passé la nuit</b> : le robot doit tout fermer le jour même. Sur l'or, c'est le bug corrigé par la v1.08.`:'✅ Aucune position n\'a passé la nuit.'}${inconnu.length?`<br>⚠️ ${inconnu.length} trade(s) d'une ligne inconnue.`:''}</div>`;
 if(nuit.length)h+=`<div class="tw"><table><thead><tr><th>Ligne</th><th>Sens</th><th>Entrée</th><th>Sortie</th><th class="n">Résultat</th></tr></thead><tbody>${nuit.map(t=>`<tr><td>${esc(NOMS[t.strat]||t.strat)}</td><td>${esc(t.sens)}</td><td>${fdt(t.op)}</td><td>${fdt(t.cl)}</td><td class="n ${cl(t.e)}">${fe(t.e)}</td></tr>`).join('')}</tbody></table></div>`;
 h+=`<h2>Tous les trades de la démo</h2><div class="tw scroll"><table><thead><tr><th>Entrée</th><th>Sortie</th><th>Ligne</th><th>Sens</th><th class="n">Résultat</th></tr></thead><tbody>${T.slice().reverse().map(t=>`<tr><td>${JOURS[(new Date(t.op.slice(0,10)+'T12:00:00').getDay()+6)%7]} ${fdt(t.op)}</td><td>${fdt(t.cl)}</td><td>${esc(NOMS[t.strat]||t.strat)}</td><td><span class="tag ${/vente/i.test(t.sens)?'v':'a'}">${/vente/i.test(t.sens)?'Vente':'Achat'}</span></td><td class="n ${cl(t.e)}">${fe(t.e)}</td></tr>`).join('')}</tbody></table></div>`;
 h+=`<div class="mut small" style="margin-top:8px">Résultats ramenés à ${TIERS?'200':RISK.toLocaleString('fr-FR')} € risqués par trade (résultat réel ÷ risque réel du trade). Les demi-sorties de l'Or Initial Balance comptent pour un seul trade.</div>`;
 $('dout').innerHTML=h}
function loadFile(f){if(!f)return;const rd=new FileReader();rd.onload=()=>{CSV=String(rd.result||'');CSVNAME=f.name;LS.set('jm_csv',CSV);LS.set('jm_csvname',CSVNAME);render()};rd.readAsText(f,'windows-1252')}

$('tabs').onclick=e=>{const b=e.target.closest('.tab');if(!b)return;TAB=b.dataset.t;LS.set('jm_tab',TAB);render()};
$('chips').onclick=e=>{const b=e.target.closest('.chip');if(!b)return;strat=b.dataset.id;LS.set('jm_strat',strat);mi=null;render()};
$('view').onclick=e=>{const b=e.target.closest('button');if(!b)return;VIEW=b.dataset.v;LS.set('jm_view',VIEW);mi=null;render()};
$('months').onclick=e=>{const r=e.target.closest('tr[data-i]');if(!r)return;mi=+r.dataset.i;render();$('mtitle').scrollIntoView({behavior:'smooth',block:'start'})};
$('fx').onclick=e=>{const b=e.target.closest('.chip');if(!b)return;const f=b.dataset.f;if(f==='3')TIERS=true;else{TIERS=false;RISK=100*f}save();build();render()};
$('amt').addEventListener('input',e=>{const v=parseFloat(e.target.value.replace(/\s/g,'').replace(',','.'));if(!(v>0)||v>10000000)return;RISK=v;TIERS=false;save();build();render()});
$('amt').addEventListener('blur',()=>render());
$('file').addEventListener('change',e=>loadFile(e.target.files[0]));
const dz=$('drop');['dragenter','dragover'].forEach(n=>dz.addEventListener(n,e=>{e.preventDefault();dz.classList.add('over')}));
['dragleave','drop'].forEach(n=>dz.addEventListener(n,e=>{e.preventDefault();dz.classList.remove('over')}));
dz.addEventListener('drop',e=>loadFile(e.dataTransfer.files[0]));
$('since').addEventListener('change',()=>render());
$('clear').onclick=()=>{CSV='';CSVNAME='';LS.del('jm_csv');LS.del('jm_csvname');$('file').value='';render()};
render();
"""

page = ("<!doctype html>\n<html lang=\"fr\"><head><meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
        "<meta name=\"claude:viewport-fit-sides\" content=\"left right\">\n"
        "<title>Journal des bots (Melvin)</title>\n<style>" + CSS + "</style></head><body>" + BODY +
        "\n<script>\nconst D=" + json.dumps(D, ensure_ascii=False) + ";\n" + JS + "</script></body></html>\n")
open(out, "w", encoding="utf-8").write(page)
print(len(page), "octets")
