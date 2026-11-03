//+------------------------------------------------------------------+
//|                                                     ExportM15_Indices.mq5 |
//|  Script : exporte l'historique en 15 minutes (M15) indices + actions US |
//|  bot sans yen, en CSV, dans MQL5\Files\export_m15\.                 |
//|  Ne passe aucun ordre. Utilisation : double-clic dans le           |
//|  Navigateur (ou glisser sur un graphique).                         |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.00"

input string   InpSymbols = "FRA40,NETH25,TECHDE30,EU50,EUSTX50,STOXX50,ESP35,SWI20,UK100,ITA40,JPN225,NVDA,TSLA,AAPL,AMD,META,MSFT,AMZN,GOOGL,NFLX";
input datetime InpFrom    = D'2022.01.01';

void OnStart()
  {
   // liste de tous les symboles du serveur (pour trouver les bons noms)
   int hl = FileOpen("export_m15b\\symboles.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(hl != INVALID_HANDLE)
     {
      for(int q = 0; q < SymbolsTotal(false); q++)
        {
         string nm = SymbolName(q, false);
         FileWrite(hl, nm + ";" + SymbolInfoString(nm, SYMBOL_PATH) + ";" + SymbolInfoString(nm, SYMBOL_DESCRIPTION));
        }
      FileClose(hl);
     }
   string s[];
   int n = StringSplit(InpSymbols, ',', s);
   for(int i = 0; i < n && !IsStopped(); i++)
     {
      string sym = s[i];
      if(!SymbolSelect(sym, true))
        {
         PrintFormat("[ExportM15b] %s introuvable", sym);
         continue;
        }
      Comment(StringFormat("Export M15 %s (%d/%d)... ne ferme pas MT5", sym, i + 1, n));
      MqlRates r[];
      int got = -1;
      for(int k = 0; k < 120 && !IsStopped(); k++)
        {
         got = CopyRates(sym, PERIOD_M15, InpFrom, TimeCurrent(), r);
         if(got > 0 && SeriesInfoInteger(sym, PERIOD_M15, SERIES_SYNCHRONIZED))
            break;
         Sleep(1000);
        }
      if(got <= 0)
        {
         PrintFormat("[ExportM15b] %s : pas de donnees (%d)", sym, GetLastError());
         continue;
        }
      int h = FileOpen("export_m15b\\" + sym + "_M15.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
      if(h == INVALID_HANDLE)
         continue;
      int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      FileWrite(h, "time", "open", "high", "low", "close", "tick_volume", "spread_points");
      for(int j = 0; j < got; j++)
         FileWrite(h, TimeToString(r[j].time, TIME_DATE | TIME_MINUTES),
                   DoubleToString(r[j].open, digits), DoubleToString(r[j].high, digits),
                   DoubleToString(r[j].low, digits), DoubleToString(r[j].close, digits),
                   (long)r[j].tick_volume, r[j].spread);
      FileClose(h);
      PrintFormat("[ExportM15b] %s : %d bougies depuis %s", sym, got, TimeToString(r[0].time));
     }
   Comment("");
   Print("[ExportM15b] termine. Fichiers dans MQL5\\Files\\export_m15");
  }
//+------------------------------------------------------------------+
