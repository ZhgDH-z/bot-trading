//+------------------------------------------------------------------+
//|                                                     ExportM5.mq5 |
//|  Script : exporte l'historique en 5 minutes (M5) des marches du   |
//|  bot sans yen, en CSV, dans MQL5\Files\export_m5\.                 |
//|  Ne passe aucun ordre. Utilisation : double-clic dans le           |
//|  Navigateur (ou glisser sur un graphique).                         |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.00"

input string   InpSymbols = "US500,US30,USTECH100M,DE40,XAUUSD,XAGUSD,EURUSD,GBPUSD,AUDUSD,USDCAD,USDCHF,EURGBP,EURCHF";
input datetime InpFrom    = D'2016.01.01';

void OnStart()
  {
   string s[];
   int n = StringSplit(InpSymbols, ',', s);
   for(int i = 0; i < n && !IsStopped(); i++)
     {
      string sym = s[i];
      if(!SymbolSelect(sym, true))
        {
         PrintFormat("[ExportM5] %s introuvable", sym);
         continue;
        }
      Comment(StringFormat("Export M5 %s (%d/%d)... ne ferme pas MT5", sym, i + 1, n));
      MqlRates r[];
      int got = -1;
      for(int k = 0; k < 120 && !IsStopped(); k++)
        {
         got = CopyRates(sym, PERIOD_M5, InpFrom, TimeCurrent(), r);
         if(got > 0 && SeriesInfoInteger(sym, PERIOD_M5, SERIES_SYNCHRONIZED))
            break;
         Sleep(1000);
        }
      if(got <= 0)
        {
         PrintFormat("[ExportM5] %s : pas de donnees (%d)", sym, GetLastError());
         continue;
        }
      int h = FileOpen("export_m5\\" + sym + "_M5.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
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
      PrintFormat("[ExportM5] %s : %d bougies depuis %s", sym, got, TimeToString(r[0].time));
     }
   Comment("");
   Print("[ExportM5] termine. Fichiers dans MQL5\\Files\\export_m5");
  }
//+------------------------------------------------------------------+
