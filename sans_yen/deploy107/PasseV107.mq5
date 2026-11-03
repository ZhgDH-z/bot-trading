//+------------------------------------------------------------------+
//| PasseV107.mq5 : remplace DayTrader_MT5 v1.06 par v1.07 sur le     |
//| graphique DE40 M15 du compte DEMO. TradeNotifier n'est pas touche.|
//| Ne fait rien si le compte n'est pas DEMO, ni si la v1.01 a encore |
//| une position ou un ordre en attente (magic 261103xx ou 261106xx).|
//| Rapport : MQL5\Files\passe_v107.txt                               |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.00"

int fh = INVALID_HANDLE;
void Out(const string s) { Print("[PasseV107] ", s); if(fh != INVALID_HANDLE) FileWriteString(fh, s + "\r\n"); }
bool OldMagic(long m) { return (m >= 26110300 && m <= 26110302) || (m >= 26110600 && m <= 26110603) || (m >= 26110700 && m <= 26110704); }

void OnStart()
  {
   fh = FileOpen("passe_v107.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   long mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   Out(StringFormat("compte %I64d, serveur %s, mode %s, heure serveur %s", AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER),
                    mode == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" : "PAS DEMO", TimeToString(TimeCurrent())));
   if(mode != ACCOUNT_TRADE_MODE_DEMO) { Out("Compte pas DEMO : rien n'est fait."); FileClose(fh); return; }
   int busy = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(PositionGetTicket(i) > 0 && OldMagic(PositionGetInteger(POSITION_MAGIC)))
        { busy++; Out(StringFormat("position d'une ancienne version ouverte : %s magic %I64d", PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC))); }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
      if(OrderGetTicket(i) > 0 && OldMagic(OrderGetInteger(ORDER_MAGIC)))
        { busy++; Out(StringFormat("ordre d'une ancienne version en attente : %s magic %I64d", OrderGetString(ORDER_SYMBOL), OrderGetInteger(ORDER_MAGIC))); }
   Out(StringFormat("positions ouvertes sur le compte : %d, ordres : %d", PositionsTotal(), OrdersTotal()));
   if(busy > 0) { Out("Une ancienne version a encore un trade en cours : rien n'est remplace. Relancer quand il sera ferme."); FileClose(fh); return; }
   Out(StringFormat("bouton Algo Trading : %s", TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "ACTIVE" : "COUPE"));
   long target = -1;
   for(long id = ChartFirst(); id >= 0; id = ChartNext(id))
     {
      string e = ChartGetString(id, CHART_EXPERT_NAME);
      Out(StringFormat("graphique %I64d %s %s : robot '%s'", id, ChartSymbol(id), EnumToString(ChartPeriod(id)), e));
      if((e == "DayTrader_MT5_v106" || e == "DayTrader_MT5_v107") && target < 0) target = id;
     }
   if(target < 0)
     {
      Out("Pas de graphique avec DayTrader_MT5 v1.06 : ouverture d'un graphique DE40 M15.");
      SymbolSelect("DE40", true); target = ChartOpen("DE40", PERIOD_M15);
      if(target == 0) { Out(StringFormat("ERREUR ouverture graphique : %d", GetLastError())); FileClose(fh); return; }
     }
   if(!ChartApplyTemplate(target, "\\Scripts\\LanceDayTrader107.tpl")) { Out(StringFormat("ERREUR modele : %d", GetLastError())); FileClose(fh); return; }
   for(int k = 0; k < 40; k++)
     {
      Sleep(500);
      if(k >= 4 && ChartGetString(target, CHART_EXPERT_NAME) == "DayTrader_MT5_v107")
        { Out(StringFormat("OK : DayTrader_MT5_v107 (re)lance sur %s %s avec les nouveaux reglages", ChartSymbol(target), EnumToString(ChartPeriod(target)))); FileClose(fh); return; }
     }
   Out(StringFormat("ECHEC : robot lu sur le graphique apres 20 s = '%s'", ChartGetString(target, CHART_EXPERT_NAME)));
   FileClose(fh);
  }
