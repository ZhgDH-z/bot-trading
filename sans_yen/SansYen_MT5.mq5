//+------------------------------------------------------------------+
//|                                                  SansYen_MT5.mq5 |
//|  Bot multi-marches SANS AUCUNE paire en yen (projet aurele).      |
//|  Un seul robot pose sur UN graphique gere tous les marches.        |
//|                                                                    |
//|  Strategies (code a mettre dans InpConfig, SYMBOLE:STRATEGIE) :    |
//|   ASIE  : retour a la moyenne en H1 pendant la session asiatique   |
//|           (01h-07h serveur). Si la cloture s'ecarte de plus de     |
//|           2 ecarts-types de sa moyenne 20, on joue le retour.      |
//|           Sortie au retour a la moyenne ou a 10h. Stop 2 ATR H1.   |
//|   DIP   : indices. Achat sur repli en journalier : cloture > MM200 |
//|           et RSI(2) < 25. Sortie quand la cloture repasse au-dessus|
//|           de la MM5 ou apres 10 jours. Stop 3 ATR(20) journalier.  |
//|   REPLI : indices. Pendant la seance US (17h-20h serveur), si      |
//|           l'indice est tombe d'une demi-ATR journaliere sous son   |
//|           ouverture, achat, sortie a 23h. Stop 0,6 ATR journalier. |
//|   DONCH : tendance. Cassure du plus haut / plus bas de 20 jours,   |
//|           stop 2 ATR(20) journalier, sortie sur le canal 10 jours. |
//|                                                                    |
//|  Module DAY TRADING (tout est ferme le jour meme) :                 |
//|   ORB30US  : cassure des 30 premieres minutes US (16h30-17h00      |
//|              serveur). Ordres stop au-dessus / en dessous jusqu'a  |
//|              20h15, stop de l'autre cote, fermeture 22h55.         |
//|   ORB15US  : sens de la 1re bougie de 15 min US (16h30-16h45),     |
//|              entree 16h45, stop de l'autre cote, fermeture 22h55.  |
//|   ORB30DAX : cassure des 30 premieres minutes du DAX (10h-10h30    |
//|              serveur), ordres jusqu'a 14h15, fermeture 18h25.      |
//|   Risque InpDayRiskPct par trade, et plus d'entree day trading     |
//|   des que les trades du jour perdent InpDayMaxLossPct.             |
//|                                                                    |
//|  Suivi : une notification sur le telephone (appli MetaTrader) a    |
//|  chaque ouverture et chaque fermeture, gagnante ou perdante, et un |
//|  journal CSV dans MQL5\Files\SansYen\ (journal.csv + etat.txt).    |
//|                                                                    |
//|  Securite : bloque sur compte REEL tant que InpAllowRealAccount    |
//|  = false.                                                          |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "2.10"
#property description "Sans yen : retour a la moyenne EURCHF (Asie), achat sur repli des indices, tendance argent"

#include <Trade/Trade.mqh>

input group "=== Marches et strategies ==="
input string InpConfig       = "EURCHF:ASIE,XAGUSD:DONCH,US30:REPLI,US500:DIP,US30:DIP,USTECH100M:DIP,DE40:DIP,US500:ORB30US,US30:ORB30US,USTECH100M:ORB30US,USTECH100M:ORB15US,DE40:ORB30DAX"; // SYMBOLE:STRATEGIE separes par des virgules
input string InpSymbolSuffix = "";       // Suffixe des symboles chez ton broker (ex : ".m"), vide sinon

input group "=== Risque ==="
input double InpRiskPct          = 0.5;  // Risque par trade forex / metaux (% du capital)
input double InpIndexRiskPct     = 1.0;  // Risque par trade indices (% du capital)
input int    InpMaxPositions     = 15;   // Nombre max de positions ouvertes en meme temps
input double InpMaxDailyLossPct  = 3.0;  // Perte max sur la journee (%) avant d'arreter les entrees
input double InpMaxDrawdownPct   = 20.0; // Baisse max depuis le plus haut (%) : coupe-circuit
input double InpDayRiskPct       = 0.1;  // Day trading : risque par trade (% du capital)
input double InpDayMaxLossPct    = 0.5;  // Day trading : plus d'entree si les trades du jour perdent ce % du capital

input group "=== Reglages des strategies (valeurs testees, ne pas changer sans retester) ==="
input double InpDipRsiLevel      = 25.0; // DIP : achat si le RSI(2) journalier est sous ce niveau
input double InpAsieZ            = 2.0;  // ASIE : ecart (en ecarts-types) pour entrer
input double InpMaxSpreadFrac    = 0.10; // Spread max = cette fraction de la distance du stop

input group "=== Suivi ==="
input bool   InpPush             = false; // Notification telephone a chaque trade (false : TradeNotifier s en charge deja)
input bool   InpJournal          = true; // Journal CSV dans MQL5\Files\SansYen\

input group "=== Divers ==="
input ulong  InpMagicBase        = 26110200; // Base des numeros magiques (un par ligne de InpConfig : 26110200, 26110201...)
input int    InpSlippagePoints   = 30;       // Glissement max (points)
input bool   InpAllowRealAccount = false;    // Autoriser un compte REEL (laisser false)

#define ST_ASIE  0
#define ST_DIP   1
#define ST_REPLI 2
#define ST_DONCH 3
#define ST_ORB30US  4
#define ST_ORB15US  5
#define ST_ORB30DAX 6

struct Slot
  {
   string   sym;
   string   name;
   int      strat;
   bool     isIndex;
   ulong    magic;
   datetime lastBar;
   long     lastSetupDay;
  };

Slot     slots[];
CTrade   trade;
double   dayStartEquity = 0.0;
long     currentDay     = -1;
double   peakEquity     = 0.0;
bool     killSwitch     = false;
datetime lastStatus     = 0;
double   dtPnlToday     = 0.0;   // resultat des trades day trading fermes aujourd'hui
long     dtDay          = -1;

//+------------------------------------------------------------------+
void Log(const string msg) { PrintFormat("[SansYen] %s", msg); }

void LogError(const string where)
  {
   PrintFormat("[SansYen] ERREUR %s : code %d (%s) | derniere erreur %d",
               where, (int)trade.ResultRetcode(), trade.ResultRetcodeDescription(), GetLastError());
  }

long DayKey(datetime t) { return (long)(t / 86400); }

bool IsDayTrade(int st) { return st == ST_ORB30US || st == ST_ORB15US || st == ST_ORB30DAX; }

int HHMM(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return dt.hour * 100 + dt.min;
  }

int HourOf(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return dt.hour;
  }

int StratCode(const string s)
  {
   if(s == "ASIE")  return ST_ASIE;
   if(s == "DIP")   return ST_DIP;
   if(s == "REPLI") return ST_REPLI;
   if(s == "DONCH") return ST_DONCH;
   if(s == "ORB30US")  return ST_ORB30US;
   if(s == "ORB15US")  return ST_ORB15US;
   if(s == "ORB30DAX") return ST_ORB30DAX;
   return -1;
  }

bool LooksLikeIndex(const string sym)
  {
   string s = sym;
   StringToUpper(s);
   return StringFind(s, "US500") >= 0 || StringFind(s, "US30") >= 0 || StringFind(s, "USTEC") >= 0 ||
          StringFind(s, "DE40") >= 0 || StringFind(s, "NAS") >= 0 || StringFind(s, "SPX") >= 0 ||
          StringFind(s, "GER") >= 0;
  }

//+------------------------------------------------------------------+
//| Indicateurs calcules a la main (identiques au backtest Python)     |
//+------------------------------------------------------------------+
// ATR de Wilder (moyenne exponentielle 1/n) de la bougie 'shift'
double WilderATR(const string sym, ENUM_TIMEFRAMES tf, int n, int shift)
  {
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int cnt = n * 10 + 1;
   if(CopyRates(sym, tf, shift, cnt, r) != cnt)
      return 0.0;
   double a = r[1].high - r[1].low;
   for(int k = 1; k < cnt; k++)
     {
      double pc = r[k - 1].close;
      double tr = MathMax(r[k].high - r[k].low, MathMax(MathAbs(r[k].high - pc), MathAbs(r[k].low - pc)));
      a = (k == 1) ? tr : a + (tr - a) / n;
     }
   return a;
  }

bool SmaStd(const string sym, ENUM_TIMEFRAMES tf, int n, int shift, double &mean, double &sd)
  {
   double c[];
   if(CopyClose(sym, tf, shift, n, c) != n)
      return false;
   mean = 0;
   for(int k = 0; k < n; k++) mean += c[k];
   mean /= n;
   double v = 0;
   for(int k = 0; k < n; k++) v += (c[k] - mean) * (c[k] - mean);
   sd = MathSqrt(v / (n - 1));
   return true;
  }

double Sma(const string sym, ENUM_TIMEFRAMES tf, int n, int shift)
  {
   double m, s;
   if(n < 2)
      return iClose(sym, tf, shift);
   if(!SmaStd(sym, tf, n, shift, m, s))
      return 0.0;
   return m;
  }

// RSI de Wilder sur n periodes, bougie 'shift'
double WilderRSI(const string sym, ENUM_TIMEFRAMES tf, int n, int shift)
  {
   double c[];
   ArraySetAsSeries(c, false);
   int cnt = 100;
   if(CopyClose(sym, tf, shift, cnt, c) != cnt)
      return 50.0;
   double up = 0, dn = 0;
   for(int k = 1; k < cnt; k++)
     {
      double d = c[k] - c[k - 1];
      double u = d > 0 ? d : 0, w = d < 0 ? -d : 0;
      if(k == 1) { up = u; dn = w; }
      else { up += (u - up) / n; dn += (w - dn) / n; }
     }
   if(dn == 0)
      return 100.0;
   return 100.0 - 100.0 / (1.0 + up / dn);
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
        {
         Log("Element de configuration ignore : " + item);
         continue;
        }
      string sym = kv[0] + InpSymbolSuffix;
      int st = StratCode(kv[1]);
      if(st < 0 || !SymbolSelect(sym, true))
        {
         Log("Symbole ou strategie inconnu(e) : " + item);
         continue;
        }
      if(StringFind(sym, "JPY") >= 0)
        {
         Log("Paire en yen refusee (bot sans yen) : " + item);
         continue;
        }
      Slot s;
      s.sym = sym;
      s.name = kv[1];
      s.strat = st;
      s.isIndex = (st == ST_DIP || st == ST_REPLI) || LooksLikeIndex(sym);
      s.magic = InpMagicBase + (ulong)i;
      s.lastBar = 0;
      s.lastSetupDay = -1;
      int k = ArraySize(slots);
      ArrayResize(slots, k + 1);
      slots[k] = s;
      Log(StringFormat("Actif : %s avec %s (magic %I64u)", sym, kv[1], s.magic));
     }
   if(ArraySize(slots) == 0)
     {
      Log("Aucun marche valide dans InpConfig.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   trade.SetDeviationInPoints(InpSlippagePoints);
   peakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   EventSetTimer(5);
   Notify(StringFormat("SansYen demarre sur %s : %d lignes actives.", AccountInfoString(ACCOUNT_SERVER), ArraySize(slots)));
   WriteStatus();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { EventKillTimer(); }
void OnTick()  { Run(); }
void OnTimer() { Run(); }

void Run()
  {
   UpdateRiskGuards();
   for(int i = 0; i < ArraySize(slots); i++)
     {
      switch(slots[i].strat)
        {
         case ST_ASIE:  ProcessAsie(i);  break;
         case ST_DIP:   ProcessDip(i);   break;
         case ST_REPLI: ProcessRepli(i); break;
         case ST_DONCH: ProcessDonch(i); break;
         default:       ProcessOrb(i);   break;
        }
     }
   if(TimeCurrent() - lastStatus >= 300)
      WriteStatus();
  }

void UpdateRiskGuards()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   long d = DayKey(TimeCurrent());
   if(d != currentDay)
     {
      currentDay = d;
      dayStartEquity = eq;
     }
   if(eq > peakEquity)
      peakEquity = eq;
   if(!killSwitch && InpMaxDrawdownPct > 0 && eq < peakEquity * (1.0 - InpMaxDrawdownPct / 100.0))
     {
      killSwitch = true;
      Log("COUPE-CIRCUIT active.");
      Notify(StringFormat("COUPE-CIRCUIT : baisse de plus de %.0f %% depuis le plus haut. Plus aucune nouvelle entree.", InpMaxDrawdownPct));
     }
  }

bool EntriesAllowed(const string sym, double stopDist)
  {
   if(killSwitch)
      return false;
   if(InpMaxDailyLossPct > 0 && AccountInfoDouble(ACCOUNT_EQUITY) < dayStartEquity * (1.0 - InpMaxDailyLossPct / 100.0))
      return false;
   if(CountAllPositions() >= InpMaxPositions)
      return false;
   double spread = SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID);
   if(spread > InpMaxSpreadFrac * stopDist)
     {
      Log(StringFormat("%s : entree ignoree, spread trop eleve.", sym));
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Positions et ordres                                               |
//+------------------------------------------------------------------+
int SlotOfMagic(ulong magic)
  {
   for(int i = 0; i < ArraySize(slots); i++)
      if(slots[i].magic == magic)
         return i;
   return -1;
  }

int CountAllPositions()
  {
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(PositionGetTicket(i) > 0 && SlotOfMagic((ulong)PositionGetInteger(POSITION_MAGIC)) >= 0)
         c++;
   return c;
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

void DeletePending(const Slot &s)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t > 0 && OrderGetString(ORDER_SYMBOL) == s.sym && (ulong)OrderGetInteger(ORDER_MAGIC) == s.magic)
         if(!trade.OrderDelete(t))
            LogError("suppression ordre en attente " + s.sym);
     }
  }

double LotsForRisk(const Slot &s, double stopDist)
  {
   double riskPct = IsDayTrade(s.strat) ? InpDayRiskPct : (s.isIndex ? InpIndexRiskPct : InpRiskPct);
   double tickSize  = SymbolInfoDouble(s.sym, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(s.sym, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0 || stopDist <= 0)
      return 0.0;
   double lots = AccountInfoDouble(ACCOUNT_EQUITY) * riskPct / 100.0 / (stopDist / tickSize * tickValue);
   double step = SymbolInfoDouble(s.sym, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(s.sym, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(s.sym, SYMBOL_VOLUME_MAX);
   if(step <= 0)
      step = 0.01;
   lots = MathFloor(lots / step) * step;
   if(lots < vmin)
     {
      Log(StringFormat("%s : capital trop petit pour %.2f %% de risque, trade ignore.", s.sym, riskPct));
      return 0.0;
     }
   lots = MathMin(lots, vmax);
   int d = (int)MathMax(0, MathCeil(-MathLog10(step)));
   return NormalizeDouble(lots, d);
  }

bool OpenMarket(Slot &s, int side, double stopDist)
  {
   if(!EntriesAllowed(s.sym, stopDist))
      return false;
   double lots = LotsForRisk(s, stopDist);
   if(lots <= 0)
      return false;
   int digits = (int)SymbolInfoInteger(s.sym, SYMBOL_DIGITS);
   double price = side > 0 ? SymbolInfoDouble(s.sym, SYMBOL_ASK) : SymbolInfoDouble(s.sym, SYMBOL_BID);
   double sl = NormalizeDouble(price - side * stopDist, digits);
   trade.SetExpertMagicNumber(s.magic);
   trade.SetTypeFillingBySymbol(s.sym);
   bool ok = side > 0 ? trade.Buy(lots, s.sym, price, sl, 0.0, s.name) : trade.Sell(lots, s.sym, price, sl, 0.0, s.name);
   if(ok && (trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_PLACED))
      return true;
   LogError("ouverture " + s.name + " " + s.sym);
   return false;
  }

void ClosePos(Slot &s, ulong ticket, const string why)
  {
   trade.SetExpertMagicNumber(s.magic);
   if(trade.PositionClose(ticket))
      Log(StringFormat("%s %s : position fermee (%s).", s.name, s.sym, why));
   else
      LogError("fermeture " + s.name + " " + s.sym);
  }

bool NewBar(Slot &s, ENUM_TIMEFRAMES tf)
  {
   datetime bar = iTime(s.sym, tf, 0);
   if(bar == 0 || bar == s.lastBar)
      return false;
   s.lastBar = bar;
   return true;
  }

//+------------------------------------------------------------------+
//| ASIE : retour a la moyenne H1 en session asiatique                 |
//+------------------------------------------------------------------+
void ProcessAsie(int i)
  {
   if(!NewBar(slots[i], PERIOD_H1))
      return;
   string sym = slots[i].sym;
   double m, sd;
   if(!SmaStd(sym, PERIOD_H1, 20, 1, m, sd) || sd <= 0)
     {
      slots[i].lastBar = 0;
      return;
     }
   double c1 = iClose(sym, PERIOD_H1, 1);
   int hPrev = HourOf(iTime(sym, PERIOD_H1, 1));
   int hNow  = HourOf(iTime(sym, PERIOD_H1, 0));

   ulong pos = FindPosition(slots[i]);
   if(pos > 0 && PositionSelectByTicket(pos))
     {
      bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      if((isBuy && c1 >= m) || (!isBuy && c1 <= m))
         ClosePos(slots[i], pos, "retour a la moyenne");
      else if(hPrev >= 9 || hNow < hPrev)
         ClosePos(slots[i], pos, "fin de session asiatique");
      return;
     }
   if(hNow < 1 || hNow > 7)
      return;
   double z = (c1 - m) / sd;
   int side = z > InpAsieZ ? -1 : (z < -InpAsieZ ? 1 : 0);
   if(side == 0)
      return;
   double a = WilderATR(sym, PERIOD_H1, 14, 1);
   if(a > 0)
      OpenMarket(slots[i], side, 2.0 * a);
  }

//+------------------------------------------------------------------+
//| DIP : achat sur repli des indices, en journalier                   |
//+------------------------------------------------------------------+
void ProcessDip(int i)
  {
   if(!NewBar(slots[i], PERIOD_D1))
      return;
   string sym = slots[i].sym;
   double ma200 = Sma(sym, PERIOD_D1, 200, 1);
   double ma5   = Sma(sym, PERIOD_D1, 5, 1);
   double a     = WilderATR(sym, PERIOD_D1, 20, 1);
   double r2    = WilderRSI(sym, PERIOD_D1, 2, 1);
   if(ma200 <= 0 || ma5 <= 0 || a <= 0)
     {
      slots[i].lastBar = 0;
      return;
     }
   double c1 = iClose(sym, PERIOD_D1, 1);
   ulong pos = FindPosition(slots[i]);
   if(pos > 0 && PositionSelectByTicket(pos))
     {
      int held = iBarShift(sym, PERIOD_D1, (datetime)PositionGetInteger(POSITION_TIME), false);
      if(c1 > ma5)
         ClosePos(slots[i], pos, "rebond");
      else if(held >= 11)
         ClosePos(slots[i], pos, "10 jours");
      return;
     }
   if(c1 > ma200 && r2 < InpDipRsiLevel)
      OpenMarket(slots[i], 1, 3.0 * a);
  }

//+------------------------------------------------------------------+
//| REPLI : achat d'un repli intraday pendant la seance US             |
//+------------------------------------------------------------------+
void ProcessRepli(int i)
  {
   string sym = slots[i].sym;
   ulong pos = FindPosition(slots[i]);
   // securite : jamais de position REPLI gardee la nuit
   if(pos > 0 && PositionSelectByTicket(pos))
     {
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if(HourOf(TimeCurrent()) >= 23 || DayKey(TimeCurrent()) != DayKey(opened))
        {
         ClosePos(slots[i], pos, "fin de seance");
         return;
        }
     }
   if(!NewBar(slots[i], PERIOD_H1))
      return;
   if(pos > 0)
     {
      if(HourOf(iTime(sym, PERIOD_H1, 1)) >= 22)
         ClosePos(slots[i], pos, "fin de seance");
      return;
     }
   long today = DayKey(TimeCurrent());
   int hPrev = HourOf(iTime(sym, PERIOD_H1, 1));
   if(slots[i].lastSetupDay == today || hPrev < 17 || hPrev > 20 || DayKey(iTime(sym, PERIOD_H1, 1)) != today)
      return;
   double dayOpen = iOpen(sym, PERIOD_D1, 0);
   double dA = WilderATR(sym, PERIOD_D1, 14, 1);
   if(dayOpen <= 0 || dA <= 0)
      return;
   if(iClose(sym, PERIOD_H1, 1) < dayOpen - 0.5 * dA)
     {
      slots[i].lastSetupDay = today;
      OpenMarket(slots[i], 1, 0.6 * dA);
     }
  }

//+------------------------------------------------------------------+
//| DONCH : tendance, cassure 20 jours / sortie 10 jours               |
//+------------------------------------------------------------------+
void ProcessDonch(int i)
  {
   string sym = slots[i].sym;
   ulong pos = FindPosition(slots[i]);
   if(pos > 0)
      DeletePending(slots[i]); // OCO : l'ordre oppose disparait
   if(!NewBar(slots[i], PERIOD_D1))
      return;
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   int ih = iHighest(sym, PERIOD_D1, MODE_HIGH, 20, 1), il = iLowest(sym, PERIOD_D1, MODE_LOW, 20, 1);
   int oh = iHighest(sym, PERIOD_D1, MODE_HIGH, 10, 1), ol = iLowest(sym, PERIOD_D1, MODE_LOW, 10, 1);
   double a = WilderATR(sym, PERIOD_D1, 20, 1);
   if(ih < 0 || il < 0 || oh < 0 || ol < 0 || a <= 0)
     {
      slots[i].lastBar = 0;
      return;
     }
   double hi20 = iHigh(sym, PERIOD_D1, ih), lo20 = iLow(sym, PERIOD_D1, il);
   double hi10 = iHigh(sym, PERIOD_D1, oh), lo10 = iLow(sym, PERIOD_D1, ol);

   if(pos > 0 && PositionSelectByTicket(pos))
     {
      // remonte le stop sur le canal 10 jours (jamais en arriere)
      bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double sl = PositionGetDouble(POSITION_SL);
      double nsl = isBuy ? MathMax(sl, lo10) : MathMin(sl, hi10);
      double bid = SymbolInfoDouble(sym, SYMBOL_BID), ask = SymbolInfoDouble(sym, SYMBOL_ASK);
      if(isBuy && bid <= nsl)
         ClosePos(slots[i], pos, "canal 10 jours");
      else if(!isBuy && ask >= nsl)
         ClosePos(slots[i], pos, "canal 10 jours");
      else if(MathAbs(nsl - sl) > SymbolInfoDouble(sym, SYMBOL_POINT))
        {
         trade.SetExpertMagicNumber(slots[i].magic);
         if(!trade.PositionModify(pos, NormalizeDouble(nsl, digits), 0.0))
            LogError("stop DONCH " + sym);
        }
      return;
     }

   // nouveaux ordres du jour : achat au-dessus du plus haut 20 jours, vente sous le plus bas
   DeletePending(slots[i]);
   double stopDist = 2.0 * a;
   if(!EntriesAllowed(sym, stopDist))
      return;
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK), bid = SymbolInfoDouble(sym, SYMBOL_BID);
   if(ask >= hi20)
     {
      OpenMarket(slots[i], 1, stopDist);
      return;
     }
   if(bid <= lo20)
     {
      OpenMarket(slots[i], -1, stopDist);
      return;
     }
   double lots = LotsForRisk(slots[i], stopDist);
   if(lots <= 0)
      return;
   trade.SetExpertMagicNumber(slots[i].magic);
   trade.SetTypeFillingBySymbol(sym);
   double b = NormalizeDouble(hi20, digits), s = NormalizeDouble(lo20, digits);
   if(!trade.BuyStop(lots, b, sym, NormalizeDouble(b - stopDist, digits), 0.0, ORDER_TIME_GTC, 0, "DONCH"))
      LogError("BuyStop " + sym);
   if(!trade.SellStop(lots, s, sym, NormalizeDouble(s + stopDist, digits), 0.0, ORDER_TIME_GTC, 0, "DONCH"))
      LogError("SellStop " + sym);
  }

//+------------------------------------------------------------------+
//| DAY TRADING : cassure d'ouverture (ORB), ferme le jour meme        |
//+------------------------------------------------------------------+
void OrbHours(int st, int &rs, int &re, int &lastEntry, int &exitAt)
  {
   if(st == ST_ORB30DAX) { rs = 1000; re = 1015; lastEntry = 1415; exitAt = 1825; return; }
   if(st == ST_ORB15US)  { rs = 1630; re = 1630; lastEntry = 1650; exitAt = 2255; return; }
   rs = 1630; re = 1645; lastEntry = 2015; exitAt = 2255; // ORB30US
  }

// un trade day trading deja fait aujourd'hui sur cette ligne (utile si le robot redemarre)
bool TradedToday(const Slot &s)
  {
   datetime now = TimeCurrent();
   if(!HistorySelect(now - now % 86400, now))
      return false;
   for(int k = HistoryDealsTotal() - 1; k >= 0; k--)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d > 0 && (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) == s.magic &&
         HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
         return true;
     }
   return false;
  }

bool DayTradeAllowed()
  {
   long d = DayKey(TimeCurrent());
   if(d != dtDay) { dtDay = d; dtPnlToday = 0.0; }
   if(InpDayMaxLossPct > 0 && dtPnlToday < -dayStartEquity * InpDayMaxLossPct / 100.0)
      return false;
   return true;
  }

void ProcessOrb(int i)
  {
   string sym = slots[i].sym;
   int rs, re, lastEntry, exitAt;
   OrbHours(slots[i].strat, rs, re, lastEntry, exitAt);
   datetime now = TimeCurrent();
   int x = HHMM(now);
   long today = DayKey(now);
   ulong pos = FindPosition(slots[i]);

   // fermeture de fin de journee : jamais de position day trading la nuit
   if(pos > 0 && PositionSelectByTicket(pos))
     {
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if(x >= exitAt || DayKey(opened) != today)
        {
         ClosePos(slots[i], pos, "fin de journee");
         return;
        }
      DeletePending(slots[i]); // OCO : l'ordre oppose disparait
      return;
     }
   // plus d'entree apres la fenetre
   if(x > lastEntry)
     {
      DeletePending(slots[i]);
      return;
     }
   int rangeEnd = (re % 100 + 15 >= 60) ? (re / 100 + 1) * 100 + (re % 100 + 15 - 60) : re + 15;
   if(slots[i].lastSetupDay == today || x < rangeEnd)
      return;
   if(TradedToday(slots[i]))
     {
      slots[i].lastSetupDay = today;
      return;
     }

   // range des bougies M15 du jour entre rs et re
   double hi = -DBL_MAX, lo = DBL_MAX, firstOpen = 0, lastClose = 0;
   int found = 0;
   for(int k = 1; k <= 60; k++)
     {
      datetime t = iTime(sym, PERIOD_M15, k);
      if(t == 0 || DayKey(t) != today)
         break;
      int h = HHMM(t);
      if(h < rs || h > re)
         continue;
      hi = MathMax(hi, iHigh(sym, PERIOD_M15, k));
      lo = MathMin(lo, iLow(sym, PERIOD_M15, k));
      if(h == rs) firstOpen = iOpen(sym, PERIOD_M15, k);
      if(h == re) lastClose = iClose(sym, PERIOD_M15, k);
      found++;
     }
   int need = (re == rs) ? 1 : 2;
   double dA = WilderATR(sym, PERIOD_D1, 14, 1);
   if(found < need || dA <= 0 || firstOpen == 0 || lastClose == 0)
     {
      Log(StringFormat("%s %s : range d'ouverture introuvable aujourd'hui.", slots[i].name, sym));
      return;
     }
   slots[i].lastSetupDay = today; // un seul essai par jour
   double range = hi - lo;
   if(range < 0.05 * dA || range > 1.0 * dA)
     {
      Log(StringFormat("%s %s : range hors limites, pas de trade aujourd'hui.", slots[i].name, sym));
      return;
     }
   if(!DayTradeAllowed())
     {
      Log(slots[i].name + " : limite de perte day trading du jour atteinte.");
      return;
     }
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK), bid = SymbolInfoDouble(sym, SYMBOL_BID);

   if(slots[i].strat == ST_ORB15US)
     {
      // sens de la 1re bougie, entree au marche, stop de l'autre cote de la bougie
      int side = lastClose > firstOpen ? 1 : -1;
      double stopDist = side > 0 ? ask - lo : hi - bid;
      if(stopDist > 0.02 * dA)
         OpenMarket(slots[i], side, stopDist);
      return;
     }

   // ORB 30 : le prix a deja casse -> entree au marche, sinon ordres stop (OCO)
   if(ask >= hi)
     {
      OpenMarket(slots[i], 1, ask - lo);
      return;
     }
   if(bid <= lo)
     {
      OpenMarket(slots[i], -1, hi - bid);
      return;
     }
   if(!EntriesAllowed(sym, range))
      return;
   double lots = LotsForRisk(slots[i], range);
   if(lots <= 0)
      return;
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   double stopsLevel = (double)SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * point;
   double b = NormalizeDouble(hi, digits), s = NormalizeDouble(lo, digits);
   trade.SetExpertMagicNumber(slots[i].magic);
   trade.SetTypeFillingBySymbol(sym);
   if(b - ask > stopsLevel && !trade.BuyStop(lots, b, sym, s, 0.0, ORDER_TIME_GTC, 0, slots[i].name))
      LogError("BuyStop " + sym);
   if(bid - s > stopsLevel && !trade.SellStop(lots, s, sym, b, 0.0, ORDER_TIME_GTC, 0, slots[i].name))
      LogError("SellStop " + sym);
   Log(StringFormat("%s %s : ordres poses a %s / %s (%.2f lot)", slots[i].name, sym,
                    DoubleToString(b, digits), DoubleToString(s, digits), lots));
  }

//+------------------------------------------------------------------+
//| Suivi : notification + journal a chaque ouverture / fermeture      |
//+------------------------------------------------------------------+
void Notify(const string msg)
  {
   Log(msg);
   if(InpPush && !MQLInfoInteger(MQL_TESTER))
      if(!SendNotification(msg))
         Log("Notification non envoyee (MetaQuotes ID configure dans Outils > Options > Notifications ?)");
  }

void Journal(const string line)
  {
   if(!InpJournal)
      return;
   string path = "SansYen\\journal.csv";
   bool exists = FileIsExist(path);
   int f = FileOpen(path, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ';');
   if(f == INVALID_HANDLE)
      return;
   if(!exists)
      FileWrite(f, "heure_serveur", "evenement", "symbole", "strategie", "magic", "sens", "lots", "prix", "resultat", "capital");
   FileSeek(f, 0, SEEK_END);
   FileWriteString(f, line + "\r\n");
   FileClose(f);
  }

void WriteStatus()
  {
   lastStatus = TimeCurrent();
   if(!InpJournal)
      return;
   int f = FileOpen("SansYen\\etat.txt", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(f == INVALID_HANDLE)
      return;
   string cur = AccountInfoString(ACCOUNT_CURRENCY);
   FileWriteString(f, StringFormat("maj_serveur=%s\r\n", TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS)));
   FileWriteString(f, StringFormat("capital=%.2f %s\r\nsolde=%.2f %s\r\n", AccountInfoDouble(ACCOUNT_EQUITY), cur,
                                   AccountInfoDouble(ACCOUNT_BALANCE), cur));
   FileWriteString(f, StringFormat("plus_haut=%.2f\r\ncoupe_circuit=%s\r\npositions=%d\r\n", peakEquity,
                                   killSwitch ? "OUI" : "non", CountAllPositions()));
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      int k = t > 0 ? SlotOfMagic((ulong)PositionGetInteger(POSITION_MAGIC)) : -1;
      if(k < 0)
         continue;
      FileWriteString(f, StringFormat("position=%s;%s;%s;%.2f lot;ouverture %s;resultat latent %.2f\r\n",
                                      slots[k].sym, slots[k].name,
                                      PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "achat" : "vente",
                                      PositionGetDouble(POSITION_VOLUME), DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN),
                                      (int)SymbolInfoInteger(slots[k].sym, SYMBOL_DIGITS)), PositionGetDouble(POSITION_PROFIT)));
     }
   FileClose(f);
  }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal))
      return;
   ulong magic = (ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   int k = SlotOfMagic(magic);
   if(k < 0)
      return;
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   long type  = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   double vol = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double px  = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   int digits = (int)SymbolInfoInteger(slots[k].sym, SYMBOL_DIGITS);
   string cur = AccountInfoString(ACCOUNT_CURRENCY);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   string when = TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES);
   if(entry == DEAL_ENTRY_IN)
     {
      string side = type == DEAL_TYPE_BUY ? "ACHAT" : "VENTE";
      Notify(StringFormat("SansYen OUVERTURE %s %s (%s) %.2f lot a %s", side, slots[k].sym, slots[k].name, vol,
                          DoubleToString(px, digits)));
      Journal(StringFormat("%s;ouverture;%s;%s;%I64u;%s;%.2f;%s;;%.2f", when, slots[k].sym, slots[k].name, magic, side, vol,
                           DoubleToString(px, digits), bal));
     }
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double pnl = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_SWAP) +
                   HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
      string res = pnl >= 0 ? "GAGNANT" : "PERDANT";
      if(IsDayTrade(slots[k].strat))
        {
         long d = DayKey(TimeCurrent());
         if(d != dtDay) { dtDay = d; dtPnlToday = 0.0; }
         dtPnlToday += pnl;
        }
      Notify(StringFormat("SansYen FERMETURE %s %s : %s %+.2f %s | capital %.2f %s", slots[k].sym, slots[k].name, res,
                          pnl, cur, bal, cur));
      Journal(StringFormat("%s;fermeture;%s;%s;%I64u;%s;%.2f;%s;%.2f;%.2f", when, slots[k].sym, slots[k].name, magic, res, vol,
                           DoubleToString(px, digits), pnl, bal));
     }
   WriteStatus();
  }
//+------------------------------------------------------------------+
