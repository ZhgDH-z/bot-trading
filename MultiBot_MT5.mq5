//+------------------------------------------------------------------+
//|                                                 MultiBot_MT5.mq5 |
//|  Bot multi-marches, construit sur la base du premier bot          |
//|  (MA_Cross_USDJPY). Un seul robot pose sur UN graphique gere       |
//|  plusieurs marches et plusieurs strategies en meme temps.          |
//|                                                                    |
//|  Strategies disponibles (code a mettre dans InpConfig) :           |
//|   MM      : bot de la 1re video generalise. EMA 8 / SMMA 30 en H1, |
//|             achat ET vente, stop + trailing = 4 x ATR(14) H1       |
//|   MMLONG  : pareil mais achat uniquement (comme la video)          |
//|   MM200   : bot de la 2e video (Paul Bourdeau). EMA 50 / EMA 200   |
//|             H1, SL 4,5 ATR, TP 9 ATR, trailing 1,8 ATR, fermeture  |
//|             et retournement au croisement inverse                  |
//|   LONDON  : cassure de Londres. Range de la session asiatique      |
//|             (00h-09h serveur), ordres stop au-dessus / en dessous, |
//|             stop de l'autre cote du range, sortie a 23h            |
//|   DIP     : indices (US500, US30, Nasdaq). Achat sur repli en      |
//|             journalier : cloture > MM200 et RSI(2) < 10, sortie    |
//|             quand la cloture repasse au-dessus de la MM5 ou apres  |
//|             10 jours, stop 3 x ATR(20) journalier                  |
//|                                                                    |
//|  Gestion du risque : taille de lot calculee pour risquer           |
//|  InpRiskPct % du capital par trade, limite de perte journaliere,   |
//|  coupe-circuit sur la baisse maximale, nombre max de positions.    |
//|  Securite : bloque sur compte REEL tant que InpAllowRealAccount    |
//|  = false.                                                          |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.11"
#property description "Multi-marches : MM (video 1), MM200 (video 2), cassure de Londres, achat sur repli des indices"

#include <Trade/Trade.mqh>

//--- parametres
input group "=== Marches et strategies ==="
input string InpConfig       = "GBPJPY:MM,GBPUSD:MM,USDJPY:MMLONG,EURJPY:MMLONG,USDJPY:LONDON,GBPJPY:MM200,US500:DIP,US30:DIP,USTECH100M:DIP"; // SYMBOLE:STRATEGIE separes par des virgules
input string InpSymbolSuffix = "";       // Suffixe des symboles chez ton broker (ex : ".m"), vide sinon

input group "=== Risque ==="
input double InpRiskPct          = 0.5;  // Risque par trade (% du capital)
input int    InpMaxPositions     = 10;   // Nombre max de positions ouvertes en meme temps
input double InpMaxDailyLossPct  = 3.0;  // Perte max sur la journee (%) avant d'arreter les entrees
input double InpMaxDrawdownPct   = 20.0; // Baisse max depuis le plus haut (%) : coupe-circuit

input group "=== Indices (DIP) ==="
input double InpDipRiskPct       = 1.0;  // Risque par trade DIP (% du capital)
input double InpDipRsiLevel      = 10.0; // Achat si le RSI(2) journalier est sous ce niveau

input group "=== Filtres ==="
input int    InpMaxSpreadPips    = 5;    // Spread max autorise (pips, or : 1 pip = 0,10 $)
input int    InpSlippagePoints   = 30;   // Glissement max (points)

input group "=== Divers ==="
input ulong  InpMagicBase        = 26103000; // Base des numeros magiques (un par ligne de InpConfig)
input bool   InpAllowRealAccount = false;    // Autoriser un compte REEL (laisser false en test)

//--- strategies
#define ST_MM      0
#define ST_MMLONG  1
#define ST_MM200   2
#define ST_LONDON  3
#define ST_DIP     4

struct Slot
  {
   string   sym;
   int      strat;
   ulong    magic;
   int      hFast;
   int      hSlow;
   int      hAtr;
   int      hRsi;
   datetime lastBar;
   long     lastSetupDay;
  };

Slot     slots[];
CTrade   trade;
double   dayStartEquity = 0.0;
long     currentDay     = -1;
double   peakEquity     = 0.0;
bool     killSwitch     = false;

//+------------------------------------------------------------------+
void Log(const string msg) { PrintFormat("[MultiBot] %s", msg); }

void LogError(const string where)
  {
   PrintFormat("[MultiBot] ERREUR %s : code %d (%s) | derniere erreur %d",
               where, (int)trade.ResultRetcode(), trade.ResultRetcodeDescription(), GetLastError());
  }

long DayKey(datetime t) { return (long)(t / 86400); }

int ServerHour()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return dt.hour;
  }

double PipSize(const string sym)
  {
   if(StringFind(sym, "XAU") == 0)
      return 0.1; // or : 1 pip = 0,10 $
   int digits   = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   return (digits == 3 || digits == 5) ? point * 10.0 : point;
  }

int StratCode(const string s)
  {
   if(s == "MM")     return ST_MM;
   if(s == "MMLONG") return ST_MMLONG;
   if(s == "MM200")  return ST_MM200;
   if(s == "LONDON") return ST_LONDON;
   if(s == "DIP")    return ST_DIP;
   return -1;
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
      Slot s;
      s.sym = sym;
      s.strat = st;
      s.magic = InpMagicBase + (ulong)i;
      s.lastBar = 0;
      s.lastSetupDay = -1;
      s.hFast = INVALID_HANDLE;
      s.hSlow = INVALID_HANDLE;
      s.hRsi  = INVALID_HANDLE;
      if(st == ST_MM || st == ST_MMLONG)
        {
         s.hFast = iMA(sym, PERIOD_H1, 8, 0, MODE_EMA, PRICE_CLOSE);
         s.hSlow = iMA(sym, PERIOD_H1, 30, 0, MODE_SMMA, PRICE_CLOSE);
         s.hAtr  = iATR(sym, PERIOD_H1, 14);
        }
      else if(st == ST_MM200)
        {
         s.hFast = iMA(sym, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
         s.hSlow = iMA(sym, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
         s.hAtr  = iATR(sym, PERIOD_H1, 14);
        }
      else if(st == ST_DIP)
        {
         s.hFast = iMA(sym, PERIOD_D1, 5, 0, MODE_SMA, PRICE_CLOSE);
         s.hSlow = iMA(sym, PERIOD_D1, 200, 0, MODE_SMA, PRICE_CLOSE);
         s.hRsi  = iRSI(sym, PERIOD_D1, 2, PRICE_CLOSE);
         s.hAtr  = iATR(sym, PERIOD_D1, 20);
        }
      else
         s.hAtr = iATR(sym, PERIOD_D1, 14);

      if(s.hAtr == INVALID_HANDLE || (st != ST_LONDON && (s.hFast == INVALID_HANDLE || s.hSlow == INVALID_HANDLE)) ||
         (st == ST_DIP && s.hRsi == INVALID_HANDLE))
        {
         Log("Impossible de creer les indicateurs pour " + item);
         continue;
        }
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
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i = 0; i < ArraySize(slots); i++)
     {
      if(slots[i].hFast != INVALID_HANDLE) IndicatorRelease(slots[i].hFast);
      if(slots[i].hSlow != INVALID_HANDLE) IndicatorRelease(slots[i].hSlow);
      if(slots[i].hAtr  != INVALID_HANDLE) IndicatorRelease(slots[i].hAtr);
      if(slots[i].hRsi  != INVALID_HANDLE) IndicatorRelease(slots[i].hRsi);
     }
  }

void OnTick()  { Run(); }
void OnTimer() { Run(); }

//+------------------------------------------------------------------+
void Run()
  {
   UpdateRiskGuards();
   for(int i = 0; i < ArraySize(slots); i++)
     {
      if(slots[i].strat == ST_LONDON)
         ProcessLondon(i);
      else if(slots[i].strat == ST_DIP)
         ProcessDip(i);
      else
         ProcessCross(i);
     }
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
      Log(StringFormat("COUPE-CIRCUIT : baisse de plus de %.1f %% depuis le plus haut. Plus aucune nouvelle entree.",
                       InpMaxDrawdownPct));
     }
  }

// maxSpread : ecart achat/vente maximum accepte, en prix
bool EntriesAllowed(const string sym, double maxSpread)
  {
   if(killSwitch)
      return false;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(InpMaxDailyLossPct > 0 && eq < dayStartEquity * (1.0 - InpMaxDailyLossPct / 100.0))
      return false;
   if(CountAllPositions() >= InpMaxPositions)
      return false;
   double spread = SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID);
   if(spread > maxSpread)
     {
      Log(StringFormat("%s : entree ignoree, spread trop eleve.", sym));
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Positions et ordres                                               |
//+------------------------------------------------------------------+
bool IsOurMagic(ulong magic)
  {
   for(int i = 0; i < ArraySize(slots); i++)
      if(slots[i].magic == magic)
         return true;
   return false;
  }

int CountAllPositions()
  {
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(PositionGetTicket(i) > 0 && IsOurMagic((ulong)PositionGetInteger(POSITION_MAGIC)))
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
            LogError("suppression ordre en attente " + s.sym);
     }
  }

// Lot pour perdre riskPct % du capital si le stop (distance en prix) est touche.
double LotsForRisk(const string sym, double stopDist, double riskPct)
  {
   double tickSize  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0 || stopDist <= 0)
      return 0.0;
   double riskMoney  = AccountInfoDouble(ACCOUNT_EQUITY) * riskPct / 100.0;
   double lossPerLot = stopDist / tickSize * tickValue;
   double lots = riskMoney / lossPerLot;
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   if(step <= 0)
      step = 0.01;
   lots = MathFloor(lots / step) * step;
   if(lots < vmin)
     {
      Log(StringFormat("%s : capital trop petit pour respecter %.2f %% de risque, trade ignore.", sym, riskPct));
      return 0.0;
     }
   lots = MathMin(lots, vmax);
   int d = (int)MathMax(0, MathCeil(-MathLog10(step)));
   return NormalizeDouble(lots, d);
  }

// Les distances de trailing sont gardees dans le commentaire de la position : "MM|0.452"
double DistFromComment(const string comment)
  {
   int p = StringFind(comment, "|");
   if(p < 0)
      return 0.0;
   return StringToDouble(StringSubstr(comment, p + 1));
  }

bool OpenMarket(Slot &s, int side, double stopDist, double tpDist, double trailDist, const string tag)
  {
   int digits = (int)SymbolInfoInteger(s.sym, SYMBOL_DIGITS);
   double lots = LotsForRisk(s.sym, stopDist, s.strat == ST_DIP ? InpDipRiskPct : InpRiskPct);
   if(lots <= 0)
      return false;
   double price = side > 0 ? SymbolInfoDouble(s.sym, SYMBOL_ASK) : SymbolInfoDouble(s.sym, SYMBOL_BID);
   double sl = NormalizeDouble(price - side * stopDist, digits);
   double tp = tpDist > 0 ? NormalizeDouble(price + side * tpDist, digits) : 0.0;
   string comment = StringFormat("%s|%s", tag, DoubleToString(trailDist, digits));
   trade.SetExpertMagicNumber(s.magic);
   trade.SetTypeFillingBySymbol(s.sym);
   bool ok = side > 0 ? trade.Buy(lots, s.sym, price, sl, tp, comment)
                      : trade.Sell(lots, s.sym, price, sl, tp, comment);
   if(ok && (trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_PLACED))
     {
      Log(StringFormat("%s %s %s %.2f lot a %s | SL %s%s", tag, side > 0 ? "ACHAT" : "VENTE", s.sym, lots,
                       DoubleToString(trade.ResultPrice(), digits), DoubleToString(sl, digits),
                       tp > 0 ? " | TP " + DoubleToString(tp, digits) : ""));
      return true;
     }
   LogError("ouverture " + tag + " " + s.sym);
   return false;
  }

void TrailPosition(Slot &s, ulong ticket, double refBuy, double refSell, double dist)
  {
   if(dist <= 0 || !PositionSelectByTicket(ticket))
      return;
   int digits = (int)SymbolInfoInteger(s.sym, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(s.sym, SYMBOL_POINT);
   double stopsLevel = (double)SymbolInfoInteger(s.sym, SYMBOL_TRADE_STOPS_LEVEL) * point;
   double curSL = PositionGetDouble(POSITION_SL);
   double tp = PositionGetDouble(POSITION_TP);
   double step = PipSize(s.sym);
   bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
   double newSL;
   if(isBuy)
     {
      newSL = NormalizeDouble(refBuy - dist, digits);
      if(SymbolInfoDouble(s.sym, SYMBOL_BID) - newSL < stopsLevel || (curSL > 0 && newSL < curSL + step))
         return;
     }
   else
     {
      newSL = NormalizeDouble(refSell + dist, digits);
      if(newSL - SymbolInfoDouble(s.sym, SYMBOL_ASK) < stopsLevel || (curSL > 0 && newSL > curSL - step))
         return;
     }
   trade.SetExpertMagicNumber(s.magic);
   if(!trade.PositionModify(ticket, newSL, tp))
      LogError("trailing " + s.sym);
  }

//+------------------------------------------------------------------+
//| MM / MMLONG / MM200 : croisements de moyennes mobiles en H1        |
//+------------------------------------------------------------------+
void ProcessCross(int i)
  {
   ulong pos = FindPosition(slots[i]);

   // MM : trailing continu (comme le premier bot), distance gardee dans le commentaire
   if(pos > 0 && slots[i].strat != ST_MM200 && PositionSelectByTicket(pos))
      TrailPosition(slots[i], pos, SymbolInfoDouble(slots[i].sym, SYMBOL_BID),
                    SymbolInfoDouble(slots[i].sym, SYMBOL_ASK), DistFromComment(PositionGetString(POSITION_COMMENT)));

   datetime bar = iTime(slots[i].sym, PERIOD_H1, 0);
   if(bar == 0 || bar == slots[i].lastBar)
      return;
   slots[i].lastBar = bar;

   double f[], s[], a[];
   ArraySetAsSeries(f, true);
   ArraySetAsSeries(s, true);
   ArraySetAsSeries(a, true);
   if(CopyBuffer(slots[i].hFast, 0, 1, 2, f) != 2 || CopyBuffer(slots[i].hSlow, 0, 1, 2, s) != 2 ||
      CopyBuffer(slots[i].hAtr, 0, 1, 1, a) != 1)
     {
      Log("Donnees indicateurs indisponibles pour " + slots[i].sym);
      slots[i].lastBar = 0;
      return;
     }
   bool up = f[0] > s[0] && f[1] <= s[1];
   bool dn = f[0] < s[0] && f[1] >= s[1];

   if(slots[i].strat == ST_MM200)
     {
      // trailing sur la cloture de la bougie precedente
      if(pos > 0 && PositionSelectByTicket(pos))
        {
         double c1 = iClose(slots[i].sym, PERIOD_H1, 1);
         TrailPosition(slots[i], pos, c1, c1, DistFromComment(PositionGetString(POSITION_COMMENT)));
        }
      // fermeture au croisement inverse
      if(pos > 0 && PositionSelectByTicket(pos))
        {
         bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
         if((isBuy && dn) || (!isBuy && up))
           {
            trade.SetExpertMagicNumber(slots[i].magic);
            if(trade.PositionClose(pos))
               Log("MM200 croisement inverse : position fermee sur " + slots[i].sym);
            else
               LogError("fermeture MM200 " + slots[i].sym);
            pos = 0;
           }
        }
     }

   if(pos > 0 || !(up || dn))
      return;
   if(slots[i].strat == ST_MMLONG && !up)
      return;

   int h = ServerHour();
   if(slots[i].strat != ST_MM200 && (h >= 23 || h < 1))
     {
      Log(slots[i].sym + " : signal ignore, plage 23h-1h.");
      return;
     }
   if(!EntriesAllowed(slots[i].sym, InpMaxSpreadPips * PipSize(slots[i].sym)))
      return;

   int side = up ? 1 : -1;
   if(slots[i].strat == ST_MM200)
      OpenMarket(slots[i], side, 4.5 * a[0], 9.0 * a[0], 1.8 * a[0], "MM200");
   else
      OpenMarket(slots[i], side, 4.0 * a[0], 0.0, 4.0 * a[0], slots[i].strat == ST_MM ? "MM" : "MMLONG");
  }

//+------------------------------------------------------------------+
//| LONDON : cassure du range asiatique                               |
//+------------------------------------------------------------------+
bool AsianRange(const string sym, double &hi, double &lo)
  {
   long today = DayKey(TimeCurrent());
   hi = -DBL_MAX;
   lo = DBL_MAX;
   int found = 0;
   for(int k = 1; k <= 30; k++)
     {
      datetime t = iTime(sym, PERIOD_H1, k);
      if(t == 0 || DayKey(t) != today)
         continue;
      MqlDateTime dt;
      TimeToStruct(t, dt);
      if(dt.hour >= 9)
         continue;
      hi = MathMax(hi, iHigh(sym, PERIOD_H1, k));
      lo = MathMin(lo, iLow(sym, PERIOD_H1, k));
      found++;
     }
   return found >= 5;
  }

void ProcessLondon(int i)
  {
   int h = ServerHour();
   long today = DayKey(TimeCurrent());
   ulong pos = FindPosition(slots[i]);

   // sortie de fin de journee
   if(h >= 23)
     {
      if(pos > 0)
        {
         trade.SetExpertMagicNumber(slots[i].magic);
         if(trade.PositionClose(pos))
            Log("LONDON fin de journee : position fermee sur " + slots[i].sym);
         else
            LogError("fermeture LONDON " + slots[i].sym);
        }
      if(CountPending(slots[i]) > 0)
         DeletePending(slots[i]);
      return;
     }

   // une position est ouverte : on retire l'ordre oppose (OCO)
   if(pos > 0)
     {
      if(CountPending(slots[i]) > 0)
         DeletePending(slots[i]);
      return;
     }

   // plus d'entree apres 17h59
   if(h > 17)
     {
      if(CountPending(slots[i]) > 0)
         DeletePending(slots[i]);
      return;
     }

   if(h < 9 || slots[i].lastSetupDay == today || CountPending(slots[i]) > 0)
      return;

   double hi, lo, a[];
   ArraySetAsSeries(a, true);
   if(!AsianRange(slots[i].sym, hi, lo) || CopyBuffer(slots[i].hAtr, 0, 1, 1, a) != 1)
      return;
   slots[i].lastSetupDay = today;

   double range = hi - lo;
   if(range > 1.2 * a[0] || range < 0.15 * a[0])
     {
      Log(StringFormat("%s : range asiatique hors limites, pas de trade aujourd'hui.", slots[i].sym));
      return;
     }
   if(!EntriesAllowed(slots[i].sym, InpMaxSpreadPips * PipSize(slots[i].sym)))
      return;

   int digits = (int)SymbolInfoInteger(slots[i].sym, SYMBOL_DIGITS);
   double ask = SymbolInfoDouble(slots[i].sym, SYMBOL_ASK);
   double bid = SymbolInfoDouble(slots[i].sym, SYMBOL_BID);
   double point = SymbolInfoDouble(slots[i].sym, SYMBOL_POINT);
   double stopsLevel = (double)SymbolInfoInteger(slots[i].sym, SYMBOL_TRADE_STOPS_LEVEL) * point;

   // le prix a deja casse le range : entree au marche, comme dans le backtest
   if(ask >= hi)
     {
      OpenMarket(slots[i], 1, ask - lo, 0.0, 0.0, "LONDON");
      return;
     }
   if(bid <= lo)
     {
      OpenMarket(slots[i], -1, hi - bid, 0.0, 0.0, "LONDON");
      return;
     }

   double lots = LotsForRisk(slots[i].sym, range, InpRiskPct);
   if(lots <= 0)
      return;
   trade.SetExpertMagicNumber(slots[i].magic);
   trade.SetTypeFillingBySymbol(slots[i].sym);
   double buyPx = NormalizeDouble(hi, digits), sellPx = NormalizeDouble(lo, digits);
   if(buyPx - ask > stopsLevel)
     {
      if(!trade.BuyStop(lots, buyPx, slots[i].sym, sellPx, 0.0, ORDER_TIME_GTC, 0, "LONDON|0"))
         LogError("BuyStop " + slots[i].sym);
     }
   if(bid - sellPx > stopsLevel)
     {
      if(!trade.SellStop(lots, sellPx, slots[i].sym, buyPx, 0.0, ORDER_TIME_GTC, 0, "LONDON|0"))
         LogError("SellStop " + slots[i].sym);
     }
   Log(StringFormat("LONDON %s : ordres poses a %s / %s (%.2f lot)", slots[i].sym,
                    DoubleToString(buyPx, digits), DoubleToString(sellPx, digits), lots));
  }
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| DIP : achat sur repli des indices, en journalier                   |
//+------------------------------------------------------------------+
void ProcessDip(int i)
  {
   datetime bar = iTime(slots[i].sym, PERIOD_D1, 0);
   if(bar == 0 || bar == slots[i].lastBar)
      return;

   double ma200[], ma5[], r2[], a[];
   if(CopyBuffer(slots[i].hSlow, 0, 1, 1, ma200) != 1 || CopyBuffer(slots[i].hFast, 0, 1, 1, ma5) != 1 ||
      CopyBuffer(slots[i].hRsi, 0, 1, 1, r2) != 1 || CopyBuffer(slots[i].hAtr, 0, 1, 1, a) != 1)
     {
      Log("Donnees indicateurs indisponibles pour " + slots[i].sym);
      return;
     }
   slots[i].lastBar = bar;
   double c1 = iClose(slots[i].sym, PERIOD_D1, 1);

   ulong pos = FindPosition(slots[i]);
   if(pos > 0 && PositionSelectByTicket(pos))
     {
      // sortie : la cloture d'hier repasse au-dessus de la MM5 (le rebond), ou 10 jours de detention
      int held = iBarShift(slots[i].sym, PERIOD_D1, (datetime)PositionGetInteger(POSITION_TIME), false);
      if(c1 <= ma5[0] && held < 11)
         return;
      trade.SetExpertMagicNumber(slots[i].magic);
      if(!trade.PositionClose(pos))
        {
         LogError("fermeture DIP " + slots[i].sym);
         slots[i].lastBar = 0; // on reessaie au prochain passage
         return;
        }
      Log(StringFormat("DIP %s : position fermee (%s).", slots[i].sym, c1 > ma5[0] ? "rebond" : "10 jours"));
     }

   // entree : tendance de fond haussiere (cloture > MM200) et forte baisse a court terme (RSI(2) bas)
   if(c1 > ma200[0] && r2[0] < InpDipRsiLevel && EntriesAllowed(slots[i].sym, 0.05 * a[0]))
      OpenMarket(slots[i], 1, 3.0 * a[0], 0.0, 0.0, "DIP");
  }
//+------------------------------------------------------------------+
