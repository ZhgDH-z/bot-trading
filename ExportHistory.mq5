//+------------------------------------------------------------------+
//|                                                ExportHistory.mq5 |
//|  Script : exporte l'historique (D1 et H1) des indices, matieres   |
//|  premieres et paires forex disponibles chez ton broker, en CSV,   |
//|  dans MQL5\Files\export\. Ne passe aucun ordre.                    |
//|  Utilisation : glisser le script sur n'importe quel graphique.     |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.00"
#property script_show_inputs

input string   InpKeywords = "US500,SPX,SP500,US30,DJ30,DOW,NAS,USTEC,US100,NDX,NQ100,GER,DE40,DE30,DAX,UK100,FTSE,JP225,JPN225,NIKKEI,FRA40,CAC,EU50,STOXX,XAU,XAG,WTI,USOIL,OIL,BRENT,UKOIL,BTC,ETH"; // Mots-cles indices / matieres premieres / crypto
input string   InpForex    = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,USDCHF,EURGBP,EURJPY,GBPJPY,AUDJPY,EURCHF"; // Paires forex
input datetime InpFromD1   = D'2000.01.01'; // Debut historique journalier
input datetime InpFromH1   = D'2012.01.01'; // Debut historique horaire

string kw[], fx[];

bool Wanted(const string name)
  {
   string u = name;
   StringToUpper(u);
   for(int i = 0; i < ArraySize(fx); i++)
      if(StringFind(u, fx[i]) == 0)
         return true;
   for(int i = 0; i < ArraySize(kw); i++)
      if(StringFind(u, kw[i]) >= 0)
         return true;
   return false;
  }

int Export(const string sym, ENUM_TIMEFRAMES tf, datetime from)
  {
   MqlRates r[];
   int n = -1;
   for(int k = 0; k < 20 && !IsStopped(); k++)
     {
      n = CopyRates(sym, tf, from, TimeCurrent(), r);
      if(n > 0 && SeriesInfoInteger(sym, tf, SERIES_SYNCHRONIZED))
         break;
      Sleep(500);
     }
   if(n <= 0)
     {
      PrintFormat("[Export] %s %s : pas de donnees (%d)", sym, EnumToString(tf), GetLastError());
      return 0;
     }
   string safe = sym;
   StringReplace(safe, "/", "_");
   StringReplace(safe, "\\", "_");
   string fn = "export\\" + safe + "_" + (tf == PERIOD_D1 ? "D1" : "H1") + ".csv";
   int h = FileOpen(fn, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(h == INVALID_HANDLE)
     {
      PrintFormat("[Export] impossible d'ecrire %s (%d)", fn, GetLastError());
      return 0;
     }
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   FileWrite(h, "time", "open", "high", "low", "close", "tick_volume", "spread_points");
   for(int j = 0; j < n; j++)
      FileWrite(h, TimeToString(r[j].time, TIME_DATE | TIME_MINUTES),
                DoubleToString(r[j].open, digits), DoubleToString(r[j].high, digits),
                DoubleToString(r[j].low, digits), DoubleToString(r[j].close, digits),
                (long)r[j].tick_volume, r[j].spread);
   FileClose(h);
   return n;
  }

void OnStart()
  {
   StringSplit(InpKeywords, ',', kw);
   StringSplit(InpForex, ',', fx);

   int fl = FileOpen("export\\symbols.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(fl == INVALID_HANDLE)
     {
      Print("[Export] impossible de creer export\\symbols.csv");
      return;
     }
   FileWrite(fl, "symbol", "path", "description", "digits", "point", "contract_size",
             "tick_value", "tick_size", "bars_D1", "bars_H1");

   int total = SymbolsTotal(false);
   int done = 0;
   for(int i = 0; i < total && !IsStopped(); i++)
     {
      string name = SymbolName(i, false);
      int nD1 = 0, nH1 = 0;
      if(Wanted(name))
        {
         SymbolSelect(name, true);
         Comment(StringFormat("Export %s (%d/%d)...", name, i + 1, total));
         nD1 = Export(name, PERIOD_D1, InpFromD1);
         nH1 = Export(name, PERIOD_H1, InpFromH1);
         done++;
        }
      FileWrite(fl, name, SymbolInfoString(name, SYMBOL_PATH), SymbolInfoString(name, SYMBOL_DESCRIPTION),
                (int)SymbolInfoInteger(name, SYMBOL_DIGITS), SymbolInfoDouble(name, SYMBOL_POINT),
                SymbolInfoDouble(name, SYMBOL_TRADE_CONTRACT_SIZE), SymbolInfoDouble(name, SYMBOL_TRADE_TICK_VALUE),
                SymbolInfoDouble(name, SYMBOL_TRADE_TICK_SIZE), nD1, nH1);
     }
   FileClose(fl);
   Comment("");
   PrintFormat("[Export] termine : %d symboles exportes sur %d disponibles. Fichiers dans MQL5\\Files\\export", done, total);
  }
//+------------------------------------------------------------------+
