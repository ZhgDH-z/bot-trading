//+------------------------------------------------------------------+
//|                                                DayTrader_MT5.mq5 |
//|  Bot de DAY TRADING sans yen (projet aurele, 02/11/2026).          |
//|  Tout est ferme le jour meme. Achat ET vente.                      |
//|                                                                    |
//|  Les 3 strategies gagnantes de 2025-2026, avec le correctif        |
//|  "tendance" : on n'achete que si le marche monte depuis 20 jours   |
//|  (cloture d'hier > moyenne 20 jours), on ne vend que s'il baisse.  |
//|                                                                    |
//|   DAX1B    : 1re bougie de 15 min du DAX (10h00-10h15 serveur).    |
//|              Entree a 10h15 dans le sens de la bougie, stop de     |
//|              l'autre cote de la bougie, fermeture a 18h30 serveur. |
//|   DAXBRUIT : zone de bruit (Zarattini, Aziz, Barbon 2024) sur le   |
//|              DAX. Toutes les 30 min, achat si le prix sort au-     |
//|              dessus de la zone de bruit ET de la VWAP, vente si    |
//|              en dessous. Sortie quand il revient sous la zone ou   |
//|              la VWAP, et a 18h30 au plus tard.                     |
//|   ORIB     : Initial Balance sur l'or. Range de la 1re heure de    |
//|              New York (16h30-17h30 serveur). Apres la 1re cassure, |
//|              ordre limite 25 % a l'interieur du range, stop 60 %   |
//|              du range, objectif 50 % au-dela, fermeture a 23h.     |
//|                                                                    |
//|  Heures = heure du serveur MT5 (New York + 7 h). Heure de Paris =  |
//|  heure serveur - 1 h la plupart du temps.                          |
//|                                                                    |
//|  Fichiers pour l'analyse (MQL5\Files\DayTrader\) :                 |
//|   outbox\     : un fichier cle=valeur par evenement, lu et envoye  |
//|                 par TradeNotifier : MATIN (9h45 serveur), SOIR     |
//|                 (23h05 serveur), OUVERTURE et FERMETURE de trade   |
//|   journal.csv : une ligne par trade ferme (pour les bilans)        |
//|   etat.txt    : capital, positions, protections (toutes les 5 min) |
//|                                                                    |
//|  v1.03 (03/11/2026), 3 correctifs or verifies sur 2023-25 ET sur  |
//|  la derniere annee :                                               |
//|   A  ORIB : moitie de la position fermee a +0,5 R                  |
//|   B  ORIB : pas de trade si l'elan sur 5 jours va contre le trade  |
//|   C  ORTEND : pas de trade si la volatilite est agitee (ATR du     |
//|      jour > 1,2 x sa moyenne des 100 jours)                        |
//|  v1.04 (03/11/2026), idees reprises des skills Claude Trading :     |
//|   D  garde-fou : pas d'entree si l'ecart achat/vente de la         |
//|      derniere bougie depasse 2 x son niveau median des 20 jours    |
//|   E  alarme de degradation dans la notification de fermeture si    |
//|      les 60 derniers trades perdent trop (aucun arret automatique) |
//|  v1.05 (03/11/2026), idee du skill tradingview-mcp (backtests) :   |
//|   F  DAXST : supertrend du DAX en 15 min (ATR 14, multiplicateur 4)|
//|      achat/vente au retournement de la tendance entre 10h00 et     |
//|      18h15 serveur, stop 1,5 x ATR 15 min, sortie au retournement  |
//|      suivant (avec retournement de position) ou a 18h30.           |
//|  v1.06 (03/11/2026), audit :                                       |
//|   G  DAXBRUIT retire de la config par defaut : quasi nul sur       |
//|      2023-2025 (+0,01 R par trade), perdant avec couts x2, pas     |
//|      mieux que le hasard (p = 0,26). Le code reste disponible.     |
//|                                                                    |
//|  Securite : bloque sur compte REEL tant que InpAllowRealAccount    |
//|  = false.                                                          |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.06"
#property description "Day trading sans yen v1.06 : 1re bougie DAX, supertrend DAX, Initial Balance or, or tendance, garde-fous"

#include <Trade/Trade.mqh>

input group "=== Marches et strategies ==="
input string InpConfig       = "DE40:DAX1B,XAUUSD:ORIB,XAUUSD:ORTEND,DE40:DAXST"; // SYMBOLE:STRATEGIE separes par des virgules
input string InpSymbolSuffix = "";        // Suffixe des symboles chez ton broker (ex : ".m"), vide sinon

input group "=== Risque ==="
input double InpRiskMoney        = 200.0; // Risque par trade a l'ACHAT (dans la devise du compte, 200 = 200 EUR ; choix d'aurele le 03/11/2026)
input double InpShortFactor      = 1.0;   // Risque a la VENTE = ce facteur x InpRiskMoney (1 = 200 EUR comme l'achat, 0 = pas de vente)
input double InpMaxDailyLossMoney= 600.0; // Plus aucune entree si la journee perd plus que ce montant (3 x le risque par trade)
input double InpMaxDrawdownPct   = 20.0;  // Coupe-circuit : baisse max depuis le plus haut du capital (%)
input bool   InpTrendFilter      = true;  // Correctif tendance (ne pas desactiver : c'est lui qui corrige les pertes)
input double InpDax1BMaxRiskATR  = 0.19;  // v1.02 : DAX 1re bougie, pas de trade si le stop depasse 0,19 x ATR du jour (0 = off)
input bool   InpDax1BSkipMonday  = true;  // v1.02 : DAX 1re bougie, pas de trade le lundi
input double InpOribHalfAtR      = 0.5;   // v1.03 A : ORIB, moitie fermee a +0,5 R (0 = off)
input bool   InpOribMom5Filter   = true;  // v1.03 B : ORIB, pas de trade si l'elan sur 5 jours va contre
input double InpOrTendMaxVol     = 1.2;   // v1.03 C : ORTEND, pas de trade si ATR du jour > 1,2 x moyenne 100 jours (0 = off)
input double InpSpreadSpikeX     = 2.0;   // v1.04 D : pas d'entree si spread de la derniere bougie > 2 x mediane 20 jours (0 = off)
input double InpStMult           = 4.0;   // v1.05 F : DAXST, multiplicateur du supertrend
input double InpStStopATR        = 1.5;   // v1.05 F : DAXST, stop = 1,5 x ATR 14 des bougies 15 min
input int    InpAlarmTrades      = 60;    // v1.04 E : alarme calculee sur les N derniers trades fermes
input double InpAlarmWarnR       = -16.0; // v1.04 E : vigilance si ces trades perdent plus de 16 x le risque par trade
input double InpAlarmStopR       = -31.0; // v1.04 E : pire que tout l'historique teste (2023-2026) : revoir le bot

input group "=== Analyse du marche ==="
input string InpWatchlist        = "DE40,XAUUSD,US500,USTECH100M,US30,EURUSD,GBPUSD,XAGUSD,XTIUSD|XBRUSD|USOIL|UKOIL|WTI|BRENT"; // Marches decrits matin et soir (A|B = 1er qui existe)
input int    InpMorningHHMM      = 945;   // Heure serveur du rapport du matin (945 = 9h45)
input int    InpEveningHHMM      = 2305;  // Heure serveur du rapport du soir (2305 = 23h05)

input group "=== Divers ==="
input ulong  InpMagicBase        = 26110600; // v1.06 : numeros magiques 26110600 a 26110603 (differents de la demo v1.01 en 261103xx)
input int    InpSlippagePoints   = 30;
input bool   InpAllowRealAccount = false;    // Autoriser un compte REEL (laisser false)

#define ST_DAX1B    0
#define ST_DAXBRUIT 1
#define ST_ORIB     2
#define ST_ORTEND   3
#define ST_DAXST    4

struct Slot
  {
   string   sym;
   string   name;
   int      strat;
   ulong    magic;
   datetime lastBar;
   long     doneDay;      // jour ou la strategie a deja joue son trade (DAX1B, ORIB)
   // ORIB
   long     ibDay;
   double   ibHi, ibLo;
   int      ibSide;       // 0 = pas encore de cassure, 1 / -1 = sens de la 1re cassure
   bool     ibOrder;
   // memo pour le journal
   string   reason;       // raison d'entree du trade en cours
   string   exitReason;   // raison de la fermeture demandee par le robot
   double   riskMoney;
  };

Slot     slots[];
CTrade   trade;
double   dayStartEquity = 0.0;
long     currentDay     = -1;
double   peakEquity     = 0.0;
bool     killSwitch     = false;
datetime lastStatus     = 0;
long     morningDone    = -1;
long     eveningDone    = -1;

//+------------------------------------------------------------------+
void Log(const string msg) { PrintFormat("[DayTrader] %s", msg); }
void LogError(const string where)
  {
   PrintFormat("[DayTrader] ERREUR %s : code %d (%s) | derniere erreur %d", where, (int)trade.ResultRetcode(),
               trade.ResultRetcodeDescription(), GetLastError());
  }
long DayKey(datetime t) { return (long)(t / 86400); }
int  HHMM(datetime t) { MqlDateTime d; TimeToStruct(t, d); return d.hour * 100 + d.min; }
datetime DayStart(datetime t) { return t - (t % 86400); }
datetime AtHHMM(datetime day, int hhmm) { return DayStart(day) + (hhmm / 100) * 3600 + (hhmm % 100) * 60; }

int StratCode(const string s)
  {
   if(s == "DAX1B")    return ST_DAX1B;
   if(s == "DAXBRUIT") return ST_DAXBRUIT;
   if(s == "ORIB")     return ST_ORIB;
   if(s == "ORTEND")   return ST_ORTEND;
   if(s == "DAXST")    return ST_DAXST;
   return -1;
  }

//+------------------------------------------------------------------+
//| Indicateurs (identiques au backtest Python)                        |
//+------------------------------------------------------------------+
double WilderATR(const string sym, ENUM_TIMEFRAMES tf, int n, int shift)
  {
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int cnt = n * 10 + 1;
   if(CopyRates(sym, tf, shift, cnt, r) != cnt)
      return 0.0;
   double a = 0;
   for(int k = 1; k < cnt; k++)
     {
      double pc = r[k - 1].close;
      double tr = MathMax(r[k].high - r[k].low, MathMax(MathAbs(r[k].high - pc), MathAbs(r[k].low - pc)));
      a = (k == 1) ? tr : a + (tr - a) / n;
     }
   return a;
  }

// v1.03 C : ATR 14 jours d'hier / moyenne des ATR des 100 jours d'avant (identique au backtest)
double AtrRel100(const string sym)
  {
   int n = 14, keep = 101, cnt = keep + n * 10 + 1;
   MqlRates r[];
   ArraySetAsSeries(r, false);
   if(CopyRates(sym, PERIOD_D1, 1, cnt, r) != cnt)
      return 0.0;
   double a = 0;
   double v[];
   ArrayResize(v, cnt);
   for(int k = 1; k < cnt; k++)
     {
      double pc = r[k - 1].close;
      double tr = MathMax(r[k].high - r[k].low, MathMax(MathAbs(r[k].high - pc), MathAbs(r[k].low - pc)));
      a = (k == 1) ? tr : a + (tr - a) / n;
      v[k] = a;
     }
   double s = 0;
   for(int k = cnt - 101; k < cnt - 1; k++) s += v[k];   // ATR d'il y a 2 a 101 jours
   double m = s / 100.0;
   return m > 0 ? v[cnt - 1] / m : 0.0;
  }

double SmaD1(const string sym, int n, int shift)
  {
   double c[];
   if(CopyClose(sym, PERIOD_D1, shift, n, c) != n)
      return 0.0;
   double s = 0;
   for(int k = 0; k < n; k++) s += c[k];
   return s / n;
  }

// +1 si la cloture d'hier est au-dessus de sa moyenne 20 jours, -1 sinon, 0 si inconnu
int Trend(const string sym)
  {
   double ma = SmaD1(sym, 20, 1), c1 = iClose(sym, PERIOD_D1, 1);
   if(ma <= 0 || c1 <= 0)
      return 0;
   return c1 > ma ? 1 : -1;
  }

bool SideAllowed(const string sym, int side)
  {
   if(side < 0 && InpShortFactor <= 0)
      return false;
   if(!InpTrendFilter)
      return true;
   return Trend(sym) == side;
  }

// Bougie M15 qui commence exactement a 'hhmm' le jour 'day' : index (shift) ou -1
int BarAt(const string sym, datetime day, int hhmm)
  {
   return iBarShift(sym, PERIOD_M15, AtHHMM(day, hhmm), true);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL && !InpAllowRealAccount)
     {
      Log("Compte REEL detecte : robot bloque. Teste d'abord en demo.");
      return(INIT_FAILED);
     }
   string items[];
   int n = StringSplit(InpConfig, ',', items);
   ArrayResize(slots, 0);
   for(int i = 0; i < n; i++)
     {
      string kv[];
      string item = items[i];
      StringTrimLeft(item);
      StringTrimRight(item);
      if(StringSplit(item, ':', kv) != 2)
         continue;
      string sym = kv[0] + InpSymbolSuffix;
      int st = StratCode(kv[1]);
      if(st < 0 || !SymbolSelect(sym, true) || StringFind(sym, "JPY") >= 0)
        {
         Log("Ligne ignoree (symbole, strategie inconnue ou paire en yen) : " + item);
         continue;
        }
      Slot s;
      s.sym = sym; s.name = kv[1]; s.strat = st; s.magic = InpMagicBase + (ulong)i;
      s.lastBar = 0; s.doneDay = -1; s.ibDay = -1; s.ibHi = 0; s.ibLo = 0; s.ibSide = 0; s.ibOrder = false;
      s.reason = ""; s.exitReason = ""; s.riskMoney = 0;
      int k = ArraySize(slots);
      ArrayResize(slots, k + 1);
      slots[k] = s;
      Log(StringFormat("Actif : %s avec %s (magic %I64u)", sym, kv[1], s.magic));
     }
   if(ArraySize(slots) == 0)
      return(INIT_PARAMETERS_INCORRECT);
   ResolveWatchlist();
   FolderCreate("DayTrader", 0);
   FolderCreate("DayTrader\\outbox", 0);
   trade.SetDeviationInPoints(InpSlippagePoints);
   peakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   EventSetTimer(5);
   WriteStatus();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { EventKillTimer(); }
void OnTick()  { Run(); }
void OnTimer() { Run(); }

void Run()
  {
   UpdateGuards();
   for(int i = 0; i < ArraySize(slots); i++)
     {
      if(slots[i].strat == ST_DAX1B)         ProcessDax1B(i);
      else if(slots[i].strat == ST_DAXBRUIT) ProcessBruit(i);
      else if(slots[i].strat == ST_ORIB)     ProcessOrib(i);
      else if(slots[i].strat == ST_ORTEND)   ProcessOrTend(i);
      else                                   ProcessDaxSt(i);
     }
   MarketReports();
   if(TimeCurrent() - lastStatus >= 300)
      WriteStatus();
  }

void UpdateGuards()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   long d = DayKey(TimeCurrent());
   if(d != currentDay) { currentDay = d; dayStartEquity = eq; }
   if(eq > peakEquity) peakEquity = eq;
   if(!killSwitch && InpMaxDrawdownPct > 0 && eq < peakEquity * (1.0 - InpMaxDrawdownPct / 100.0))
     {
      killSwitch = true;
      Log(StringFormat("COUPE-CIRCUIT : baisse de plus de %.0f %% depuis le plus haut. Plus aucune entree.", InpMaxDrawdownPct));
     }
  }

bool EntriesAllowed()
  {
   if(killSwitch)
      return false;
   if(InpMaxDailyLossMoney > 0 && AccountInfoDouble(ACCOUNT_EQUITY) < dayStartEquity - InpMaxDailyLossMoney)
     {
      static long logged = -1;
      if(logged != currentDay) { logged = currentDay; Log("Perte max de la journee atteinte : plus d'entree aujourd'hui."); }
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Ordres                                                            |
//+------------------------------------------------------------------+
int SlotOfMagic(ulong magic)
  {
   for(int i = 0; i < ArraySize(slots); i++)
      if(slots[i].magic == magic)
         return i;
   return -1;
  }

ulong FindPosition(const Slot &s)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t > 0 && PositionGetString(POSITION_SYMBOL) == s.sym && (ulong)PositionGetInteger(POSITION_MAGIC) == s.magic)
         return t;
     }
   return 0;
  }

int CountPending(const Slot &s)
  {
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t > 0 && OrderGetString(ORDER_SYMBOL) == s.sym && (ulong)OrderGetInteger(ORDER_MAGIC) == s.magic)
         c++;
     }
   return c;
  }

void DeletePending(const Slot &s)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t > 0 && OrderGetString(ORDER_SYMBOL) == s.sym && (ulong)OrderGetInteger(ORDER_MAGIC) == s.magic)
         if(!trade.OrderDelete(t))
            LogError("suppression ordre " + s.sym);
     }
  }

// Lot pour perdre 'money' (devise du compte) si le prix parcourt 'dist'
double LotsForMoney(const string sym, double dist, double money)
  {
   double tickSize = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0 || dist <= 0 || money <= 0)
      return 0.0;
   double lots = money / (dist / tickSize * tickValue);
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = 0.01;
   lots = MathFloor(lots / step) * step;
   if(lots < vmin)
     {
      Log(StringFormat("%s : risque trop petit pour le lot minimum, trade ignore.", sym));
      return 0.0;
     }
   lots = MathMin(lots, vmax);
   int d = (int)MathMax(0, MathCeil(-MathLog10(step)));
   return NormalizeDouble(lots, d);
  }

double RiskFor(int side) { return side > 0 ? InpRiskMoney : InpRiskMoney * InpShortFactor; }

// v1.04 D : ecart de la derniere bougie fermee compare a sa mediane sur 20 jours (bougies 15 min)
bool SpreadSpikeOk(const string sym)
  {
   if(InpSpreadSpikeX <= 0)
      return true;
   int sp[];
   int n = CopySpread(sym, PERIOD_M15, 1, 20 * 96, sp);
   if(n < 96)
      return true;
   int last = sp[n - 1];
   int srt[];
   ArrayCopy(srt, sp);
   ArraySort(srt);
   double med = (n % 2 == 1) ? srt[n / 2] : 0.5 * (srt[n / 2 - 1] + srt[n / 2]);
   if(med <= 0)
      return true;
   if(last > InpSpreadSpikeX * med)
     {
      Log(StringFormat("%s : ecart achat/vente anormal (%d points, normale %.0f), pas d'entree (garde-fou v1.04).", sym, last, med));
      return false;
     }
   return true;
  }

bool Spreadok(const string sym, double riskDist)
  {
   if(!SpreadSpikeOk(sym))
      return false;
   double spread = SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID);
   if(spread > 0.15 * riskDist)
     {
      Log(sym + " : spread trop large par rapport au stop, trade ignore.");
      return false;
     }
   return true;
  }

// 1 R = riskDist ; le stop est pose a slMult x riskDist (1 en general)
bool OpenMarket(Slot &s, int side, double riskDist, double slMult, double tpPrice, const string reason)
  {
   if(!EntriesAllowed() || !Spreadok(s.sym, riskDist))
      return false;
   double money = RiskFor(side);
   double lots = LotsForMoney(s.sym, riskDist, money);
   if(lots <= 0)
      return false;
   int digits = (int)SymbolInfoInteger(s.sym, SYMBOL_DIGITS);
   double price = side > 0 ? SymbolInfoDouble(s.sym, SYMBOL_ASK) : SymbolInfoDouble(s.sym, SYMBOL_BID);
   double sl = NormalizeDouble(price - side * slMult * riskDist, digits);
   double tp = tpPrice > 0 ? NormalizeDouble(tpPrice, digits) : 0.0;
   s.reason = reason;
   s.riskMoney = money;
   trade.SetExpertMagicNumber(s.magic);
   trade.SetTypeFillingBySymbol(s.sym);
   bool ok = side > 0 ? trade.Buy(lots, s.sym, price, sl, tp, s.name) : trade.Sell(lots, s.sym, price, sl, tp, s.name);
   if(ok && (trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_PLACED))
      return true;
   LogError("ouverture " + s.name + " " + s.sym);
   return false;
  }

void ClosePos(Slot &s, ulong ticket, const string why)
  {
   s.exitReason = why;
   trade.SetExpertMagicNumber(s.magic);
   if(!trade.PositionClose(ticket))
      LogError("fermeture " + s.name + " " + s.sym);
  }

bool NewM15Bar(Slot &s)
  {
   datetime b = iTime(s.sym, PERIOD_M15, 0);
   if(b == 0 || b == s.lastBar)
      return false;
   s.lastBar = b;
   return true;
  }

// deja un trade ouvert aujourd'hui par cette ligne (utile si le robot redemarre)
bool TradedToday(const Slot &s)
  {
   datetime now = TimeCurrent();
   if(!HistorySelect(DayStart(now), now))
      return false;
   for(int k = HistoryDealsTotal() - 1; k >= 0; k--)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d > 0 && (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) == s.magic && HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| DAX1B : sens de la 1re bougie de 15 min du DAX                     |
//+------------------------------------------------------------------+
void ProcessDax1B(int i)
  {
   string sym = slots[i].sym;
   datetime now = TimeCurrent();
   ulong pos = FindPosition(slots[i]);
   if(pos > 0 && PositionSelectByTicket(pos))
     {
      if(HHMM(now) >= 1830 || DayKey((datetime)PositionGetInteger(POSITION_TIME)) != DayKey(now))
         ClosePos(slots[i], pos, "fin de journee 18h30");
      return;
     }
   if(!NewM15Bar(slots[i]))
      return;
   long today = DayKey(now);
   if(HHMM(iTime(sym, PERIOD_M15, 0)) != 1015 || slots[i].doneDay == today)
      return;
   slots[i].doneDay = today;
   if(TradedToday(slots[i]) || HHMM(iTime(sym, PERIOD_M15, 1)) != 1000 || DayKey(iTime(sym, PERIOD_M15, 1)) != today)
      return;
   double o = iOpen(sym, PERIOD_M15, 1), c = iClose(sym, PERIOD_M15, 1);
   double hi = iHigh(sym, PERIOD_M15, 1), lo = iLow(sym, PERIOD_M15, 1);
   double dA = WilderATR(sym, PERIOD_D1, 14, 1);
   if(dA <= 0 || hi - lo < 0.05 * dA || hi - lo > 1.0 * dA)
     {
      Log("DAX1B : 1re bougie hors limites, pas de trade aujourd'hui.");
      return;
     }
   MqlDateTime dt;
   TimeToStruct(now, dt);
   if(InpDax1BSkipMonday && dt.day_of_week == 1)
     {
      Log("DAX1B : lundi, pas de trade (correctif v1.02).");
      return;
     }
   int side = c > o ? 1 : -1;
   if(!SideAllowed(sym, side))
     {
      Log(StringFormat("DAX1B : bougie %s mais tendance 20 jours contraire, pas de trade.", side > 0 ? "haussiere" : "baissiere"));
      return;
     }
   double price = side > 0 ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);
   double dist = side > 0 ? price - lo : hi - price;
   if(dist <= 0.02 * dA)
      return;
   if(InpDax1BMaxRiskATR > 0 && dist > InpDax1BMaxRiskATR * dA)
     {
      Log(StringFormat("DAX1B : 1re bougie trop grande (stop %.2f x ATR), pas de trade (correctif v1.02).", dist / dA));
      return;
     }
   OpenMarket(slots[i], side, dist, 1.0, 0.0,
              StringFormat("1re bougie %s (%.1f -> %.1f), stop de l'autre cote", side > 0 ? "haussiere" : "baissiere", o, c));
  }

//+------------------------------------------------------------------+
//| DAXBRUIT : zone de bruit du DAX                                    |
//+------------------------------------------------------------------+
#define BR_OPEN 1000
#define BR_LAST 1830

// sigma = moyenne sur les 14 dernieres seances de |cloture a 'endHHMM' / ouverture 10h00 - 1|
double NoiseSigma(const string sym, datetime today, int endHHMM)
  {
   int barStart = (endHHMM % 100 == 0) ? (endHHMM - 100 + 45) : (endHHMM - 15);
   double sum = 0;
   int found = 0, seen = 0;
   for(int dback = 1; dback <= 30 && seen < 14; dback++)
     {
      datetime day = today - dback * 86400;
      int b0 = BarAt(sym, day, BR_OPEN);
      if(b0 < 0)
         continue;      // jour sans seance
      seen++;
      int b1 = BarAt(sym, day, barStart);
      if(b1 < 0)
         continue;
      double o = iOpen(sym, PERIOD_M15, b0);
      if(o <= 0)
         continue;
      sum += MathAbs(iClose(sym, PERIOD_M15, b1) / o - 1.0);
      found++;
     }
   return found >= 10 ? sum / found : -1.0;
  }

double PrevSessionClose(const string sym, datetime today)
  {
   for(int dback = 1; dback <= 7; dback++)
     {
      int b = BarAt(sym, today - dback * 86400, 1815);
      if(b >= 0)
         return iClose(sym, PERIOD_M15, b);
     }
   return 0.0;
  }

double SessionVWAP(const string sym, datetime today)
  {
   double pv = 0, v = 0;
   for(int k = 1; k <= 60; k++)
     {
      datetime t = iTime(sym, PERIOD_M15, k);
      if(t == 0 || DayKey(t) != DayKey(today) || HHMM(t) < BR_OPEN)
         break;
      double tp = (iHigh(sym, PERIOD_M15, k) + iLow(sym, PERIOD_M15, k) + iClose(sym, PERIOD_M15, k)) / 3.0;
      double vol = (double)MathMax(1, iVolume(sym, PERIOD_M15, k));
      pv += tp * vol;
      v += vol;
     }
   return v > 0 ? pv / v : 0.0;
  }

void ProcessBruit(int i)
  {
   string sym = slots[i].sym;
   datetime now = TimeCurrent();
   ulong pos = FindPosition(slots[i]);
   if(pos > 0 && PositionSelectByTicket(pos) && DayKey((datetime)PositionGetInteger(POSITION_TIME)) != DayKey(now))
     {
      ClosePos(slots[i], pos, "securite : position d'un jour precedent");
      return;
     }
   if(!NewM15Bar(slots[i]))
      return;
   int endHHMM = HHMM(iTime(sym, PERIOD_M15, 0));       // fin de la bougie qui vient de se fermer
   if(endHHMM % 100 != 0 && endHHMM % 100 != 30)
      return;                                           // on ne decide qu'a l'heure pile et a la demie
   if(endHHMM < BR_OPEN + 30 || endHHMM > BR_LAST)
      return;
   int b0 = BarAt(sym, now, BR_OPEN);
   if(b0 < 0)
      return;
   double o = iOpen(sym, PERIOD_M15, b0);
   double pc = PrevSessionClose(sym, now);
   double sig = NoiseSigma(sym, now, endHHMM);
   double c = iClose(sym, PERIOD_M15, 1);
   double vw = SessionVWAP(sym, now);
   if(o <= 0 || pc <= 0 || sig < 0 || vw <= 0)
      return;
   double up = MathMax(o, pc) * (1 + sig), lo = MathMin(o, pc) * (1 - sig);
   bool last = endHHMM >= BR_LAST;

   if(pos > 0 && PositionSelectByTicket(pos))
     {
      bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      if(last)
        {
         ClosePos(slots[i], pos, "fin de seance 18h30");
         return;
        }
      if(isBuy && c < MathMax(up, vw))
         ClosePos(slots[i], pos, "retour dans la zone de bruit ou sous la VWAP");
      else if(!isBuy && c > MathMin(lo, vw))
         ClosePos(slots[i], pos, "retour dans la zone de bruit ou au-dessus de la VWAP");
      else
         return;
      pos = 0;
     }
   if(last)
      return;
   int side = (c > up && c > vw) ? 1 : ((c < lo && c < vw) ? -1 : 0);
   if(side == 0 || !SideAllowed(sym, side))
      return;
   double dA = WilderATR(sym, PERIOD_D1, 14, 1);
   double rk = MathMax(sig * o, 0.1 * dA);
   // stop de secours a 3 R : la vraie sortie se fait aux points de controle de 30 min
   OpenMarket(slots[i], side, rk, 3.0, 0.0,
              StringFormat("sortie de la zone de bruit (%s %.1f, VWAP %.1f, cloture %.1f)", side > 0 ? "haut" : "bas",
                           side > 0 ? up : lo, vw, c));
  }

//+------------------------------------------------------------------+
//| v1.03 A : ORIB, moitie fermee des que le trade gagne +0,5 R        |
//| (1 R = distance entre le prix d'entree et le stop initial).        |
//+------------------------------------------------------------------+
void OribHalf(int i, ulong pos)
  {
   if(InpOribHalfAtR <= 0 || !PositionSelectByTicket(pos))
      return;
   string sym = slots[i].sym;
   long   pid = PositionGetInteger(POSITION_IDENTIFIER);
   double op  = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl  = PositionGetDouble(POSITION_SL);
   double vol = PositionGetDouble(POSITION_VOLUME);
   int side = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
   static long donePid = -1;
   if(sl <= 0 || op <= 0 || pid == donePid)
      return;
   // deja une sortie partielle sur cette position ? (fiable meme apres un redemarrage)
   if(HistorySelectByPosition(pid))
      for(int j = 0; j < HistoryDealsTotal(); j++)
        {
         ulong d = HistoryDealGetTicket(j);
         if(d > 0 && HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_OUT)
           {
            donePid = pid;
            return;
           }
        }
   double risk = MathAbs(op - sl);
   double px = side > 0 ? SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);
   if(side * (px - op) < InpOribHalfAtR * risk)
      return;
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   if(step <= 0) step = 0.01;
   double half = MathFloor(vol / 2.0 / step + 1e-9) * step;
   if(half < vmin || vol - half < vmin)
     {
      static long warned = -1;
      if(warned != pid) { warned = pid; Log("ORIB : volume trop petit pour fermer la moitie, position gardee entiere."); }
      return;
     }
   slots[i].exitReason = StringFormat("moitie fermee a +%.1f R (correctif v1.03), le reste continue", InpOribHalfAtR);
   trade.SetExpertMagicNumber(slots[i].magic);
   if(trade.PositionClosePartial(pos, half))
      donePid = pid;
   else
     {
      slots[i].exitReason = "";
      LogError("fermeture de la moitie ORIB");
     }
  }

//+------------------------------------------------------------------+
//| ORIB : Initial Balance de l'or                                     |
//+------------------------------------------------------------------+
void ProcessOrib(int i)
  {
   string sym = slots[i].sym;
   datetime now = TimeCurrent();
   int x = HHMM(now);
   long today = DayKey(now);
   ulong pos = FindPosition(slots[i]);
   if(pos > 0)
     {
      if(CountPending(slots[i]) > 0)
         DeletePending(slots[i]);
      if(x >= 2300 || (PositionSelectByTicket(pos) && DayKey((datetime)PositionGetInteger(POSITION_TIME)) != today))
         ClosePos(slots[i], pos, "fin de journee 23h");
      else
         OribHalf(i, pos);
      return;
     }
   if(x >= 2215 && CountPending(slots[i]) > 0)
      DeletePending(slots[i]);
   if(!NewM15Bar(slots[i]))
      return;
   int bar0 = HHMM(iTime(sym, PERIOD_M15, 0));
   if(slots[i].ibDay != today)
     {
      if(bar0 < 1730 || bar0 > 2200)
         return;
      slots[i].ibDay = today;
      slots[i].ibSide = 0;
      slots[i].ibOrder = false;
      slots[i].ibHi = 0;
      if(TradedToday(slots[i]))
        {
         slots[i].doneDay = today;
         return;
        }
      double hi = -DBL_MAX, lo = DBL_MAX, op = 0;
      int n = 0;
      int hh[4] = {1630, 1645, 1700, 1715};
      for(int k = 0; k < 4; k++)
        {
         int b = BarAt(sym, now, hh[k]);
         if(b < 0) continue;
         hi = MathMax(hi, iHigh(sym, PERIOD_M15, b));
         lo = MathMin(lo, iLow(sym, PERIOD_M15, b));
         if(k == 0) op = iOpen(sym, PERIOD_M15, b);
         n++;
        }
      if(n < 3 || op <= 0 || (hi - lo) / op < 0.003 || (hi - lo) / op > 0.015)
        {
         Log("ORIB : Initial Balance absente ou hors limites (0,3 % - 1,5 %), pas de trade aujourd'hui.");
         slots[i].doneDay = today;
         return;
        }
      slots[i].ibHi = hi;
      slots[i].ibLo = lo;
      Log(StringFormat("ORIB : Initial Balance %.2f - %.2f", hi, lo));
     }
   if(slots[i].doneDay == today || slots[i].ibHi <= 0 || slots[i].ibOrder)
      return;
   if(bar0 > 2200)
      return;
   double hi = slots[i].ibHi, lo = slots[i].ibLo, w = hi - lo;
   // 1re cassure, lue sur la bougie qui vient de se fermer
   if(slots[i].ibSide == 0)
     {
      if(iHigh(sym, PERIOD_M15, 1) > hi) slots[i].ibSide = 1;
      else if(iLow(sym, PERIOD_M15, 1) < lo) slots[i].ibSide = -1;
      if(slots[i].ibSide == 0)
         return;
      if(!SideAllowed(sym, slots[i].ibSide))
        {
         Log("ORIB : 1re cassure contre la tendance 20 jours, pas de trade aujourd'hui.");
         slots[i].doneDay = today;
         return;
        }
      // v1.03 B : elan sur 5 jours (cloture d'hier - cloture d'il y a 6 jours) dans le sens du trade
      double c1 = iClose(sym, PERIOD_D1, 1), c6 = iClose(sym, PERIOD_D1, 6);
      if(InpOribMom5Filter && c1 > 0 && c6 > 0 && slots[i].ibSide * (c1 - c6) < 0)
        {
         Log("ORIB : l'elan sur 5 jours va contre la cassure, pas de trade aujourd'hui (correctif v1.03).");
         slots[i].doneDay = today;
         return;
        }
     }
   int side = slots[i].ibSide;
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double e  = side > 0 ? hi - 0.25 * w : lo + 0.25 * w;
   double sl = e - side * 0.6 * w;
   double tp = side > 0 ? hi + 0.5 * w : lo - 0.5 * w;
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK), bid = SymbolInfoDouble(sym, SYMBOL_BID);
   string why = StringFormat("cassure %s de l'Initial Balance %.2f-%.2f, entree au retour a %.2f", side > 0 ? "haussiere" : "baissiere", hi, lo, e);
   slots[i].doneDay = today;
   // le prix est deja revenu au niveau d'entree : au marche
   if((side > 0 && ask <= e) || (side < 0 && bid >= e))
     {
      double px = side > 0 ? ask : bid;
      OpenMarket(slots[i], side, MathAbs(px - sl), 1.0, tp, why);
      return;
     }
   if(!EntriesAllowed() || !Spreadok(sym, 0.6 * w))
      return;
   double lots = LotsForMoney(sym, 0.6 * w, RiskFor(side));
   if(lots <= 0)
      return;
   slots[i].reason = why;
   slots[i].riskMoney = RiskFor(side);
   trade.SetExpertMagicNumber(slots[i].magic);
   trade.SetTypeFillingBySymbol(sym);
   bool ok = side > 0 ? trade.BuyLimit(lots, NormalizeDouble(e, digits), sym, NormalizeDouble(sl, digits), NormalizeDouble(tp, digits), ORDER_TIME_GTC, 0, slots[i].name)
                      : trade.SellLimit(lots, NormalizeDouble(e, digits), sym, NormalizeDouble(sl, digits), NormalizeDouble(tp, digits), ORDER_TIME_GTC, 0, slots[i].name);
   if(ok)
     {
      slots[i].ibOrder = true;
      Log("ORIB : ordre limite pose. " + why);
     }
   else
      LogError("ordre limite ORIB");
  }

//+------------------------------------------------------------------+
//| ORTEND (v1.02) : un trade par jour sur l'or dans le sens de la     |
//| tendance 20 jours. Entree a 10h00 serveur (9h Paris), stop de      |
//| secours a 0,5 x ATR du jour, fermeture a 23h00 serveur.            |
//| Teste sur 2012-2026 : gagnant 3 periodes sur 4 (spread 0,15 $).    |
//+------------------------------------------------------------------+
void ProcessOrTend(int i)
  {
   string sym = slots[i].sym;
   datetime now = TimeCurrent();
   int x = HHMM(now);
   long today = DayKey(now);
   ulong pos = FindPosition(slots[i]);
   if(pos > 0)
     {
      if(x >= 2300 || (PositionSelectByTicket(pos) && DayKey((datetime)PositionGetInteger(POSITION_TIME)) != today))
         ClosePos(slots[i], pos, "fin de journee 23h");
      return;
     }
   if(x < 1000 || x >= 1100 || slots[i].doneDay == today)
      return;
   slots[i].doneDay = today;
   if(TradedToday(slots[i]))
      return;
   int side = Trend(sym);
   if(side == 0 || (side < 0 && InpShortFactor <= 0))
      return;
   double dA = WilderATR(sym, PERIOD_D1, 14, 1);
   if(dA <= 0)
      return;
   // v1.03 C : pas de trade si la volatilite est agitee
   double rel = AtrRel100(sym);
   if(InpOrTendMaxVol > 0 && rel > InpOrTendMaxVol)
     {
      Log(StringFormat("ORTEND : volatilite agitee (ATR = %.2f x sa moyenne 100 jours), pas de trade aujourd'hui (correctif v1.03).", rel));
      return;
     }
   OpenMarket(slots[i], side, 0.5 * dA, 1.0, 0.0,
              StringFormat("or dans le sens de la tendance 20 jours (%s), stop de secours 0,5 ATR", side > 0 ? "haussiere" : "baissiere"));
  }

//+------------------------------------------------------------------+
//| v1.05 F : supertrend du DAX en 15 min (identique a fs_robuste.py). |
//| Calcul sur les 1 500 dernieres bougies (toutes heures), ATR de     |
//| Wilder 14. dir[] : +1 tendance haussiere, -1 baissiere.            |
//| Renvoie le signal de la derniere bougie fermee (+1, -1 ou 0) et    |
//| l'ATR de cette bougie.                                             |
//+------------------------------------------------------------------+
int SuperTrendSignal(const string sym, double &atrOut)
  {
   int cnt = 1500;
   MqlRates r[];
   ArraySetAsSeries(r, false);
   if(CopyRates(sym, PERIOD_M15, 1, cnt, r) != cnt)
      return 0;
   double atr = 0, fu = 0, fd = 0, pfu = 0, pfd = 0;
   int dir = 1, pdir = 1;
   for(int k = 0; k < cnt; k++)
     {
      double tr = r[k].high - r[k].low;
      if(k > 0)
         tr = MathMax(tr, MathMax(MathAbs(r[k].high - r[k - 1].close), MathAbs(r[k].low - r[k - 1].close)));
      atr = (k == 0) ? tr : atr + (tr - atr) / 14.0;
      double hl = (r[k].high + r[k].low) / 2.0;
      double up = hl - InpStMult * atr, dn = hl + InpStMult * atr;
      pdir = dir;
      if(k == 0) { fu = up; fd = dn; pfu = fu; pfd = fd; continue; }
      pfu = fu; pfd = fd;
      fu = (r[k - 1].close > pfu) ? MathMax(up, pfu) : up;
      fd = (r[k - 1].close < pfd) ? MathMin(dn, pfd) : dn;
      if(r[k].close > pfd)      dir = 1;
      else if(r[k].close < pfu) dir = -1;
     }
   atrOut = atr;
   return dir != pdir ? dir : 0;
  }

// DAXST n'utilise PAS le filtre de tendance 20 jours (teste sans), seulement l'autorisation des ventes
bool SideAllowedNoTrend(int side) { return !(side < 0 && InpShortFactor <= 0); }

void ProcessDaxSt(int i)
  {
   string sym = slots[i].sym;
   datetime now = TimeCurrent();
   int x = HHMM(now);
   ulong pos = FindPosition(slots[i]);
   long today = DayKey(now);
   if(pos > 0 && (x >= 1830 || (PositionSelectByTicket(pos) && DayKey((datetime)PositionGetInteger(POSITION_TIME)) != today)))
     {
      ClosePos(slots[i], pos, "fin de seance 18h30");
      return;
     }
   if(!NewM15Bar(slots[i]))
      return;
   datetime b1 = iTime(sym, PERIOD_M15, 1), b0 = iTime(sym, PERIOD_M15, 0);
   if(b1 == 0 || DayKey(b1) != DayKey(b0))
      return;
   double atr = 0;
   int sig = SuperTrendSignal(sym, atr);
   if(sig == 0 || atr <= 0)
      return;
   int side = 0;
   if(pos > 0 && PositionSelectByTicket(pos))
     {
      side = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      if(sig == side)
         return;
      ClosePos(slots[i], pos, "retournement du supertrend");
     }
   int h1 = HHMM(b1), h0 = HHMM(b0);
   if(h1 < 1000 || h1 >= 1815 || h0 >= 1815)
      return;
   if(!SideAllowedNoTrend(sig))
      return;
   OpenMarket(slots[i], sig, InpStStopATR * atr, 1.0, 0.0,
              StringFormat("supertrend DAX 15 min %s (multiplicateur %.1f), stop %.1f ATR", sig > 0 ? "haussier" : "baissier", InpStMult, InpStStopATR));
  }

//+------------------------------------------------------------------+
//| Analyse du marche : fichiers lus par TradeNotifier                 |
//|                                                                    |
//| Un fichier par evenement dans MQL5\Files\DayTrader\outbox\ :       |
//|   AAAAMMJJ_HHMMSS_TYPE_POSITION.txt   (date et heure du SERVEUR)   |
//|   TYPE     = MATIN, SOIR, OUVERTURE ou FERMETURE                   |
//|   POSITION = identifiant de la position (0 pour MATIN et SOIR)     |
//| Ecrit d'abord en .tmp puis renomme en .txt (jamais lu a moitie).   |
//| Une ligne cle=valeur par donnee, point decimal, texte sans accent. |
//| Aucune notification envoyee d'ici : TradeNotifier s'en charge.     |
//+------------------------------------------------------------------+
#define OUTBOX "DayTrader\\outbox\\"

string wlSym[];    // symbole reel chez le broker
string wlKey[];    // prefixe des cles (symbole sans suffixe)

// memoire des positions ouvertes : risque et raison d'entree
long   pmId[];
double pmRisk[];
string pmWhy[];

string Num(double v, int d) { return DoubleToString(v, d); }
string Signed(double v, int d) { return (v > 0 ? "+" : "") + DoubleToString(v, d); }

string IsoTime(datetime t)
  {
   MqlDateTime d;
   TimeToStruct(t, d);
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d", d.year, d.mon, d.day, d.hour, d.min, d.sec);
  }

void KV(string &body, const string key, string val)
  {
   StringReplace(val, "\r", " ");
   StringReplace(val, "\n", " ");
   body += key + "=" + val + "\r\n";
  }

string TrendLabel(int t) { return t > 0 ? "haussiere" : (t < 0 ? "baissiere" : "inconnue"); }
string VolLabel(double rel) { return rel <= 0 ? "inconnue" : (rel < 0.85 ? "faible" : (rel > 1.2 ? "forte" : "normale")); }

string NiceName(const string key)
  {
   if(key == "DE40")       return "DAX 40";
   if(key == "XAUUSD")     return "Or";
   if(key == "XAGUSD")     return "Argent";
   if(key == "US500")      return "S&P 500";
   if(key == "USTECH100M") return "Nasdaq 100";
   if(key == "US30")       return "Dow Jones";
   if(key == "EURUSD")     return "EUR/USD";
   if(key == "GBPUSD")     return "GBP/USD";
   if(key == "XTIUSD" || key == "USOIL" || key == "WTI")    return "Petrole WTI";
   if(key == "XBRUSD" || key == "UKOIL" || key == "BRENT")  return "Petrole Brent";
   return key;
  }

// Liste a surveiller : "A,B,C1|C2" -> pour C on prend le 1er symbole qui existe chez le broker
void ResolveWatchlist()
  {
   ArrayResize(wlSym, 0);
   ArrayResize(wlKey, 0);
   string w[];
   int nw = StringSplit(InpWatchlist, ',', w);
   for(int i = 0; i < nw; i++)
     {
      string alt[];
      int na = StringSplit(w[i], '|', alt);
      for(int a = 0; a < na; a++)
        {
         string key = alt[a];
         StringTrimLeft(key);
         StringTrimRight(key);
         if(key == "" || StringFind(key, "JPY") >= 0)
            continue;
         string sym = key + InpSymbolSuffix;
         bool custom = false;
         if(!SymbolExist(sym, custom) || !SymbolSelect(sym, true))
            continue;
         int k = ArraySize(wlSym);
         ArrayResize(wlSym, k + 1);
         ArrayResize(wlKey, k + 1);
         wlSym[k] = sym;
         wlKey[k] = key;
         break;
        }
     }
   string lst = "";
   for(int i = 0; i < ArraySize(wlKey); i++)
      lst += (i > 0 ? "," : "") + wlKey[i];
   Log("Marches suivis pour l'analyse : " + lst);
  }

struct MktInfo
  {
   int    digits;
   int    trend;
   double px, varJour, var5, var20, ecart, atrPct, atrRel, hi, lo, range, rangeAtr;
  };

bool GetMkt(const string sym, MktInfo &m)
  {
   m.digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   m.px = SymbolInfoDouble(sym, SYMBOL_BID);
   double c1 = iClose(sym, PERIOD_D1, 1);
   if(m.px <= 0 || c1 <= 0)
      return false;
   double c5 = iClose(sym, PERIOD_D1, 5), c20 = iClose(sym, PERIOD_D1, 20);
   double ma = SmaD1(sym, 20, 1);
   double atr = WilderATR(sym, PERIOD_D1, 14, 1);
   double avg = 0;
   int n = 0;
   for(int k = 1; k <= 60; k++)
     {
      double h = iHigh(sym, PERIOD_D1, k), l = iLow(sym, PERIOD_D1, k);
      if(h > 0 && l > 0) { avg += h - l; n++; }
     }
   avg = n > 0 ? avg / n : 0;
   m.trend    = ma > 0 ? (c1 > ma ? 1 : -1) : 0;
   m.varJour  = (m.px / c1 - 1) * 100;
   m.var5     = c5 > 0 ? (m.px / c5 - 1) * 100 : 0;
   m.var20    = c20 > 0 ? (m.px / c20 - 1) * 100 : 0;
   m.ecart    = ma > 0 ? (m.px / ma - 1) * 100 : 0;
   m.atrPct   = atr > 0 ? atr / m.px * 100 : 0;
   m.atrRel   = (atr > 0 && avg > 0) ? atr / avg : 0;
   m.hi       = iHigh(sym, PERIOD_D1, 0);
   m.lo       = iLow(sym, PERIOD_D1, 0);
   m.range    = (m.hi > 0 && m.lo > 0) ? m.hi - m.lo : 0;
   m.rangeAtr = atr > 0 ? m.range / atr : 0;
   return true;
  }

// p = "" pour un trade, "DE40." pour un rapport ; withPrice = false pour un trade (prix = prix d'execution)
void AddMarket(string &b, const string p, const MktInfo &m, bool withPrice)
  {
   if(withPrice)
      KV(b, p + "prix", Num(m.px, m.digits));
   KV(b, p + "var_jour", Signed(m.varJour, 2));
   KV(b, p + "var_5j", Signed(m.var5, 2));
   KV(b, p + "var_20j", Signed(m.var20, 2));
   KV(b, p + "tendance20j", TrendLabel(m.trend));
   KV(b, p + "ecart_ma20_pct", Signed(m.ecart, 2));
   KV(b, p + "atr_pct", Num(m.atrPct, 2));
   KV(b, p + "atr_relatif", Num(m.atrRel, 2));
   KV(b, p + "volatilite", VolLabel(m.atrRel));
   KV(b, p + "range_jour", Num(m.range, m.digits));
   KV(b, p + "range_vs_atr", Num(m.rangeAtr, 2));
   KV(b, p + "haut_jour", Num(m.hi, m.digits));
   KV(b, p + "bas_jour", Num(m.lo, m.digits));
  }

void AddHeader(string &b, const string type, long posId)
  {
   KV(b, "type", type);
   KV(b, "heure_serveur", IsoTime(TimeCurrent()));
   KV(b, "heure_paris", IsoTime(TimeLocal()));
   KV(b, "position", IntegerToString(posId));
   KV(b, "robot", "DayTrader_MT5");
   KV(b, "devise", AccountInfoString(ACCOUNT_CURRENCY));
  }

bool OutboxWrite(const string type, long posId, const string body)
  {
   if(MQLInfoInteger(MQL_TESTER))
      return false;
   datetime t = TimeCurrent();
   string name = "";
   for(int k = 0; k < 60; k++)
     {
      MqlDateTime d;
      TimeToStruct(t + k, d);   // si le nom existe deja, on decale d'une seconde
      name = StringFormat("%s%04d%02d%02d_%02d%02d%02d_%s_%I64d", OUTBOX, d.year, d.mon, d.day, d.hour, d.min, d.sec, type, posId);
      if(!FileIsExist(name + ".txt") && !FileIsExist(name + ".tmp"))
         break;
     }
   int f = FileOpen(name + ".tmp", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(f == INVALID_HANDLE)
     {
      Log(StringFormat("outbox : impossible d'ecrire %s.tmp (erreur %d)", name, GetLastError()));
      return false;
     }
   FileWriteString(f, body);
   FileClose(f);
   if(!FileMove(name + ".tmp", 0, name + ".txt", FILE_REWRITE))
     {
      Log(StringFormat("outbox : impossible de renommer %s.tmp (erreur %d)", name, GetLastError()));
      return false;
     }
   return true;
  }

//--- bilan du jour du robot (trades fermes aujourd'hui, heure serveur)
struct DayStats
  {
   int    n, wins, losses;
   double pnl;
   double perSlot[];
   int    nSlot[];
  };

void ComputeDayStats(DayStats &s)
  {
   s.n = 0; s.wins = 0; s.losses = 0; s.pnl = 0;
   ArrayResize(s.perSlot, ArraySize(slots));
   ArrayResize(s.nSlot, ArraySize(slots));
   ArrayInitialize(s.perSlot, 0.0);
   ArrayInitialize(s.nSlot, 0);
   datetime now = TimeCurrent();
   if(!HistorySelect(DayStart(now), now + 60))
      return;
   for(int k = 0; k < HistoryDealsTotal(); k++)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d == 0)
         continue;
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e != DEAL_ENTRY_OUT && e != DEAL_ENTRY_OUT_BY)
         continue;
      int i = SlotOfMagic((ulong)HistoryDealGetInteger(d, DEAL_MAGIC));
      if(i < 0)
         continue;
      double p = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
      s.n++;
      s.pnl += p;
      if(p >= 0) s.wins++; else s.losses++;
      s.perSlot[i] += p;
      s.nSlot[i]++;
     }
  }

void AddDayStats(string &b)
  {
   DayStats s;
   ComputeDayStats(s);
   KV(b, "trades_fermes_jour", IntegerToString(s.n));
   KV(b, "gagnants_jour", IntegerToString(s.wins));
   KV(b, "perdants_jour", IntegerToString(s.losses));
   KV(b, "resultat_bot_jour", Signed(s.pnl, 2));
   for(int i = 0; i < ArraySize(slots); i++)
      KV(b, "bilan." + slots[i].name, StringFormat("%d trade(s), %s", s.nSlot[i], Signed(s.perSlot[i], 2)));
   KV(b, "capital", Num(AccountInfoDouble(ACCOUNT_EQUITY), 2));
   KV(b, "variation_capital_jour", Signed(AccountInfoDouble(ACCOUNT_EQUITY) - dayStartEquity, 2));
   KV(b, "coupe_circuit", killSwitch ? "OUI" : "non");
  }

string PlanText(const Slot &s)
  {
   if(!InpTrendFilter)
      return "achats et ventes autorises";
   int t = Trend(s.sym);
   if(t > 0)
      return StringFormat("achats seulement (tendance 20 jours haussiere), risque %.0f %s", RiskFor(1), AccountInfoString(ACCOUNT_CURRENCY));
   if(t < 0)
      return InpShortFactor > 0 ? StringFormat("ventes seulement (tendance 20 jours baissiere), risque %.0f %s", RiskFor(-1), AccountInfoString(ACCOUNT_CURRENCY))
                                : "aucun trade (tendance baissiere et ventes desactivees)";
   return "tendance inconnue, pas de trade";
  }

void MarketReports()
  {
   if(MQLInfoInteger(MQL_TESTER))
      return;
   datetime now = TimeCurrent();
   long today = DayKey(now);
   MqlDateTime d;
   TimeToStruct(now, d);
   if(d.day_of_week == 0 || d.day_of_week == 6)
      return;
   int x = HHMM(now);
   string type = "";
   if(x >= InpMorningHHMM && x < InpMorningHHMM + 100 && morningDone != today) { type = "MATIN"; morningDone = today; }
   else if(x >= InpEveningHHMM && eveningDone != today)                        { type = "SOIR";  eveningDone = today; }
   if(type == "")
      return;
   string b = "";
   AddHeader(b, type, 0);
   string lst = "";
   string up = "", dn = "";
   double vUp = -DBL_MAX, vDn = DBL_MAX;
   string body = "";
   for(int i = 0; i < ArraySize(wlSym); i++)
     {
      MktInfo m;
      if(!GetMkt(wlSym[i], m))
         continue;
      lst += (lst == "" ? "" : ",") + wlKey[i];
      KV(body, wlKey[i] + ".nom", NiceName(wlKey[i]));
      AddMarket(body, wlKey[i] + ".", m, true);
      if(m.varJour > vUp) { vUp = m.varJour; up = wlKey[i]; }
      if(m.varJour < vDn) { vDn = m.varJour; dn = wlKey[i]; }
     }
   KV(b, "marches", lst);
   KV(b, "plus_forte_hausse", up == "" ? "" : StringFormat("%s %s %%", up, Signed(vUp, 2)));
   KV(b, "plus_forte_baisse", dn == "" ? "" : StringFormat("%s %s %%", dn, Signed(vDn, 2)));
   b += body;
   for(int i = 0; i < ArraySize(slots); i++)
     {
      KV(b, "strategie." + slots[i].name + ".symbole", slots[i].sym);
      KV(b, "strategie." + slots[i].name + ".plan", PlanText(slots[i]));
     }
   AddDayStats(b);
   if(OutboxWrite(type, 0, b))
      Log("Rapport " + type + " depose dans MQL5\\Files\\DayTrader\\outbox");
  }

//--- memoire des positions (risque, raison d'entree)
int PosMemFind(long id)
  {
   for(int i = 0; i < ArraySize(pmId); i++)
      if(pmId[i] == id)
         return i;
   return -1;
  }

void PosMemSet(long id, double risk, const string why)
  {
   int i = PosMemFind(id);
   if(i < 0)
     {
      i = ArraySize(pmId);
      if(i >= 200)   // on garde la memoire petite
        {
         ArrayRemove(pmId, 0, 100);
         ArrayRemove(pmRisk, 0, 100);
         ArrayRemove(pmWhy, 0, 100);
         i = ArraySize(pmId);
        }
      ArrayResize(pmId, i + 1);
      ArrayResize(pmRisk, i + 1);
      ArrayResize(pmWhy, i + 1);
     }
   pmId[i] = id;
   pmRisk[i] = risk;
   pmWhy[i] = why;
  }

// valeur en devise du compte d'un ecart de prix 'dist' pour 'vol' lots
double MoneyOf(const string sym, double dist, double vol)
  {
   double ts = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE), tv = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   return (ts > 0 && tv > 0) ? dist / ts * tv * vol : 0.0;
  }

// risque initial (1 R) retrouve dans l'historique si le robot a redemarre
double RiskFromHistory(long posId, int strat, const string sym)
  {
   if(!HistorySelectByPosition(posId))
      return 0;
   for(int k = 0; k < HistoryDealsTotal(); k++)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d == 0 || HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN)
         continue;
      double sl = HistoryOrderGetDouble((ulong)HistoryDealGetInteger(d, DEAL_ORDER), ORDER_SL);
      if(sl <= 0)
         return 0;
      double r = MoneyOf(sym, MathAbs(HistoryDealGetDouble(d, DEAL_PRICE) - sl), HistoryDealGetDouble(d, DEAL_VOLUME));
      return strat == ST_DAXBRUIT ? r / 3.0 : r;   // DAXBRUIT : stop de secours a 3 R
     }
   return 0;
  }

// plus grand gain latent (fav) et plus grande perte latente (adv) en prix, a la minute pres
void Excursion(const string sym, int side, double entry, datetime t0, datetime t1, double &fav, double &adv)
  {
   fav = 0;
   adv = 0;
   MqlRates r[];
   int n = CopyRates(sym, PERIOD_M1, t0, t1, r);
   for(int k = 0; k < n; k++)
     {
      if(side > 0) { fav = MathMax(fav, r[k].high - entry); adv = MathMax(adv, entry - r[k].low); }
      else         { fav = MathMax(fav, entry - r[k].low);  adv = MathMax(adv, r[k].high - entry); }
     }
  }

string SideText(int side) { return side > 0 ? "achat" : "vente"; }

// journal cumule (une ligne par trade ferme) : DayTrader\journal.csv
void AppendJournal(const string line)
  {
   string file = "DayTrader\\journal.csv";
   bool exists = FileIsExist(file);
   int f = FileOpen(file, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(f == INVALID_HANDLE)
      return;
   if(!exists)
      FileWriteString(f, "ouverture_serveur;fermeture_serveur;fermeture_paris;position;strategie;symbole;sens;lots;prix_entree;prix_sortie;risque;resultat;resultat_R;mfe;mae;duree_min;tendance20j;raison_entree;raison_sortie\r\n");
   FileSeek(f, 0, SEEK_END);
   FileWriteString(f, line + "\r\n");
   FileClose(f);
  }

//+------------------------------------------------------------------+
//| v1.04 E : alarme de degradation. Somme des N derniers trades       |
//| fermes (toutes les lignes du robot), comparee au risque par trade. |
//| Le texte est ajoute a la raison de sortie, donc il arrive dans la  |
//| notification de TradeNotifier. Le robot NE s'arrete PAS seul : le  |
//| coupe-circuit apres pertes a ete teste et rejete (03/11/2026).     |
//+------------------------------------------------------------------+
string Degradation()
  {
   if(InpAlarmTrades <= 0 || InpRiskMoney <= 0)
      return "";
   datetime now = TimeCurrent();
   if(!HistorySelect(now - 400 * 86400, now + 60))
      return "";
   long ids[];
   double pnl[];
   int n = 0;
   for(int j = HistoryDealsTotal() - 1; j >= 0; j--)
     {
      ulong d = HistoryDealGetTicket(j);
      if(d == 0 || SlotOfMagic((ulong)HistoryDealGetInteger(d, DEAL_MAGIC)) < 0)
         continue;
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e != DEAL_ENTRY_OUT && e != DEAL_ENTRY_OUT_BY)
         continue;
      long id = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      double p = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
      int f = -1;
      for(int q = 0; q < n; q++) if(ids[q] == id) { f = q; break; }
      if(f >= 0) { pnl[f] += p; continue; }
      if(n >= InpAlarmTrades) continue;
      ArrayResize(ids, n + 1); ArrayResize(pnl, n + 1);
      ids[n] = id; pnl[n] = p; n++;
     }
   if(n < InpAlarmTrades)
      return "";
   double sum = 0;
   for(int q = 0; q < n; q++) sum += pnl[q];
   if(sum < InpAlarmStopR * InpRiskMoney)
     {
      Log(StringFormat("ALERTE : les %d derniers trades font %.0f, pire que tout l'historique teste.", n, sum));
      return StringFormat(" | ALERTE BOT : les %d derniers trades font %.0f (pire que tout l'historique teste). Il faut revoir le bot.", n, sum);
     }
   if(sum < InpAlarmWarnR * InpRiskMoney)
      return StringFormat(" | VIGILANCE : les %d derniers trades font %.0f (moins bien que 95 %% du passe teste).", n, sum);
   return "";
  }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal))
      return;
   ulong magic = (ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   int k = SlotOfMagic(magic);
   if(k < 0)
      return;
   long   entry  = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   long   type   = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   long   posId  = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   long   dreas  = HistoryDealGetInteger(trans.deal, DEAL_REASON);
   double vol    = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double px     = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   double pnl    = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_SWAP) + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   datetime tDeal = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
   string sym = slots[k].sym;
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   MktInfo m;
   bool mk = GetMkt(sym, m);

   string b = "";
   if(entry == DEAL_ENTRY_IN)
     {
      int side = type == DEAL_TYPE_BUY ? 1 : -1;
      double sl = 0, tp = 0;
      if(PositionSelectByTicket((ulong)posId)) { sl = PositionGetDouble(POSITION_SL); tp = PositionGetDouble(POSITION_TP); }
      string why = slots[k].reason != "" ? slots[k].reason : "inconnue (robot redemarre)";
      double risk = sl > 0 ? MoneyOf(sym, MathAbs(px - sl), vol) / (slots[k].strat == ST_DAXBRUIT ? 3.0 : 1.0) : slots[k].riskMoney;
      PosMemSet(posId, risk, why);
      AddHeader(b, "OUVERTURE", posId);
      KV(b, "symbole", sym);
      KV(b, "nom", NiceName(StringSubstr(sym, 0, StringLen(sym) - StringLen(InpSymbolSuffix))));
      KV(b, "sens", SideText(side));
      KV(b, "strategie", slots[k].name);
      KV(b, "magic", IntegerToString((long)magic));
      KV(b, "lots", Num(vol, 2));
      KV(b, "prix", Num(px, digits));
      KV(b, "stop", sl > 0 ? Num(sl, digits) : "");
      KV(b, "objectif", tp > 0 ? Num(tp, digits) : "aucun (sortie par la strategie)");
      KV(b, "risque", Num(risk, 2));
      KV(b, "raison_entree", why);
      if(mk)
         AddMarket(b, "", m, false);
      AddDayStats(b);
      OutboxWrite("OUVERTURE", posId, b);
      slots[k].reason = "";
     }
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      int side = type == DEAL_TYPE_SELL ? 1 : -1;   // fermer un achat = deal de vente
      int pm = PosMemFind(posId);
      double risk = pm >= 0 ? pmRisk[pm] : 0;
      string whyIn = pm >= 0 ? pmWhy[pm] : "inconnue (robot redemarre)";
      double entryPx = 0;
      datetime t0 = 0;
      if(HistorySelectByPosition(posId))
         for(int j = 0; j < HistoryDealsTotal(); j++)
           {
            ulong d = HistoryDealGetTicket(j);
            if(d > 0 && HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
              {
               entryPx = HistoryDealGetDouble(d, DEAL_PRICE);
               t0 = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
               break;
              }
           }
      if(risk <= 0)
         risk = RiskFromHistory(posId, slots[k].strat, sym);
      string whyOut;
      if(dreas == DEAL_REASON_SL)          whyOut = pnl >= 0 ? "stop touche (en gain)" : "stop touche";
      else if(dreas == DEAL_REASON_TP)     whyOut = "objectif atteint";
      else if(dreas == DEAL_REASON_SO)     whyOut = "stop out du compte (marge insuffisante)";
      else if(slots[k].exitReason != "")   whyOut = slots[k].exitReason;
      else                                 whyOut = "fermeture manuelle ou par le serveur";
      slots[k].exitReason = "";
      whyOut += Degradation();
      double fav = 0, adv = 0;
      if(entryPx > 0 && t0 > 0)
         Excursion(sym, side, entryPx, t0, tDeal, fav, adv);
      double mfe = MoneyOf(sym, fav, vol), mae = -MoneyOf(sym, adv, vol);
      double r = risk > 0 ? pnl / risk : 0;
      long dur = t0 > 0 ? (long)(tDeal - t0) / 60 : 0;

      AddHeader(b, "FERMETURE", posId);
      KV(b, "symbole", sym);
      KV(b, "nom", NiceName(StringSubstr(sym, 0, StringLen(sym) - StringLen(InpSymbolSuffix))));
      KV(b, "sens", SideText(side));
      KV(b, "strategie", slots[k].name);
      KV(b, "magic", IntegerToString((long)magic));
      KV(b, "lots", Num(vol, 2));
      KV(b, "prix_entree", entryPx > 0 ? Num(entryPx, digits) : "");
      KV(b, "prix", Num(px, digits));
      KV(b, "risque", Num(risk, 2));
      KV(b, "resultat", Signed(pnl, 2));
      KV(b, "resultat_R", risk > 0 ? Signed(r, 2) : "");
      KV(b, "issue", pnl > 0 ? "gagnant" : (pnl < 0 ? "perdant" : "nul"));
      KV(b, "duree_min", IntegerToString(dur));
      KV(b, "mfe", Signed(mfe, 2));
      KV(b, "mae", Signed(mae, 2));
      KV(b, "mfe_R", risk > 0 ? Signed(mfe / risk, 2) : "");
      KV(b, "mae_R", risk > 0 ? Signed(mae / risk, 2) : "");
      KV(b, "raison_entree", whyIn);
      KV(b, "raison_sortie", whyOut);
      if(mk)
         AddMarket(b, "", m, false);
      AddDayStats(b);
      OutboxWrite("FERMETURE", posId, b);
      AppendJournal(StringFormat("%s;%s;%s;%I64d;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%I64d;%s;%s;%s",
                                 t0 > 0 ? IsoTime(t0) : "", IsoTime(tDeal), IsoTime(TimeLocal()), posId, slots[k].name, sym, SideText(side),
                                 Num(vol, 2), entryPx > 0 ? Num(entryPx, digits) : "", Num(px, digits), Num(risk, 2), Num(pnl, 2),
                                 risk > 0 ? Num(r, 2) : "", Num(mfe, 2), Num(mae, 2), dur, mk ? TrendLabel(m.trend) : "", whyIn, whyOut));
     }
   WriteStatus();
  }

//+------------------------------------------------------------------+
//| etat.txt : capital, positions, protections (toutes les 5 min)      |
//+------------------------------------------------------------------+
bool EntriesAllowedQuiet()
  {
   return !killSwitch && !(InpMaxDailyLossMoney > 0 && AccountInfoDouble(ACCOUNT_EQUITY) < dayStartEquity - InpMaxDailyLossMoney);
  }

void WriteStatus()
  {
   lastStatus = TimeCurrent();
   if(MQLInfoInteger(MQL_TESTER))
      return;
   int f = FileOpen("DayTrader\\etat.txt", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(f == INVALID_HANDLE)
      return;
   string b = "";
   KV(b, "maj_serveur", IsoTime(TimeCurrent()));
   KV(b, "maj_paris", IsoTime(TimeLocal()));
   KV(b, "devise", AccountInfoString(ACCOUNT_CURRENCY));
   KV(b, "capital", Num(AccountInfoDouble(ACCOUNT_EQUITY), 2));
   KV(b, "solde", Num(AccountInfoDouble(ACCOUNT_BALANCE), 2));
   KV(b, "variation_capital_jour", Signed(AccountInfoDouble(ACCOUNT_EQUITY) - dayStartEquity, 2));
   KV(b, "plus_haut", Num(peakEquity, 2));
   KV(b, "coupe_circuit", killSwitch ? "OUI" : "non");
   KV(b, "entrees_autorisees", EntriesAllowedQuiet() ? "oui" : "NON");
   for(int i = 0; i < ArraySize(slots); i++)
     {
      ulong p = FindPosition(slots[i]);
      int dg = (int)SymbolInfoInteger(slots[i].sym, SYMBOL_DIGITS);
      if(p > 0 && PositionSelectByTicket(p))
         KV(b, "position." + slots[i].name,
            StringFormat("%s %s %.2f lot, entree %s, stop %s, objectif %s, latent %s", slots[i].sym,
                         PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "achat" : "vente", PositionGetDouble(POSITION_VOLUME),
                         Num(PositionGetDouble(POSITION_PRICE_OPEN), dg), Num(PositionGetDouble(POSITION_SL), dg),
                         Num(PositionGetDouble(POSITION_TP), dg), Signed(PositionGetDouble(POSITION_PROFIT), 2)));
      else
         KV(b, "position." + slots[i].name, slots[i].sym + " aucune");
     }
   FileWriteString(f, b);
   FileClose(f);
  }
//+------------------------------------------------------------------+
