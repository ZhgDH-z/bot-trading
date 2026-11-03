//+------------------------------------------------------------------+
//| LanceRobots.mq5 : attache DayTrader_MT5 (DE40 M15) et            |
//| TradeNotifier (EURUSD H1) si ils ne tournent pas deja.            |
//| Ne fait rien sur un compte qui n'est pas DEMO.                    |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.00"

int fh = INVALID_HANDLE;
void Out(const string s) { Print("[LanceRobots] ", s); if(fh != INVALID_HANDLE) FileWriteString(fh, s + "\r\n"); }

bool Attach(const string sym, ENUM_TIMEFRAMES tf, const string tpl, const string name)
  {
   SymbolSelect(sym, true);
   long c = ChartOpen(sym, tf);
   if(c == 0) { Out(StringFormat("ERREUR ouverture graphique %s : %d", sym, GetLastError())); return false; }
   if(!ChartApplyTemplate(c, tpl)) { Out(StringFormat("ERREUR modele %s : %d", tpl, GetLastError())); return false; }
   for(int k = 0; k < 30; k++)
     {
      Sleep(500);
      if(ChartGetString(c, CHART_EXPERT_NAME) == name)
        {
         Out(StringFormat("OK %s attache sur %s %s", name, sym, EnumToString(tf)));
         return true;
        }
     }
   Out(StringFormat("ECHEC %s pas visible sur %s apres 15 s (expert lu : '%s')", name, sym, ChartGetString(c, CHART_EXPERT_NAME)));
   return false;
  }

void OnStart()
  {
   fh = FileOpen("lance_robots.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   long mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   Out(StringFormat("compte %I64d, serveur %s, mode %s", AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER),
                    mode == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" : (mode == ACCOUNT_TRADE_MODE_REAL ? "REEL" : "CONCOURS")));
   if(mode != ACCOUNT_TRADE_MODE_DEMO)
     {
      Out("Compte pas DEMO : rien n'est lance.");
      if(fh != INVALID_HANDLE) FileClose(fh);
      return;
     }
   Out(StringFormat("bouton Algo Trading du terminal : %s", TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "ACTIVE" : "COUPE"));
   Out(StringFormat("notifications push : %s, MetaQuotes ID renseigne : %s",
                    TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED) ? "activees" : "non activees",
                    TerminalInfoInteger(TERMINAL_MQID) ? "oui" : "non"));
   bool dt = false, tn = false;
   for(long id = ChartFirst(); id >= 0; id = ChartNext(id))
     {
      string e = ChartGetString(id, CHART_EXPERT_NAME);
      Out(StringFormat("graphique %s %s : robot '%s'", ChartSymbol(id), EnumToString(ChartPeriod(id)), e));
      if(e == "DayTrader_MT5") dt = true;
      if(e == "TradeNotifier") tn = true;
     }
   if(dt) Out("DayTrader_MT5 tourne deja.");
   else   Attach("DE40", PERIOD_M15, "\\Scripts\\LanceDayTrader.tpl", "DayTrader_MT5");
   if(tn) Out("TradeNotifier tourne deja.");
   else   Attach("EURUSD", PERIOD_H1, "\\Scripts\\LanceNotifier.tpl", "TradeNotifier");
   if(fh != INVALID_HANDLE) FileClose(fh);
  }
