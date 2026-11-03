//+------------------------------------------------------------------+
//|                                             MA_Cross_USDJPY.mq5  |
//|  Expert Advisor MetaTrader 5 reproduisant la strategie de la      |
//|  video "Il cree un bot de trading rentable avec ChatGPT"          |
//|  (Impact Trading, janvier 2026).                                  |
//|                                                                    |
//|  Regles (exactement celles de la video) :                         |
//|   - USD/JPY, H1                                                    |
//|   - 2 moyennes mobiles : une rapide (collee au prix) et une lente  |
//|     (lissee). Achat quand la rapide croise AU-DESSUS de la lente.  |
//|   - ACHAT UNIQUEMENT, jamais de vente (pas de contre-tendance)     |
//|   - Stop loss 55 pips + trailing stop 55 pips qui demarre au meme  |
//|     niveau que le stop loss (pas de break-even a zero)             |
//|   - Une seule position a la fois, on attend le signal suivant      |
//|   - Strategie evaluee seulement a l'ouverture d'une nouvelle       |
//|     bougie, jamais a chaque tick                                   |
//|   - Controle du spread maximum, pas d'entree entre 23h et 1h       |
//|   - Lot fixe ou lot automatique proportionnel au capital           |
//|   - Journal des erreurs                                            |
//|   - Pas de grid, pas de martingale                                 |
//|                                                                    |
//|  Securite ajoutee : le robot refuse de tourner sur un compte REEL  |
//|  tant que InpAllowRealAccount = false.                             |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.00"
#property description "Croisement de moyennes mobiles, achat uniquement, SL 55 pips + trailing 55 pips"

#include <Trade/Trade.mqh>

//--- parametres
input group "=== Identite ==="
input string            InpBotName          = "MA_Cross_USDJPY"; // Nom affiche du robot
input ulong             InpMagic            = 20260118;          // Numero magique unique

input group "=== Taille de position ==="
input double            InpFixedLot         = 0.70;   // Lot fixe (video : 0,7 lot pour 10 000)
input bool              InpAutoLot          = false;  // Lot automatique selon le capital
input double            InpLotPer10k        = 0.70;   // Lot pour 10 000 de capital (si lot auto)

input group "=== Stop loss / trailing ==="
input int               InpStopLossPips     = 55;     // Stop loss (pips)
input int               InpTrailingPips     = 55;     // Distance du trailing stop (pips)
input int               InpTrailingStepPips = 1;      // Pas minimum de deplacement du trailing (pips)

input group "=== Moyennes mobiles ==="
input ENUM_TIMEFRAMES   InpTimeframe        = PERIOD_H1;   // Unite de temps
input int               InpFastPeriod       = 8;           // Periode moyenne rapide (collee au prix)
input ENUM_MA_METHOD    InpFastMethod       = MODE_EMA;    // Methode moyenne rapide
input int               InpSlowPeriod       = 30;          // Periode moyenne lente (lissee)
input ENUM_MA_METHOD    InpSlowMethod       = MODE_SMMA;   // Methode moyenne lente
input ENUM_APPLIED_PRICE InpAppliedPrice    = PRICE_CLOSE; // Prix utilise

input group "=== Filtres ==="
input int               InpMaxSpreadPoints  = 30;     // Spread maximum autorise (points)
input int               InpSlippagePoints   = 30;     // Glissement maximum (points)
input bool              InpUseTimeFilter    = true;   // Activer le filtre horaire
input int               InpNoTradeFromHour  = 23;     // Pas d'entree a partir de (heure serveur)
input int               InpNoTradeToHour    = 1;      // ... jusqu'a (heure serveur)

input group "=== Securite ==="
input bool              InpAllowRealAccount = false;  // Autoriser un compte REEL (laisser false en test)

//--- variables globales
CTrade   trade;
int      hFast = INVALID_HANDLE;
int      hSlow = INVALID_HANDLE;
double   pipSize;
datetime lastBarTime = 0;

//+------------------------------------------------------------------+
void Log(const string msg)
  {
   PrintFormat("[%s] %s", InpBotName, msg);
  }

void LogError(const string where)
  {
   PrintFormat("[%s] ERREUR %s : code %d (%s) | derniere erreur %d",
               InpBotName, where, (int)trade.ResultRetcode(),
               trade.ResultRetcodeDescription(), GetLastError());
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL && !InpAllowRealAccount)
     {
      Log("Compte REEL detecte : robot bloque. Teste d'abord en compte demo, "
          "puis passe InpAllowRealAccount a true seulement si tu l'as decide.");
      return(INIT_FAILED);
     }

   if(InpFastPeriod >= InpSlowPeriod)
     {
      Log("La periode rapide doit etre plus petite que la periode lente.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   pipSize = (digits == 3 || digits == 5) ? point * 10.0 : point;

   hFast = iMA(_Symbol, InpTimeframe, InpFastPeriod, 0, InpFastMethod, InpAppliedPrice);
   hSlow = iMA(_Symbol, InpTimeframe, InpSlowPeriod, 0, InpSlowMethod, InpAppliedPrice);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE)
     {
      PrintFormat("[%s] ERREUR creation des moyennes mobiles : %d", InpBotName, GetLastError());
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   if(_Symbol != "USDJPY" && StringFind(_Symbol, "USDJPY") < 0)
      Log("Attention : la strategie de la video est concue pour USDJPY, symbole actuel = " + _Symbol);
   if(InpTimeframe != PERIOD_H1 && !(InpTimeframe == PERIOD_CURRENT && _Period == PERIOD_H1))
      Log("Attention : la video utilise l'unite de temps H1.");

   Log(StringFormat("Demarre sur %s | MA %d/%d | SL %d pips | trailing %d pips | lot %s",
                    _Symbol, InpFastPeriod, InpSlowPeriod, InpStopLossPips, InpTrailingPips,
                    InpAutoLot ? "auto" : DoubleToString(InpFixedLot, 2)));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(hFast != INVALID_HANDLE) IndicatorRelease(hFast);
   if(hSlow != INVALID_HANDLE) IndicatorRelease(hSlow);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Le trailing stop suit le prix en continu...
   ManageTrailingStop();

   // ...mais la strategie d'entree n'est evaluee qu'a l'ouverture d'une nouvelle bougie
   if(!IsNewBar())
      return;

   if(HasOpenPosition())
      return; // une seule position a la fois

   if(!BuySignal())
      return;

   if(InpUseTimeFilter && IsBlockedHour())
     {
      Log("Signal d'achat ignore : plage horaire interdite.");
      return;
     }

   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints)
     {
      Log(StringFormat("Signal d'achat ignore : spread trop eleve (%d > %d points).",
                       (int)spread, InpMaxSpreadPoints));
      return;
     }

   OpenBuy();
  }

//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, InpTimeframe, 0);
   if(t == 0 || t == lastBarTime)
      return(false);
   lastBarTime = t;
   return(true);
  }

//+------------------------------------------------------------------+
// Croisement sur les bougies CLOTUREES : la rapide etait sous (ou egale a) la lente
// sur la bougie 2 et passe au-dessus sur la bougie 1.
bool BuySignal()
  {
   double fast[], slow[];
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);
   if(CopyBuffer(hFast, 0, 1, 2, fast) != 2 || CopyBuffer(hSlow, 0, 1, 2, slow) != 2)
     {
      PrintFormat("[%s] ERREUR lecture des moyennes mobiles : %d", InpBotName, GetLastError());
      return(false);
     }
   // fast[0] = bougie 1 (derniere cloturee), fast[1] = bougie 2
   return(fast[0] > slow[0] && fast[1] <= slow[1]);
  }

//+------------------------------------------------------------------+
bool IsBlockedHour()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int h = dt.hour;
   if(InpNoTradeFromHour > InpNoTradeToHour)
      return(h >= InpNoTradeFromHour || h < InpNoTradeToHour);
   return(h >= InpNoTradeFromHour && h < InpNoTradeToHour);
  }

//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
double NormalizeLot(double lot)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0)
      step = 0.01;
   lot = MathFloor(lot / step) * step;
   lot = MathMax(vmin, MathMin(vmax, lot));
   int d = (int)MathMax(0, MathCeil(-MathLog10(step)));
   return(NormalizeDouble(lot, d));
  }

double ComputeLot()
  {
   if(!InpAutoLot)
      return(NormalizeLot(InpFixedLot));
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   return(NormalizeLot(balance / 10000.0 * InpLotPer10k));
  }

//+------------------------------------------------------------------+
void OpenBuy()
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double sl  = NormalizeDouble(ask - InpStopLossPips * pipSize, digits);
   double lot = ComputeLot();

   double margin = 0.0;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lot, ask, margin) &&
      margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     {
      Log(StringFormat("Achat annule : marge insuffisante (%.2f requis).", margin));
      return;
     }

   if(trade.Buy(lot, _Symbol, ask, sl, 0.0, InpBotName))
     {
      if(trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_PLACED)
         Log(StringFormat("ACHAT %.2f lot a %.3f | SL %.3f", lot, trade.ResultPrice(), sl));
      else
         LogError("ouverture achat");
     }
   else
      LogError("ouverture achat");
  }

//+------------------------------------------------------------------+
// Trailing stop : le stop suit le prix a InpTrailingPips de distance et ne recule jamais.
// Il demarre au meme niveau que le stop loss initial (55 pips), pas de break-even.
void ManageTrailingStop()
  {
   int    digits     = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point      = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   double bid        = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic ||
         PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY)
         continue;

      double curSL = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      double newSL = NormalizeDouble(bid - InpTrailingPips * pipSize, digits);

      if(bid - newSL < stopsLevel)
         continue;
      if(curSL == 0.0 || newSL >= curSL + InpTrailingStepPips * pipSize)
        {
         if(trade.PositionModify(ticket, newSL, tp))
            Log(StringFormat("Trailing stop deplace : %.3f -> %.3f", curSL, newSL));
         else
            LogError("deplacement du trailing stop");
        }
     }
  }
//+------------------------------------------------------------------+
