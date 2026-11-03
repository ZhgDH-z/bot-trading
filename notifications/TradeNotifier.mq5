//+------------------------------------------------------------------+
//|                                                TradeNotifier.mq5 |
//|  Robot COMPAGNON : il ne trade pas. Il surveille le compte et     |
//|  t'envoie une notification :                                      |
//|   - a chaque ouverture de trade (sens, lot, prix, stop, risque)   |
//|   - a chaque fermeture (gagnant ou perdant, resultat en euros,    |
//|     en %, en pips, raison de la sortie, duree)                    |
//|   - un recap quotidien a heure fixe (heure de Paris) : compte,    |
//|     resultat du jour / de la semaine / depuis le lancement,       |
//|     positions ouvertes, etat du marche                            |
//|   - des alertes : trading auto coupe, coupure de connexion,       |
//|     perte du jour trop forte, bot muet depuis plusieurs jours     |
//|                                                                    |
//|  Il marche avec N'IMPORTE QUEL robot (MultiBot, nouvelle          |
//|  strategie sans yen...) et avec les trades manuels : il lit       |
//|  l'historique du compte, il ne depend pas du code du robot.       |
//|  A poser sur UN graphique, a cote du robot de trading.            |
//+------------------------------------------------------------------+
#property copyright "Bot trading - projet aurele"
#property version   "1.11"
#property description "Notifie chaque trade + recap quotidien + analyse du marche (rapports du robot, calendrier eco, IA Claude en option)"

//--- parametres
input group "=== Canaux de notification ==="
input bool   InpPush          = true;   // Notification push vers l'appli MetaTrader du telephone
input bool   InpTelegram      = false;  // Envoyer aussi sur Telegram
input string InpTgToken       = "";     // Telegram : token du bot (donne par @BotFather)
input string InpTgChatId      = "";     // Telegram : ton chat_id
input bool   InpEmail         = false;  // Envoyer aussi par e-mail (regler l'onglet E-mail de MT5)

input group "=== Trades a suivre ==="
input bool   InpTradeAlerts   = true;   // Message a chaque ouverture/fermeture (false = recap et alertes seulement)
input ulong  InpMagicMin      = 0;      // Magic minimum (0 et 0 = TOUS les trades du compte)
input ulong  InpMagicMax      = 0;      // Magic maximum

input group "=== Recap quotidien (heure de Paris) ==="
input bool   InpRecap         = true;   // Envoyer un recap chaque jour
input int    InpRecapHour     = 22;     // Heure du recap (heure de Paris)
input int    InpRecapMinute   = 30;     // Minute du recap (22h30 : apres la fermeture du day trading US)
input bool   InpRecapWeekend  = false;  // Recap aussi le samedi et le dimanche
input string InpMarketSymbols = "DE40,XAUUSD,US500,USTECH100M,US30,EURUSD,GBPUSD,EURCHF,XAGUSD,XTIUSD"; // Marches decrits dans le recap
input string InpSymbolSuffix  = "";     // Suffixe des symboles chez ton broker (ex : ".m")

input group "=== Alertes de surveillance ==="
input double InpDailyLossAlertPct = 2.0;  // Alerte si le capital perd plus de X % sur la journee (0 = off)
input bool   InpAlertAutoTrading  = true; // Alerte si le bouton Algo Trading est coupe
input bool   InpAlertConnection   = true; // Message quand la connexion revient apres une coupure
input int    InpNoTradeAlertDays  = 3;    // Signale dans le recap si aucun trade depuis X jours (0 = off)

input group "=== Analyse du marche ==="
input bool   InpAnalysis         = true;  // Lire les rapports du robot (MQL5\Files\DayTrader\outbox) et envoyer l'analyse
input string InpOutboxDir        = "DayTrader\\outbox\\";  // Dossier ou le robot depose ses rapports
input string InpOutboxArchive    = "DayTrader\\archive\\"; // Dossier ou les rapports sont ranges apres envoi
input bool   InpCalendar         = true;  // Ajouter les annonces economiques du calendrier MT5
input string InpCalCurrencies    = "USD,EUR,GBP,CHF"; // Devises suivies dans le calendrier
input int    InpCalMinImportance = 3;     // 3 = annonces a fort impact seulement, 2 = moyen et fort
input bool   InpOwnReports       = true;  // Rapport de secours si le robot n'a pas envoye le sien (marches de InpMarketSymbols)
input int    InpMorningHour      = 9;     // Heure du rapport du matin de secours (Paris ; DayTrader envoie le sien a 8h45)
input int    InpMorningMinute    = 15;    // Minute du rapport du matin de secours
input bool   InpTestAnalysis     = false; // Envoie un rapport d'essai au lancement (pour tester l'IA)

input group "=== Analyse redigee par l'IA (Claude) ==="
input bool   InpAI               = false; // Faire rediger l'analyse par Claude (cle API necessaire)
input string InpAiKey            = "";    // Cle API Anthropic (console.anthropic.com)
input string InpAiModel          = "claude-opus-5-5"; // Modele (claude-sonnet-5-5 : environ 2 fois moins cher)
input bool   InpAiWebSearch      = true;  // Chercher les news du jour pour les rapports du matin et du soir
input bool   InpAiWebSearchTrades = false; // Chercher aussi les news pour chaque trade (plus cher)
input int    InpAiMaxPerDay      = 20;    // Plafond d'analyses IA par jour (securite sur le cout)

input group "=== Divers ==="
input bool   InpCsvJournal    = true;   // Journal CSV dans MQL5\Files\TradeNotifier_journal.csv
input bool   InpTestOnStart   = true;   // Message de test au lancement

//--- etat
string   gPfx;                 // prefixe des variables globales du terminal
ulong    gLastDeal      = 0;   // dernier deal deja traite
datetime gLastDealTime  = 0;
datetime gStartTime     = 0;   // lancement du suivi (heure serveur)
double   gStartBalance  = 0;
double   gPeakEquity    = 0;

string   gPushQueue[];
uint     gLastPushMs    = 0;
bool     gPushWarned    = false;

long     gParisDay      = -1;
double   gDayStartEquity = 0;
bool     gLossAlertSent = false;
long     gLastRecapDay  = -1;

bool     gAutoWasOn     = true;
bool     gWasConnected  = true;
datetime gDisconnectedAt = 0;

string   gSyms[];
int      gMa[];
int      gRsi[];
int      gAtr[];

uint     gLastPanelMs   = 0;

//+------------------------------------------------------------------+
//| Outils                                                           |
//+------------------------------------------------------------------+
string Cur() { return AccountInfoString(ACCOUNT_CURRENCY); }

string Money(const double v, const bool sign = false)
  {
   string s = DoubleToString(MathAbs(v), 2) + " " + Cur();
   if(v < 0)    return "-" + s;
   if(sign)     return "+" + s;
   return s;
  }

string Pct(const double v)
  {
   return (v >= 0 ? "+" : "-") + DoubleToString(MathAbs(v), 2) + " %";
  }

bool MagicOk(const ulong magic)
  {
   if(InpMagicMin == 0 && InpMagicMax == 0)
      return true;
   return magic >= InpMagicMin && magic <= InpMagicMax;
  }

double PipSize(const string sym)
  {
   if(StringFind(sym, "XAU") == 0)
      return 0.1;
   int digits   = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   if(digits == 3 || digits == 5)
      return point * 10.0;
   return point > 0 ? point : 1.0;
  }

string Duration(const long sec)
  {
   long m = sec / 60;
   long h = m / 60;
   long d = h / 24;
   if(d > 0) return StringFormat("%dj %dh", (int)d, (int)(h % 24));
   if(h > 0) return StringFormat("%dh%02d", (int)h, (int)(m % 60));
   return StringFormat("%d min", (int)m);
  }

//--- heure de Paris (heure d'ete : du dernier dimanche de mars au dernier dimanche d'octobre, 01h00 UTC)
datetime LastSundayUTC(const int year, const int mon)
  {
   MqlDateTime dt;
   ZeroMemory(dt);
   dt.year = year;
   dt.mon  = mon;
   dt.day  = 31;
   dt.hour = 1;
   datetime t = StructToTime(dt);
   TimeToStruct(t, dt);
   return t - (datetime)(dt.day_of_week * 86400);
  }

datetime GmtToParis(const datetime g)
  {
   MqlDateTime dt;
   TimeToStruct(g, dt);
   bool summer = (g >= LastSundayUTC(dt.year, 3) && g < LastSundayUTC(dt.year, 10));
   return g + (summer ? 7200 : 3600);
  }

int ServerOffsetSec()
  {
   double d = (double)((long)TimeTradeServer() - (long)TimeGMT());
   return (int)(MathRound(d / 1800.0) * 1800.0);
  }

datetime ServerToParis(const datetime srv) { return GmtToParis(srv - ServerOffsetSec()); }
datetime NowParis()                        { return GmtToParis(TimeGMT()); }

datetime ParisToServer(const datetime p)
  {
   datetime g = p - 3600;
   g = p - (GmtToParis(g) - g);
   return g + ServerOffsetSec();
  }

string ParisStr(const datetime p)
  {
   MqlDateTime dt;
   TimeToStruct(p, dt);
   return StringFormat("%02d/%02d %02dh%02d", dt.day, dt.mon, dt.hour, dt.min);
  }

long DayKey(const datetime t) { return (long)t / 86400; }
datetime DayStart(const datetime t) { return (datetime)(((long)t / 86400) * 86400); }

//--- variables globales du terminal (survivent a un redemarrage de MT5)
double GVGet(const string name, const double def)
  {
   string n = gPfx + name;
   if(GlobalVariableCheck(n))
      return GlobalVariableGet(n);
   return def;
  }
void GVSet(const string name, const double v) { GlobalVariableSet(gPfx + name, v); }

//+------------------------------------------------------------------+
//| Envoi des notifications                                          |
//+------------------------------------------------------------------+
// Une notification push MT5 fait 255 caracteres max et MT5 en accepte
// 10 par minute : on decoupe par lignes et on espace les envois.
void QueuePush(const string text)
  {
   string lines[];
   int n = StringSplit(text, '\n', lines);
   string chunk = "";
   for(int i = 0; i < n; i++)
     {
      string l = lines[i];
      if(StringLen(l) > 250)
         l = StringSubstr(l, 0, 247) + "...";
      if(StringLen(chunk) + StringLen(l) + 1 > 250 && chunk != "")
        {
         int k = ArraySize(gPushQueue);
         ArrayResize(gPushQueue, k + 1);
         gPushQueue[k] = chunk;
         chunk = "";
        }
      chunk += (chunk == "" ? "" : "\n") + l;
     }
   if(chunk != "")
     {
      int k = ArraySize(gPushQueue);
      ArrayResize(gPushQueue, k + 1);
      gPushQueue[k] = chunk;
     }
  }

void ProcessPushQueue()
  {
   if(ArraySize(gPushQueue) == 0)
      return;
   if(gLastPushMs != 0 && GetTickCount() - gLastPushMs < 6500)
      return;
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
      return; // on garde le message, il partira au retour de la connexion
   gLastPushMs = GetTickCount();
   ResetLastError();
   if(!SendNotification(gPushQueue[0]))
     {
      int err = GetLastError();
      PrintFormat("[Notif] Echec de la notification push (erreur %d). Verifie Outils > Options > Notifications.", err);
      if(err == 4517) // trop d'envois : on reessaiera
         return;
     }
   ArrayRemove(gPushQueue, 0, 1);
  }

string UrlEncode(const string s)
  {
   uchar b[];
   int n = StringToCharArray(s, b, 0, WHOLE_ARRAY, CP_UTF8);
   string out = "";
   for(int i = 0; i < n; i++)
     {
      uchar c = b[i];
      if(c == 0)
         break;
      if((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
         c == '-' || c == '_' || c == '.' || c == '~')
         out += CharToString(c);
      else
         out += StringFormat("%%%02X", c);
     }
   return out;
  }

void SendTelegramOne(const string text);

// Telegram accepte 4096 caracteres par message : on decoupe par lignes
void SendTelegram(const string text)
  {
   if(StringLen(text) <= 3800)
     {
      SendTelegramOne(text);
      return;
     }
   string lines[];
   int n = StringSplit(text, '\n', lines);
   string chunk = "";
   for(int i = 0; i < n; i++)
     {
      if(StringLen(chunk) + StringLen(lines[i]) + 1 > 3800 && chunk != "")
        {
         SendTelegramOne(chunk);
         chunk = "";
        }
      chunk += (chunk == "" ? "" : "\n") + lines[i];
     }
   if(chunk != "")
      SendTelegramOne(chunk);
  }

void SendTelegramOne(const string text)
  {
   if(InpTgToken == "" || InpTgChatId == "")
     {
      Print("[Notif] Telegram active mais token ou chat_id vide.");
      return;
     }
   string url  = "https://api.telegram.org/bot" + InpTgToken + "/sendMessage";
   string body = "chat_id=" + UrlEncode(InpTgChatId) + "&text=" + UrlEncode(text);
   char data[], result[];
   int n = StringToCharArray(body, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(n > 0)
      ArrayResize(data, n - 1); // sans le zero final
   string headers = "Content-Type: application/x-www-form-urlencoded\r\n";
   string rh;
   ResetLastError();
   int code = WebRequest("POST", url, headers, 5000, data, result, rh);
   if(code != 200)
      PrintFormat("[Notif] Telegram : echec (code %d, erreur %d). Ajoute https://api.telegram.org dans Outils > Options > Expert Advisors > WebRequest.",
                  code, GetLastError());
  }

void Notify(const string subject, const string text)
  {
   Print("[Notif] ", text);
   if(InpPush)
      QueuePush(text);
   if(InpTelegram)
      SendTelegram(text);
   if(InpEmail)
      SendMail(subject, text);
  }

//+------------------------------------------------------------------+
//| Journal CSV                                                      |
//+------------------------------------------------------------------+
void Journal(const string line)
  {
   if(!InpCsvJournal)
      return;
   string name = "TradeNotifier_journal.csv";
   bool exists = FileIsExist(name);
   int h = FileOpen(name, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return;
   FileSeek(h, 0, SEEK_END);
   if(!exists)
      FileWriteString(h, "date_paris;evenement;symbole;sens;lots;prix;stop;objectif;resultat;pips;raison;strategie;magic;position\r\n");
   FileWriteString(h, line + "\r\n");
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Statistiques                                                     |
//+------------------------------------------------------------------+
// Trades fermes depuis 'fromSrv' (heure serveur). Appelle HistorySelect.
void ClosedStats(const datetime fromSrv, int &n, int &wins, double &pnl, datetime &lastEntry)
  {
   n = 0; wins = 0; pnl = 0; lastEntry = 0;
   if(!HistorySelect(fromSrv, TimeTradeServer() + 86400))
      return;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0) continue;
      long type = HistoryDealGetInteger(t, DEAL_TYPE);
      if(type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL) continue;
      if(!MagicOk((ulong)HistoryDealGetInteger(t, DEAL_MAGIC))) continue;
      long entry = HistoryDealGetInteger(t, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_IN)
        {
         datetime tm = (datetime)HistoryDealGetInteger(t, DEAL_TIME);
         if(tm > lastEntry) lastEntry = tm;
         continue;
        }
      double r = HistoryDealGetDouble(t, DEAL_PROFIT) + HistoryDealGetDouble(t, DEAL_SWAP) +
                 HistoryDealGetDouble(t, DEAL_COMMISSION) + HistoryDealGetDouble(t, DEAL_FEE);
      n++;
      if(r >= 0) wins++;
      pnl += r;
     }
  }

datetime ParisMidnightAsServer()
  {
   datetime p = NowParis();
   return ParisToServer(DayStart(p));
  }

datetime ParisMondayAsServer()
  {
   datetime p = NowParis();
   MqlDateTime dt;
   TimeToStruct(p, dt);
   int back = (dt.day_of_week + 6) % 7;
   return ParisToServer(DayStart(p) - (datetime)(back * 86400));
  }

//+------------------------------------------------------------------+
//| Traitement d'un trade                                            |
//+------------------------------------------------------------------+
string StratFromComment(const string cmt, const ulong magic)
  {
   int p = StringFind(cmt, "|");
   if(p > 0)
      return StringSubstr(cmt, 0, p);
   if(cmt != "")
      return cmt;
   return magic == 0 ? "manuel" : "magic " + IntegerToString((long)magic);
  }

string ReasonText(const long reason)
  {
   switch((int)reason)
     {
      case DEAL_REASON_SL:     return "stop touche";
      case DEAL_REASON_TP:     return "objectif atteint";
      case DEAL_REASON_SO:     return "stop out (marge)";
      case DEAL_REASON_EXPERT: return "ferme par le robot";
      case DEAL_REASON_CLIENT: return "ferme a la main (PC)";
      case DEAL_REASON_MOBILE: return "ferme a la main (telephone)";
      case DEAL_REASON_WEB:    return "ferme a la main (web)";
     }
   return "autre";
  }

void ProcessDeal(const ulong t)
  {
   if(!HistoryDealSelect(t))
      return;
   long type = HistoryDealGetInteger(t, DEAL_TYPE);
   if(type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL)
      return;
   ulong magic = (ulong)HistoryDealGetInteger(t, DEAL_MAGIC);
   if(!MagicOk(magic) || !InpTradeAlerts)
      return;

   long     entry  = HistoryDealGetInteger(t, DEAL_ENTRY);
   string   sym    = HistoryDealGetString(t, DEAL_SYMBOL);
   double   vol    = HistoryDealGetDouble(t, DEAL_VOLUME);
   double   price  = HistoryDealGetDouble(t, DEAL_PRICE);
   double   res    = HistoryDealGetDouble(t, DEAL_PROFIT) + HistoryDealGetDouble(t, DEAL_SWAP) +
                     HistoryDealGetDouble(t, DEAL_COMMISSION) + HistoryDealGetDouble(t, DEAL_FEE);
   datetime tm     = (datetime)HistoryDealGetInteger(t, DEAL_TIME);
   long     reason = HistoryDealGetInteger(t, DEAL_REASON);
   ulong    pos    = (ulong)HistoryDealGetInteger(t, DEAL_POSITION_ID);
   string   cmt    = HistoryDealGetString(t, DEAL_COMMENT);
   int      digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   string   when   = ParisStr(ServerToParis(tm));
   double   bal    = AccountInfoDouble(ACCOUNT_BALANCE);

   //--- OUVERTURE
   if(entry == DEAL_ENTRY_IN)
     {
      string dir = (type == DEAL_TYPE_BUY) ? "ACHAT" : "VENTE";
      double sl = 0, tp = 0;
      if(PositionSelectByTicket(pos))
        {
         sl = PositionGetDouble(POSITION_SL);
         tp = PositionGetDouble(POSITION_TP);
        }
      string riskTxt = "pas de stop !";
      double riskMoney = 0;
      if(sl > 0)
        {
         ENUM_ORDER_TYPE ot = (type == DEAL_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
         if(OrderCalcProfit(ot, sym, vol, price, sl, riskMoney))
           {
            riskMoney = MathAbs(riskMoney);
            riskTxt = Money(riskMoney) + StringFormat(" (%.2f %% du capital)", bal > 0 ? riskMoney / bal * 100.0 : 0.0);
           }
        }
      string strat = StratFromComment(cmt, magic);
      string msg = StringFormat("▶ TRADE OUVERT : %s %s\n%.2f lot a %s\nStop %s | Objectif %s\nRisque %s\nStrategie %s | %s (Paris)",
                                dir, sym, vol, DoubleToString(price, digits),
                                sl > 0 ? DoubleToString(sl, digits) : "aucun",
                                tp > 0 ? DoubleToString(tp, digits) : "aucun (stop suiveur)",
                                riskTxt, strat, when);
      Notify("Trade ouvert " + sym, msg);
      Journal(StringFormat("%s;ouverture;%s;%s;%.2f;%s;%s;%s;;;;%s;%I64u;%I64u", when, sym, dir, vol,
                           DoubleToString(price, digits), DoubleToString(sl, digits), DoubleToString(tp, digits),
                           strat, magic, pos));
      return;
     }

   //--- FERMETURE (totale, partielle, retournement ou fermeture par position opposee)
   // le deal de sortie est une VENTE quand on ferme un ACHAT
   int    posDir = (type == DEAL_TYPE_SELL) ? 1 : -1;
   string dir    = posDir > 0 ? "ACHAT" : "VENTE";
   bool   stillOpen = PositionSelectByTicket(pos);

   double openPrice = 0, inVol = 0;
   datetime openTime = 0;
   string strat = "";
   if(HistorySelectByPosition(pos))
     {
      int nd = HistoryDealsTotal();
      for(int i = 0; i < nd; i++)
        {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0) continue;
         if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
         double v = HistoryDealGetDouble(d, DEAL_VOLUME);
         openPrice += HistoryDealGetDouble(d, DEAL_PRICE) * v;
         inVol     += v;
         datetime ot = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         if(openTime == 0 || ot < openTime) openTime = ot;
         if(strat == "") strat = StratFromComment(HistoryDealGetString(d, DEAL_COMMENT), magic);
        }
     }
   if(inVol > 0) openPrice /= inVol;
   if(strat == "") strat = StratFromComment("", magic);

   double pips = (openPrice > 0) ? (price - openPrice) * posDir / PipSize(sym) : 0;
   double balBefore = bal - res;
   double pct = balBefore > 0 ? res / balBefore * 100.0 : 0;

   string head = res >= 0 ? "✅ TRADE GAGNANT " : "❌ TRADE PERDANT ";
   string kind = "";
   if(stillOpen)                     kind = " (fermeture partielle)";
   if(entry == DEAL_ENTRY_INOUT)     kind = " (retournement)";

   // resultat du jour (heure de Paris)
   int n, w; double dayPnl; datetime le;
   ClosedStats(ParisMidnightAsServer(), n, w, dayPnl, le);

   string msg = StringFormat("%s%s (%s)%s\n%s %s %.2f lot : %s -> %s (%+.1f pips)\nSortie : %s | duree %s\nStrategie %s | %s (Paris)\nAujourd'hui : %d trade(s), %d gagnant(s), %s\nSolde : %s",
                             head, Money(res, true), Pct(pct), kind,
                             dir, sym, vol,
                             openPrice > 0 ? DoubleToString(openPrice, digits) : "?", DoubleToString(price, digits), pips,
                             ReasonText(reason), openTime > 0 ? Duration((long)(tm - openTime)) : "?",
                             strat, when,
                             n, w, Money(dayPnl, true),
                             Money(bal));
   Notify((res >= 0 ? "Trade gagnant " : "Trade perdant ") + sym, msg);
   Journal(StringFormat("%s;fermeture;%s;%s;%.2f;%s;;;%.2f;%.1f;%s;%s;%I64u;%I64u", when, sym, dir, vol,
                        DoubleToString(price, digits), res, pips, ReasonText(reason), strat, magic, pos));
  }

// Lit l'historique et traite chaque nouveau deal une seule fois.
// Marche aussi pour les trades fermes pendant une coupure (stop touche cote serveur).
void ScanDeals()
  {
   datetime from = gLastDealTime > 0 ? gLastDealTime - 300 : TimeTradeServer() - 86400;
   if(!HistorySelect(from, TimeTradeServer() + 86400))
      return;
   int total = HistoryDealsTotal();
   ulong list[];
   int k = 0;
   for(int i = 0; i < total; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t > gLastDeal)
        {
         ArrayResize(list, k + 1);
         list[k++] = t;
        }
     }
   if(k == 0)
      return;
   ArraySort(list);
   for(int i = 0; i < k; i++)
     {
      ProcessDeal(list[i]);
      gLastDeal = list[i];
      if(HistoryDealSelect(list[i]))
        {
         datetime tm = (datetime)HistoryDealGetInteger(list[i], DEAL_TIME);
         if(tm > gLastDealTime) gLastDealTime = tm;
        }
      GVSet("lastDeal", (double)gLastDeal);
      GVSet("lastDealTime", (double)gLastDealTime);
     }
  }

//+------------------------------------------------------------------+
//| Etat du marche et recap                                          |
//+------------------------------------------------------------------+
string MarketLine(const int i)
  {
   string s = gSyms[i];
   double bid = SymbolInfoDouble(s, SYMBOL_BID);
   int digits = (int)SymbolInfoInteger(s, SYMBOL_DIGITS);
   if(bid <= 0)
      return s + " : pas de prix";
   double c[], ma[], rsi[], atr[];
   if(CopyClose(s, PERIOD_D1, 1, 1, c) != 1 || CopyBuffer(gMa[i], 0, 0, 1, ma) != 1 ||
      CopyBuffer(gRsi[i], 0, 1, 1, rsi) != 1 || CopyBuffer(gAtr[i], 0, 1, 1, atr) != 1 || c[0] <= 0)
      return s + " " + DoubleToString(bid, digits) + " (donnees en chargement)";
   double chg   = (bid - c[0]) / c[0] * 100.0;
   string trend = bid > ma[0] ? "haussier" : "baissier";
   double hi = iHigh(s, PERIOD_D1, 0), lo = iLow(s, PERIOD_D1, 0);
   double ratio = atr[0] > 0 ? (hi - lo) / atr[0] : 0;
   string vol = ratio < 0.6 ? "calme" : (ratio < 1.3 ? "normal" : "agite");
   string line = StringFormat("%s %s (%s) %s, %s", s, DoubleToString(bid, digits), Pct(chg), trend, vol);
   if(rsi[0] < 10 && c[0] > ma[0])
      line += ", repli a l'achat (RSI2 " + DoubleToString(rsi[0], 0) + ")";
   else if(rsi[0] > 90)
      line += ", tres tendu (RSI2 " + DoubleToString(rsi[0], 0) + ")";
   return line;
  }

void SendRecap(const string title)
  {
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   int n, w; double pnl; datetime le;
   int nw, ww; double pnlw; datetime lew;
   int na, wa; double pnla; datetime lea;
   ClosedStats(ParisMidnightAsServer(), n, w, pnl, le);
   ClosedStats(ParisMondayAsServer(), nw, ww, pnlw, lew);
   ClosedStats(gStartTime, na, wa, pnla, lea);
   double dd = gPeakEquity > 0 ? (gPeakEquity - eq) / gPeakEquity * 100.0 : 0;
   bool algo = (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
   bool conn = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);

   string msg = StringFormat("■ %s - %s (Paris)\n", title, ParisStr(NowParis()));
   msg += StringFormat("Robot : Algo Trading %s, connexion %s\n", algo ? "ON" : "COUPE !", conn ? "OK" : "PERDUE !");
   msg += StringFormat("Solde %s | Capital %s | Latent %s\n", Money(bal), Money(eq), Money(eq - bal, true));
   msg += StringFormat("Jour : %d trade(s), %d gagnant(s), %s\n", n, w, Money(pnl, true));
   msg += StringFormat("Semaine : %d trade(s), %s\n", nw, Money(pnlw, true));
   msg += StringFormat("Depuis le lancement : %d trade(s), %s (%s), %.0f %% gagnants\n", na, Money(eq - gStartBalance, true),
                       Pct(gStartBalance > 0 ? (eq - gStartBalance) / gStartBalance * 100.0 : 0.0),
                       na > 0 ? 100.0 * wa / na : 0.0);
   msg += StringFormat("Baisse depuis le plus haut : %.1f %%\n", dd);

   if(InpNoTradeAlertDays > 0)
     {
      datetime last = (lea > gLastDealTime) ? lea : gLastDealTime;
      long limit = (long)InpNoTradeAlertDays * 86400;
      long now = (long)TimeTradeServer();
      if(now - (long)gStartTime > limit && (last == 0 || now - (long)last > limit))
         msg += StringFormat("⚠ Aucun trade depuis plus de %d jours : verifie que le robot tourne.\n", InpNoTradeAlertDays);
     }

   // positions ouvertes
   int open = 0;
   string posTxt = "";
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(!MagicOk((ulong)PositionGetInteger(POSITION_MAGIC))) continue;
      open++;
      double p = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      posTxt += StringFormat("- %s %s %.2f lot : %s\n",
                             PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "ACHAT" : "VENTE",
                             PositionGetString(POSITION_SYMBOL), PositionGetDouble(POSITION_VOLUME), Money(p, true));
     }
   msg += StringFormat("Positions ouvertes : %d\n", open) + posTxt;

   // marche
   if(ArraySize(gSyms) > 0)
     {
      msg += "Marche :\n";
      for(int i = 0; i < ArraySize(gSyms); i++)
         msg += MarketLine(i) + "\n";
     }
   Notify(title, msg);
  }

//+------------------------------------------------------------------+
//| Surveillance                                                     |
//+------------------------------------------------------------------+
void Watchdog()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > gPeakEquity)
     {
      gPeakEquity = eq;
      GVSet("peak", gPeakEquity);
     }

   // nouveau jour (heure de Paris)
   datetime p = NowParis();
   long dk = DayKey(p);
   if(dk != gParisDay)
     {
      gParisDay = dk;
      gDayStartEquity = eq;
      gLossAlertSent = false;
     }
   if(InpDailyLossAlertPct > 0 && !gLossAlertSent && gDayStartEquity > 0 &&
      eq < gDayStartEquity * (1.0 - InpDailyLossAlertPct / 100.0))
     {
      gLossAlertSent = true;
      Notify("Alerte perte du jour", StringFormat("⚠ ALERTE : le capital a perdu %.2f %% aujourd'hui (%s -> %s).",
             (gDayStartEquity - eq) / gDayStartEquity * 100.0, Money(gDayStartEquity), Money(eq)));
     }

   // bouton Algo Trading
   bool algo = (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
   if(InpAlertAutoTrading && algo != gAutoWasOn)
     {
      Notify("Algo Trading", algo ? "✅ Algo Trading de nouveau ACTIVE : le robot peut trader."
                                  : "⚠ Algo Trading COUPE dans MT5 : le robot ne peut plus trader !");
      gAutoWasOn = algo;
     }

   // connexion au serveur du broker
   bool conn = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   if(!conn && gWasConnected)
      gDisconnectedAt = TimeLocal();
   if(conn && !gWasConnected && InpAlertConnection && gDisconnectedAt > 0)
     {
      long sec = (long)(TimeLocal() - gDisconnectedAt);
      if(sec >= 60)
         Notify("Connexion", StringFormat("⚠ Connexion au broker perdue pendant %s, elle est revenue. Les trades de la coupure sont rattrapes ci-dessous s'il y en a.", Duration(sec)));
     }
   gWasConnected = conn;

   // recap quotidien
   if(InpRecap)
     {
      MqlDateTime dt;
      TimeToStruct(p, dt);
      bool weekend = (dt.day_of_week == 0 || dt.day_of_week == 6);
      if(dk != gLastRecapDay && (InpRecapWeekend || !weekend) &&
         dt.hour * 60 + dt.min >= InpRecapHour * 60 + InpRecapMinute)
        {
         gLastRecapDay = dk;
         GVSet("lastRecapDay", (double)dk);
         SendRecap(dt.day_of_week == 5 ? "RECAP DU JOUR ET DE LA SEMAINE" : "RECAP DU JOUR");
        }
     }
  }

void Panel()
  {
   if(gLastPanelMs != 0 && GetTickCount() - gLastPanelMs < 2000)
      return;
   gLastPanelMs = GetTickCount();
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   int open = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(PositionGetTicket(i) > 0 && MagicOk((ulong)PositionGetInteger(POSITION_MAGIC)))
         open++;
   string push = !InpPush ? "off" : (TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED) ? "OK" : "NON CONFIGURE");
   Comment(StringFormat("TradeNotifier - suivi du compte\nHeure de Paris : %s\nConnexion : %s | Algo Trading : %s\nPush : %s | Telegram : %s | File d'attente : %d\nSolde %s | Capital %s | Latent %s\nPositions suivies : %d\nRecap chaque jour a %02dh%02d (Paris)",
                        ParisStr(NowParis()),
                        TerminalInfoInteger(TERMINAL_CONNECTED) ? "OK" : "PERDUE",
                        TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "ON" : "COUPE",
                        push, InpTelegram ? "on" : "off", ArraySize(gPushQueue),
                        Money(bal), Money(eq), Money(eq - bal, true), open, InpRecapHour, InpRecapMinute));
  }

//+------------------------------------------------------------------+
//| ANALYSE DU MARCHE                                                |
//| Lit les fichiers que le robot de trading ecrit dans              |
//| MQL5\Files\DayTrader\outbox\ (rapport du matin, du soir, et un   |
//| instantane a chaque ouverture / fermeture de trade), ajoute les  |
//| annonces economiques du calendrier MT5, et envoie une analyse    |
//| commentee : redigee par Claude (IA) si une cle API est reglee,   |
//| sinon un commentaire automatique.                                |
//+------------------------------------------------------------------+
string Kv(const string &keys[], const string &vals[], const string key, const string def = "")
  {
   for(int i = 0; i < ArraySize(keys); i++)
      if(keys[i] == key)
         return vals[i];
   return def;
  }

bool ParseKV(const string path, string &keys[], string &vals[])
  {
   ArrayResize(keys, 0);
   ArrayResize(vals, 0);
   int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return false;
   while(!FileIsEnding(h))
     {
      string l = FileReadString(h);
      StringTrimLeft(l);
      StringTrimRight(l);
      if(l == "" || StringGetCharacter(l, 0) == '#')
         continue;
      int p = StringFind(l, "=");
      if(p <= 0)
         continue;
      string k = StringSubstr(l, 0, p);
      string v = StringSubstr(l, p + 1);
      StringTrimRight(k);
      StringTrimLeft(v);
      int n = ArraySize(keys);
      ArrayResize(keys, n + 1);
      ArrayResize(vals, n + 1);
      keys[n] = k;
      vals[n] = v;
     }
   FileClose(h);
   return true;
  }

string ParisHM(const datetime p)
  {
   MqlDateTime dt;
   TimeToStruct(p, dt);
   return StringFormat("%02dh%02d", dt.hour, dt.min);
  }

//--- calendrier economique MT5 ------------------------------------
string CalValue(const long raw, const MqlCalendarEvent &ev)
  {
   if(raw == LONG_MIN)
      return "";
   string s = DoubleToString(raw / 1000000.0, (int)ev.digits);
   switch(ev.multiplier)
     {
      case CALENDAR_MULTIPLIER_THOUSANDS: s += "K";  break;
      case CALENDAR_MULTIPLIER_MILLIONS:  s += "M";  break;
      case CALENDAR_MULTIPLIER_BILLIONS:  s += "Md"; break;
      default: break;
     }
   if(ev.unit == CALENDAR_UNIT_PERCENT)
      s += " %";
   return s;
  }

// Annonces importantes entre fromSrv et toSrv (heure serveur).
// released = true : seulement celles deja publiees (avec le chiffre reel).
string CalendarText(const datetime fromSrv, const datetime toSrv, const string currencies, const bool released)
  {
   if(!InpCalendar || toSrv <= fromSrv)
      return "";
   string cur[];
   int nc = StringSplit(currencies, ',', cur);
   datetime times[];
   string   lines[];
   for(int i = 0; i < nc; i++)
     {
      string c = cur[i];
      StringTrimLeft(c);
      StringTrimRight(c);
      if(c == "")
         continue;
      MqlCalendarValue vals[];
      if(!CalendarValueHistory(vals, fromSrv, toSrv, NULL, c))
         continue;
      for(int j = 0; j < ArraySize(vals); j++)
        {
         MqlCalendarEvent ev;
         if(!CalendarEventById(vals[j].event_id, ev))
            continue;
         if((int)ev.importance < InpCalMinImportance)
            continue;
         bool hasActual = (vals[j].actual_value != LONG_MIN);
         if(released && !hasActual)
            continue;
         string line = ParisHM(ServerToParis(vals[j].time)) + " " + c + " " + ev.name;
         string fc = CalValue(vals[j].forecast_value, ev);
         string pv = CalValue(vals[j].prev_value, ev);
         if(hasActual)
           {
            line += " : " + CalValue(vals[j].actual_value, ev);
            if(fc != "")
              {
               line += " (prevu " + fc + ")";
               if(vals[j].actual_value > vals[j].forecast_value)      line += ", plus haut que prevu";
               else if(vals[j].actual_value < vals[j].forecast_value) line += ", plus bas que prevu";
               else                                                   line += ", conforme";
              }
           }
         else
           {
            if(fc != "") line += " (prevu " + fc;
            if(pv != "") line += (fc != "" ? ", " : " (") + "precedent " + pv;
            if(fc != "" || pv != "") line += ")";
           }
         int n = ArraySize(times);
         ArrayResize(times, n + 1);
         ArrayResize(lines, n + 1);
         times[n] = vals[j].time;
         lines[n] = line;
        }
     }
   // tri par heure
   for(int a = 1; a < ArraySize(times); a++)
     {
      datetime t = times[a];
      string   l = lines[a];
      int b = a - 1;
      while(b >= 0 && times[b] > t)
        {
         times[b + 1] = times[b];
         lines[b + 1] = lines[b];
         b--;
        }
      times[b + 1] = t;
      lines[b + 1] = l;
     }
   string out = "";
   for(int k = 0; k < ArraySize(lines); k++)
      out += "- " + lines[k] + "\n";
   return out;
  }

string SymbolCurrencies(const string sym)
  {
   string a = SymbolInfoString(sym, SYMBOL_CURRENCY_BASE);
   string b = SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT);
   if(a == b || a == "")
      return b;
   if(b == "")
      return a;
   return a + "," + b;
  }

//--- commentaire automatique (sans IA) ----------------------------
int LastDot(const string k)
  {
   for(int i = StringLen(k) - 1; i >= 0; i--)
      if(StringGetCharacter(k, i) == '.')
         return i;
   return -1;
  }

string NiceKey(const string k)
  {
   string s = k;
   StringReplace(s, "_", " ");
   return s;
  }

string Upper(const string s)
  {
   string r = s;
   StringToUpper(r);
   return r;
  }

string Signed(const string v)
  {
   if(v == "")
      return "";
   ushort c = StringGetCharacter(v, 0);
   return (c == '+' || c == '-') ? v : "+" + v;
  }

string VolText(const string rva)
  {
   if(rva == "")
      return "";
   double r = StringToDouble(rva);
   if(r < 0.6)  return StringFormat("journee calme (%.1f fois l'amplitude habituelle)", r);
   if(r < 1.3)  return StringFormat("journee normale (%.1f fois l'amplitude habituelle)", r);
   return StringFormat("journee agitee (%.1f fois l'amplitude habituelle)", r);
  }

// Contexte d'un marche en une ligne. pre = "DE40." pour un rapport, "" pour un trade.
string MarketContext(const string &keys[], const string &vals[], const string pre)
  {
   string out = "";
   string vj = Kv(keys, vals, pre + "var_jour");
   string v5 = Kv(keys, vals, pre + "var_5j");
   string td = Kv(keys, vals, pre + "tendance20j");
   string v20 = Kv(keys, vals, pre + "var_20j");
   string vol = Kv(keys, vals, pre + "volatilite");
   string rva = Kv(keys, vals, pre + "range_vs_atr");
   if(vj != "")  out += "jour " + Signed(vj) + " %";
   if(v5 != "")  out += (out == "" ? "" : ", ") + "5 jours " + Signed(v5) + " %";
   if(td != "")  out += (out == "" ? "" : ", ") + "tendance 20 j " + td + (v20 != "" ? " (" + Signed(v20) + " %)" : "");
   if(vol != "") out += (out == "" ? "" : ", ") + "volatilite " + vol;
   string vt = VolText(rva);
   if(vt != "")  out += (out == "" ? "" : ", ") + vt;
   return out;
  }

// Liste des marches d'un rapport : la cle marches= si elle existe, sinon les prefixes SYMBOLE.champ
int ReportSymbols(const string &keys[], const string &vals[], string &syms[])
  {
   ArrayResize(syms, 0);
   string list = Kv(keys, vals, "marches");
   if(list != "")
     {
      string parts[];
      int n = StringSplit(list, ',', parts);
      for(int i = 0; i < n; i++)
        {
         string s = parts[i];
         StringTrimLeft(s);
         StringTrimRight(s);
         if(s == "") continue;
         int k = ArraySize(syms);
         ArrayResize(syms, k + 1);
         syms[k] = s;
        }
      return ArraySize(syms);
     }
   for(int i = 0; i < ArraySize(keys); i++)
     {
      if(StringFind(keys[i], "strategie.") == 0 || StringFind(keys[i], "bilan.") == 0)
         continue;
      int p = LastDot(keys[i]);
      if(p <= 0)
         continue;
      string s = StringSubstr(keys[i], 0, p);
      bool found = false;
      for(int j = 0; j < ArraySize(syms); j++)
         if(syms[j] == s) { found = true; break; }
      if(!found)
        {
         int k = ArraySize(syms);
         ArrayResize(syms, k + 1);
         syms[k] = s;
        }
     }
   return ArraySize(syms);
  }

string ReportCommentary(const string &keys[], const string &vals[], const string type, const string cal)
  {
   string syms[];
   int ns = ReportSymbols(keys, vals, syms);
   double var[];
   bool   hasVar[];
   ArrayResize(var, ns);
   ArrayResize(hasVar, ns);
   for(int i = 0; i < ns; i++)
     {
      string v = Kv(keys, vals, syms[i] + ".var_jour", "");
      hasVar[i] = (v != "");
      var[i] = hasVar[i] ? StringToDouble(v) : 0;
     }
   // de la plus forte hausse a la plus forte baisse
   int idx[];
   ArrayResize(idx, ns);
   for(int i = 0; i < ns; i++) idx[i] = i;
   for(int a = 1; a < ns; a++)
     {
      int x = idx[a];
      int b = a - 1;
      while(b >= 0 && var[idx[b]] < var[x]) { idx[b + 1] = idx[b]; b--; }
      idx[b + 1] = x;
     }

   string head = (type == "MATIN") ? "☀ RAPPORT DU MATIN" : "☾ RAPPORT DU SOIR";
   string out = head + " - " + ParisStr(NowParis()) + " (Paris)\n";
   string up = "", down = "";
   for(int k = 0; k < ns; k++)
     {
      int i = idx[k];
      if(!hasVar[i]) continue;
      string nm = Kv(keys, vals, syms[i] + ".nom", syms[i]);
      string t = nm + " " + Pct(var[i]);
      if(var[i] > 0)      up   += (up == "" ? "" : ", ") + t;
      else if(var[i] < 0) down = t + (down == "" ? "" : ", ") + down;
     }
   if(up != "")   out += "En hausse : " + up + "\n";
   if(down != "") out += "En baisse : " + down + "\n";

   // robot
   if(Upper(Kv(keys, vals, "coupe_circuit")) == "OUI")
      out += "⚠ Coupe-circuit du robot ACTIVE : il ne prend plus de trade.\n";
   if(type == "SOIR" && Kv(keys, vals, "trades_fermes_jour") != "")
      out += StringFormat("Robot aujourd'hui : %s trade(s) ferme(s), %s gagnant(s), %s perdant(s), resultat %s %s\n",
                          Kv(keys, vals, "trades_fermes_jour"), Kv(keys, vals, "gagnants_jour", "?"), Kv(keys, vals, "perdants_jour", "?"),
                          Signed(Kv(keys, vals, "resultat_bot_jour", "0")), Kv(keys, vals, "devise", Cur()));
   for(int j = 0; j < ArraySize(keys); j++)
     {
      if(StringFind(keys[j], "strategie.") != 0) continue;
      int p = LastDot(keys[j]);
      if(StringSubstr(keys[j], p + 1) != "plan") continue;
      string st = StringSubstr(keys[j], 10, p - 10);
      string sy = Kv(keys, vals, "strategie." + st + ".symbole");
      out += "Plan " + st + (sy != "" ? " (" + sy + ")" : "") + " : " + vals[j] + "\n";
     }

   // detail par marche
   out += "Detail :\n";
   for(int k = 0; k < ns; k++)
     {
      int i = idx[k];
      string ctx = MarketContext(keys, vals, syms[i] + ".");
      if(ctx == "") continue;
      out += "- " + Kv(keys, vals, syms[i] + ".nom", syms[i]) + " : " + ctx + "\n";
     }
   if(cal != "")
      out += (type == "MATIN" ? "Annonces du jour :\n" : "Annonces publiees aujourd'hui :\n") + cal;
   else
      out += (type == "MATIN" ? "Pas d'annonce economique majeure aujourd'hui.\n" : "Pas d'annonce economique majeure publiee aujourd'hui.\n");
   return out;
  }

// Lecture automatique d'un trade ferme a partir du MFE / MAE
string TradeReading(const string &keys[], const string &vals[])
  {
   string mfeR = Kv(keys, vals, "mfe_R"), maeR = Kv(keys, vals, "mae_R"), resR = Kv(keys, vals, "resultat_R");
   if(mfeR == "" || maeR == "" || resR == "")
      return "";
   double f = StringToDouble(mfeR), a = StringToDouble(maeR), r = StringToDouble(resR);
   string sortie = Kv(keys, vals, "raison_sortie");
   if(r < 0 && f >= 1.0)
      return StringFormat("Il etait gagnant de %.1f R avant de se retourner : le gain s'est evapore.", f);
   if(r < 0 && f < 0.2)
      return "Il est parti contre toi presque tout de suite : faux signal ou mauvais moment d'entree.";
   if(r < 0)
      return StringFormat("Il a ete un peu gagnant (%.1f R au mieux) puis a perdu.", f);
   if(r > 0 && a <= -0.8)
      return StringFormat("Il a failli toucher le stop (%.1f R au pire) avant de repartir dans le bon sens.", a);
   if(r > 0 && f > r + 0.8)
      return StringFormat("Il est monte jusqu'a %.1f R avant de rendre une partie du gain.", f);
   if(r > 0)
      return "Trade propre : il est alle dans le bon sens sans trop reculer.";
   return "Trade nul ou presque.";
  }

string TradeCommentary(const string &keys[], const string &vals[], const string type, const string cal)
  {
   string nm    = Kv(keys, vals, "nom", Kv(keys, vals, "symbole"));
   string sens  = Upper(Kv(keys, vals, "sens"));
   string strat = Kv(keys, vals, "strategie");
   string dev   = Kv(keys, vals, "devise", Cur());
   string out;
   if(type == "OUVERTURE")
     {
      out = StringFormat("▶ AVANT LE TRADE : %s %s (%s)\n", sens, nm, strat);
      string re = Kv(keys, vals, "raison_entree");
      if(re != "") out += "Pourquoi : " + re + "\n";
      out += StringFormat("Prix %s, stop %s, objectif %s, risque %s %s\n", Kv(keys, vals, "prix", "?"), Kv(keys, vals, "stop", "?"),
                          Kv(keys, vals, "objectif", "?"), Kv(keys, vals, "risque", "?"), dev);
     }
   else
     {
      string res = Signed(Kv(keys, vals, "resultat", "0"));
      string issue = Kv(keys, vals, "issue");
      bool win = (issue == "gagnant") || (issue == "" && StringToDouble(res) > 0);
      out = StringFormat("%s APRES LE TRADE : %s %s (%s) %s %s %s (%s R)\n", win ? "✅" : "❌", sens, nm, strat,
                         issue != "" ? issue : (win ? "gagnant" : "perdant"), res, dev, Signed(Kv(keys, vals, "resultat_R", "?")));
      out += StringFormat("Entree %s, sortie %s apres %s min : %s\n", Kv(keys, vals, "prix_entree", "?"), Kv(keys, vals, "prix", "?"),
                          Kv(keys, vals, "duree_min", "?"), Kv(keys, vals, "raison_sortie", "?"));
      if(Kv(keys, vals, "mfe") != "")
         out += StringFormat("Pendant le trade : au mieux %s %s (%s R), au pire %s %s (%s R)\n",
                             Signed(Kv(keys, vals, "mfe")), dev, Signed(Kv(keys, vals, "mfe_R", "?")),
                             Kv(keys, vals, "mae"), dev, Kv(keys, vals, "mae_R", "?"));
      string rd = TradeReading(keys, vals);
      if(rd != "") out += "Lecture : " + rd + "\n";
     }
   string ctx = MarketContext(keys, vals, "");
   if(ctx != "")
      out += "Marche : " + ctx + "\n";
   if(cal != "")
      out += (type == "OUVERTURE" ? "Annonces dans les 3 prochaines heures :\n" : "Annonces publiees pendant le trade :\n") + cal;
   else
      out += (type == "OUVERTURE" ? "Pas d'annonce importante dans les 3 prochaines heures.\n" : "Pas d'annonce importante pendant le trade.\n");
   return out;
  }

//--- analyse par l'IA (API Claude) ---------------------------------
string JsonEsc(const string s)
  {
   string r = s;
   StringReplace(r, "\\", "\\\\");
   StringReplace(r, "\"", "\\\"");
   StringReplace(r, "\r", "");
   StringReplace(r, "\n", "\\n");
   StringReplace(r, "\t", " ");
   return r;
  }

int HexVal(const ushort c)
  {
   if(c >= '0' && c <= '9') return c - '0';
   if(c >= 'a' && c <= 'f') return c - 'a' + 10;
   if(c >= 'A' && c <= 'F') return c - 'A' + 10;
   return 0;
  }

// lit une chaine JSON qui commence juste apres le guillemet ouvrant
int JsonReadString(const string s, int i, string &out)
  {
   out = "";
   int n = StringLen(s);
   while(i < n)
     {
      ushort c = StringGetCharacter(s, i);
      if(c == '"')
         return i + 1;
      if(c == '\\' && i + 1 < n)
        {
         ushort e = StringGetCharacter(s, i + 1);
         if(e == 'u' && i + 5 < n)
           {
            int v = 0;
            for(int k = 2; k < 6; k++)
               v = v * 16 + HexVal(StringGetCharacter(s, i + k));
            out += ShortToString((ushort)v);
            i += 6;
            continue;
           }
         if(e == 'n')      out += "\n";
         else if(e == 't') out += " ";
         else if(e == 'r') { }
         else              out += ShortToString(e);
         i += 2;
         continue;
        }
      out += ShortToString(c);
      i++;
     }
   return n;
  }

string JsonField(const string s, const string key)
  {
   int p = StringFind(s, "\"" + key + "\":\"");
   if(p < 0)
      return "";
   string out;
   JsonReadString(s, p + StringLen(key) + 4, out);
   return out;
  }

// concatene tous les blocs de texte de la reponse
string JsonAllTexts(const string s)
  {
   string all = "";
   int pos = 0;
   int n = StringLen(s);
   while(pos < n)
     {
      int p = StringFind(s, "\"text\":", pos);
      if(p < 0)
         break;
      int q = p + 7;
      while(q < n && StringGetCharacter(s, q) == ' ') q++;
      if(q >= n || StringGetCharacter(s, q) != '"')
        {
         pos = q;
         continue;
        }
      string t;
      pos = JsonReadString(s, q + 1, t);
      all += t;
     }
   return all;
  }

bool AiBudgetOk()
  {
   long day = DayKey(NowParis());
   if((long)GVGet("aiDay", -1) != day)
     {
      GVSet("aiDay", (double)day);
      GVSet("aiCount", 0);
     }
   return GVGet("aiCount", 0) < InpAiMaxPerDay;
  }

string AiSystemPrompt()
  {
   return "Tu es l'analyste de marche d'un jeune trader debutant qui fait tourner un robot de trading sur un compte DEMO MetaTrader 5. "
          "Tu ecris en francais simple, direct et honnete. Si tu utilises un mot technique, explique-le en quelques mots. "
          "Ton texte part sur Telegram : texte brut, sans Markdown, sans tableau, phrases courtes, quelques puces avec '- ' si utile. "
          "Appuie-toi d'abord sur les donnees fournies par le robot. Quand tu cites une news, donne la source en un mot (ex. Reuters). "
          "Si tu ne sais pas pourquoi un marche a bouge, dis-le franchement au lieu d'inventer. Les heures sont en heure de Paris. "
          "Tu ne donnes pas d'ordre d'achat ou de vente : tu expliques ce qui se passe et ce que ca veut dire pour les strategies du robot. "
          "Strategies du robot : ORB30US = cassure du range des 30 premieres minutes de la seance US ; ORB15US = trade dans le sens de la 1re bougie de 15 min US ; "
          "ORB30DAX = cassure des 30 premieres minutes du DAX ; DIP = achat d'un indice sur repli (RSI(2) bas) en tendance haussiere ; "
          "REPLI = achat d'un indice US tombe d'une demi-ATR sous son ouverture ; ASIE = retour a la moyenne la nuit sur EURCHF ; "
          "DONCH = suivi de tendance sur cassure du plus haut/bas de 20 jours. "
          "Robot DayTrader (tout est ferme le jour meme, achat seulement si la tendance 20 jours monte, vente seulement si elle baisse) : "
          "DAX1B = trade dans le sens de la 1re bougie de 15 min du DAX, stop de l'autre cote de la bougie ; "
          "DAXBRUIT = sur le DAX, toutes les 30 min, achat si le prix sort au-dessus de sa zone de bruit habituelle et de la VWAP, vente en dessous, sortie au retour dans la zone ; "
          "ORIB = or : range de la 1re heure de New York, apres la 1re cassure ordre limite 25 % a l'interieur du range, stop 60 % du range, objectif 50 % au-dela. "
          "R = le risque pris sur un trade (1 R = la perte si le stop est touche) ; MFE = meilleur gain latent pendant le trade, MAE = pire perte latente.";
  }

string AiTask(const string type)
  {
   if(type == "MATIN")
      return "Ecris le briefing du matin (1300 caracteres maximum) : 1) ce qui a monte et baisse et de combien, 2) pourquoi, avec les news recentes (cherche sur le web), "
             "3) les annonces de la journee qui peuvent faire bouger les marches du robot et a quelle heure, 4) en une phrase, le niveau de risque du jour (calme, normal ou agite).";
   if(type == "SOIR")
      return "Ecris le bilan du soir (1300 caracteres maximum) : 1) ce qui a bouge aujourd'hui et pourquoi (news, annonces publiees comparees aux previsions ; cherche sur le web), "
             "2) comment ca a touche les trades du robot (resultats fournis), 3) ce qu'il faut surveiller demain.";
   if(type == "OUVERTURE")
      return "Le robot vient d'ouvrir ce trade. En 600 caracteres maximum : pourquoi il est entre (la regle de sa strategie), si le contexte est plutot favorable ou non "
             "(tendance, volatilite), et les risques a surveiller (annonces a venir).";
   return "Le robot vient de fermer ce trade. En 600 caracteres maximum : ce qui s'est passe, pourquoi il a gagne ou perdu, et si c'est un resultat normal pour cette strategie "
          "ou un signe que le contexte ne lui convient pas.";
  }

// Renvoie "" en cas d'echec (on utilise alors le commentaire automatique)
string AskClaude(const string type, const string data)
  {
   if(!InpAI || InpAiKey == "" || !AiBudgetOk())
      return "";
   bool report = (type == "MATIN" || type == "SOIR");
   bool web    = InpAiWebSearch && (report || InpAiWebSearchTrades);
   string model = InpAiModel;
   bool fallbacks = (StringFind(model, "opus") >= 0 || StringFind(model, "fable") >= 0 || model == "claude-sonnet-5-5");

   for(int attempt = 0; attempt < 2; attempt++)
     {
      string body = "{\"model\":\"" + JsonEsc(model) + "\",\"max_tokens\":8000,";
      if(fallbacks)
         body += "\"fallbacks\":\"default\",";
      body += "\"system\":\"" + JsonEsc(AiSystemPrompt()) + "\",";
      body += "\"messages\":[{\"role\":\"user\",\"content\":\"" + JsonEsc(AiTask(type) + "\n\nDONNEES DU ROBOT ET DE MT5 :\n" + data) + "\"}]";
      if(web)
        {
         string tool = (StringFind(model, "haiku") >= 0) ? "web_search_20250305" : "web_search_20260209";
         body += ",\"tools\":[{\"type\":\"" + tool + "\",\"name\":\"web_search\",\"max_uses\":3}]";
        }
      body += "}";

      char req[], res[];
      int n = StringToCharArray(body, req, 0, WHOLE_ARRAY, CP_UTF8);
      if(n > 0)
         ArrayResize(req, n - 1);
      string headers = "Content-Type: application/json\r\n"
                       "x-api-key: " + InpAiKey + "\r\n"
                       "anthropic-version: 2026-10-21\r\n";
      if(fallbacks)
         headers += "anthropic-beta: server-side-fallback-2026-07-01\r\n";
      string rh;
      ResetLastError();
      int code = WebRequest("POST", "https://api.anthropic.com/v1/messages", headers, 120000, req, res, rh);
      GVSet("aiCount", GVGet("aiCount", 0) + 1);
      string resp = CharArrayToString(res, 0, WHOLE_ARRAY, CP_UTF8);
      if(code == 200)
        {
         string stop = JsonField(resp, "stop_reason");
         string txt  = JsonAllTexts(resp);
         StringTrimLeft(txt);
         StringTrimRight(txt);
         if(stop == "refusal" || txt == "")
           {
            PrintFormat("[Analyse] IA : pas de texte (stop_reason=%s)", stop);
            return "";
           }
         return txt;
        }
      if(code == -1)
        {
         PrintFormat("[Analyse] IA : WebRequest refuse (erreur %d). Ajoute https://api.anthropic.com dans Outils > Options > Expert Advisors > WebRequest.", GetLastError());
         return "";
        }
      PrintFormat("[Analyse] IA : erreur HTTP %d : %s", code, StringSubstr(resp, 0, 300));
      if(!web || code == 401 || code == 429 || code >= 500)
         return "";
      web = false; // la recherche web n'est peut-etre pas activee : on reessaie sans
     }
   return "";
  }

//--- envoi d'un texte long ------------------------------------------
// Push MT5 : 255 caracteres. Si Telegram est actif, le telephone recoit
// un resume en push et l'analyse complete sur Telegram.
void NotifyLong(const string subject, const string shortText, const string longText)
  {
   Print("[Analyse] ", longText);
   if(InpTelegram)
      SendTelegram(longText);
   if(InpEmail)
      SendMail(subject, longText);
   if(InpPush)
     {
      if(InpTelegram)
         QueuePush(shortText + "\n(analyse complete sur Telegram)");
      else
        {
         // sans Telegram : 4 notifications maximum
         string t = longText;
         if(StringLen(t) > 980)
            t = StringSubstr(t, 0, 977) + "...";
         QueuePush(t);
        }
     }
  }

string FirstLine(const string s)
  {
   int p = StringFind(s, "\n");
   return p < 0 ? s : StringSubstr(s, 0, p);
  }

void ProcessAnalysisFile(const string dir, const string name)
  {
   string path = dir + name;
   string keys[], vals[];
   if(!ParseKV(path, keys, vals))
      return;
   string type = Kv(keys, vals, "type");
   StringToUpper(type);
   if(type == "")
     {
      // type tire du nom : AAAAMMJJ_HHMMSS_TYPE_POSITION.txt
      string parts[];
      if(StringSplit(name, '_', parts) >= 3)
         type = parts[2];
     }

   datetime nowSrv = TimeTradeServer();
   string cal = "";
   string extra = "";
   if(type == "MATIN")
      cal = CalendarText(nowSrv, ParisToServer(DayStart(NowParis()) + 86400), InpCalCurrencies, false);
   else if(type == "SOIR")
     {
      cal = CalendarText(ParisMidnightAsServer(), nowSrv, InpCalCurrencies, true);
      int n, w; double pnl; datetime le;
      ClosedStats(ParisMidnightAsServer(), n, w, pnl, le);
      extra = StringFormat("Compte (tous robots) aujourd'hui : %d trade(s) ferme(s), %d gagnant(s), %s. Solde %s.\n",
                           n, w, Money(pnl, true), Money(AccountInfoDouble(ACCOUNT_BALANCE)));
     }
   else
     {
      string sym = Kv(keys, vals, "symbole");
      string curs = (sym != "" && SymbolSelect(sym, true)) ? SymbolCurrencies(sym) : InpCalCurrencies;
      if(type == "OUVERTURE")
         cal = CalendarText(nowSrv, nowSrv + 3 * 3600, curs, false);
      else
        {
         // pendant le trade : depuis l'ouverture de la position
         datetime openT = nowSrv - 6 * 3600;
         string dm = Kv(keys, vals, "duree_min");
         ulong pos = (ulong)StringToInteger(Kv(keys, vals, "position", "0"));
         if(dm != "")
            openT = nowSrv - (datetime)(StringToInteger(dm) * 60 + 300);
         else if(pos > 0 && HistorySelectByPosition(pos) && HistoryDealsTotal() > 0)
           {
            ulong d = HistoryDealGetTicket(0);
            if(d > 0) openT = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
           }
         cal = CalendarText(openT, nowSrv, curs, true);
        }
     }

   string autoTxt = (type == "MATIN" || type == "SOIR") ? ReportCommentary(keys, vals, type, cal)
                                                      : TradeCommentary(keys, vals, type, cal);
   if(extra != "")
      autoTxt += extra;

   // le robot a envoye son propre rapport : pas de rapport de secours aujourd'hui
   if((type == "MATIN" || type == "SOIR") && Kv(keys, vals, "source") != "TradeNotifier")
      GVSet("got" + type, (double)DayKey(NowParis()));

   // pour l'IA : le commentaire + toutes les donnees brutes du fichier
   string raw = "";
   for(int j = 0; j < ArraySize(keys); j++)
      raw += keys[j] + "=" + vals[j] + "\n";
   string msg = autoTxt;
   string ai = AskClaude(type, autoTxt + "\nDONNEES BRUTES (cle=valeur) :\n" + raw);
   if(ai != "")
      msg = FirstLine(autoTxt) + "\n" + ai;
   else if(InpAI && InpAiKey != "")
      msg = autoTxt + "(analyse IA indisponible, commentaire automatique)";

   string subject = (type == "MATIN") ? "Rapport du matin" : ((type == "SOIR") ? "Rapport du soir" : "Analyse du trade");
   string shortText = FirstLine(autoTxt);
   if(type == "MATIN" || type == "SOIR")
     {
      string l2 = "";
      int p = StringFind(autoTxt, "\n");
      if(p > 0)
        {
         string rest = StringSubstr(autoTxt, p + 1);
         l2 = FirstLine(rest);
        }
      shortText += "\n" + l2;
     }
   NotifyLong(subject, shortText, msg);
   Journal(StringFormat("%s;analyse_%s;%s;;;;;;;;;%s;;%s", ParisStr(NowParis()), type,
                        Kv(keys, vals, "symbole"), Kv(keys, vals, "strategie"), Kv(keys, vals, "position")));

   // archive
   string arch = InpOutboxArchive + name;
   if(!FileMove(path, 0, arch, FILE_REWRITE))
      FileDelete(path);
  }

//--- rapports propres a TradeNotifier (si le robot n'en ecrit pas) ---
string FileStamp(const datetime p)
  {
   MqlDateTime dt;
   TimeToStruct(p, dt);
   return StringFormat("%04d%02d%02d_%02d%02d%02d", dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
  }

void WriteOwnReport(const string type)
  {
   string base = InpOutboxDir + FileStamp(TimeTradeServer()) + "_" + type + "_0";
   string tmp  = base + ".tmp";
   int h = FileOpen(tmp, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, "type=" + type + "\r\n");
   FileWriteString(h, "heure_serveur=" + TimeToString(TimeTradeServer(), TIME_DATE | TIME_MINUTES) + "\r\n");
   FileWriteString(h, "source=TradeNotifier\r\n");
   string list = "";
   for(int i = 0; i < ArraySize(gSyms); i++)
      list += (i == 0 ? "" : ",") + gSyms[i];
   FileWriteString(h, "marches=" + list + "\r\n");
   for(int i = 0; i < ArraySize(gSyms); i++)
     {
      string sym = gSyms[i];
      double bid = SymbolInfoDouble(sym, SYMBOL_BID);
      double c[], ma[], rsi[], atr[];
      if(bid <= 0 || CopyClose(sym, PERIOD_D1, 1, 21, c) != 21 || CopyBuffer(gMa[i], 0, 0, 1, ma) != 1 ||
         CopyBuffer(gRsi[i], 0, 1, 1, rsi) != 1 || CopyBuffer(gAtr[i], 0, 1, 1, atr) != 1)
         continue;
      // c[20] = cloture d'hier, c[16] = il y a 5 jours, c[0] = il y a 21 jours
      double d1  = (bid - c[20]) / c[20] * 100.0;
      double d5  = (bid - c[16]) / c[16] * 100.0;
      double d20 = (bid - c[0])  / c[0]  * 100.0;
      double hi = iHigh(sym, PERIOD_D1, 0), lo = iLow(sym, PERIOD_D1, 0);
      FileWriteString(h, StringFormat("%s.var_jour=%+.2f\r\n", sym, d1));
      FileWriteString(h, StringFormat("%s.var_5j=%+.2f\r\n", sym, d5));
      FileWriteString(h, StringFormat("%s.var_20j=%+.2f\r\n", sym, d20));
      FileWriteString(h, StringFormat("%s.tendance20j=%s\r\n", sym, d20 >= 0 ? "haussiere" : "baissiere"));
      FileWriteString(h, StringFormat("%s.mm200=%s\r\n", sym, bid > ma[0] ? "au-dessus" : "en dessous"));
      FileWriteString(h, StringFormat("%s.rsi2=%.0f\r\n", sym, rsi[0]));
      if(atr[0] > 0)
        {
         FileWriteString(h, StringFormat("%s.atr_pct=%.2f\r\n", sym, atr[0] / bid * 100.0));
         if(type == "SOIR")
            FileWriteString(h, StringFormat("%s.range_vs_atr=%.2f\r\n", sym, (hi - lo) / atr[0]));
        }
     }
   FileClose(h);
   if(!FileMove(tmp, 0, base + ".txt", FILE_REWRITE))
      FileDelete(tmp);
  }

bool gTestPending = false;
uint gInitMs = 0;

void OwnReportsSchedule()
  {
   // rapport d'essai 15 s apres le lancement (le temps que les indicateurs se chargent)
   if(gTestPending && GetTickCount() - gInitMs > 15000)
     {
      gTestPending = false;
      WriteOwnReport("MATIN");
     }
   if(!InpAnalysis || !InpOwnReports)
      return;
   datetime p = NowParis();
   MqlDateTime dt;
   TimeToStruct(p, dt);
   if(dt.day_of_week == 0 || dt.day_of_week == 6)
      return;
   long dk = DayKey(p);
   int now = dt.hour * 60 + dt.min;
   // rapports de secours : seulement si le robot de trading n'a pas envoye le sien
   if((long)GVGet("ownMatin", -1) != dk && (long)GVGet("gotMATIN", -1) != dk &&
      now >= InpMorningHour * 60 + InpMorningMinute && now < 12 * 60)
     {
      GVSet("ownMatin", (double)dk);
      WriteOwnReport("MATIN");
     }
   if((long)GVGet("ownSoir", -1) != dk && (long)GVGet("gotSOIR", -1) != dk &&
      now >= InpRecapHour * 60 + InpRecapMinute)
     {
      GVSet("ownSoir", (double)dk);
      WriteOwnReport("SOIR");
     }
  }

uint gLastOutboxMs = 0;

void ScanOutbox()
  {
   if(!InpAnalysis)
      return;
   if(gLastOutboxMs != 0 && GetTickCount() - gLastOutboxMs < 5000)
      return;
   gLastOutboxMs = GetTickCount();
   OwnReportsSchedule();
   string files[];
   string name;
   long h = FileFindFirst(InpOutboxDir + "*.txt", name);
   if(h == INVALID_HANDLE)
      return;
   do
     {
      int n = ArraySize(files);
      ArrayResize(files, n + 1);
      files[n] = name;
     }
   while(FileFindNext(h, name));
   FileFindClose(h);
   // ordre chronologique grace au nom AAAAMMJJ_HHMMSS
   for(int a = 1; a < ArraySize(files); a++)
     {
      string x = files[a];
      int b = a - 1;
      while(b >= 0 && StringCompare(files[b], x) > 0) { files[b + 1] = files[b]; b--; }
      files[b + 1] = x;
     }
   int maxN = ArraySize(files) < 3 ? ArraySize(files) : 3; // 3 analyses max par passage
   for(int i = 0; i < maxN; i++)
      ProcessAnalysisFile(InpOutboxDir, files[i]);
  }

//+------------------------------------------------------------------+
//| Evenements                                                       |
//+------------------------------------------------------------------+
int OnInit()
  {
   gPfx = "TN_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "_";

   if(InpPush && !TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED))
      Print("[Notif] Les notifications push ne sont pas activees : Outils > Options > Notifications, coche la case et colle ton MetaQuotes ID.");

   // reprise apres un redemarrage : on garde le dernier deal traite
   gLastDeal     = (ulong)GVGet("lastDeal", 0);
   gLastDealTime = (datetime)(long)GVGet("lastDealTime", 0);
   gStartTime    = (datetime)(long)GVGet("startTime", 0);
   gStartBalance = GVGet("startBalance", 0);
   gPeakEquity   = GVGet("peak", AccountInfoDouble(ACCOUNT_EQUITY));
   gLastRecapDay = (long)GVGet("lastRecapDay", -1);

   if(gStartTime == 0)
     {
      // premier lancement : on ne renvoie pas les vieux trades
      gStartTime    = TimeTradeServer();
      gStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      GVSet("startTime", (double)gStartTime);
      GVSet("startBalance", gStartBalance);
      if(HistorySelect(0, TimeTradeServer() + 86400))
        {
         int total = HistoryDealsTotal();
         for(int i = 0; i < total; i++)
           {
            ulong t = HistoryDealGetTicket(i);
            if(t > gLastDeal)
              {
               gLastDeal = t;
               datetime tm = (datetime)HistoryDealGetInteger(t, DEAL_TIME);
               if(tm > gLastDealTime) gLastDealTime = tm;
              }
           }
        }
      GVSet("lastDeal", (double)gLastDeal);
      GVSet("lastDealTime", (double)gLastDealTime);
     }

   // marches du recap
   string parts[];
   int n = StringSplit(InpMarketSymbols, ',', parts);
   ArrayResize(gSyms, 0);
   ArrayResize(gMa, 0);
   ArrayResize(gRsi, 0);
   ArrayResize(gAtr, 0);
   for(int i = 0; i < n; i++)
     {
      string s = parts[i];
      StringTrimLeft(s);
      StringTrimRight(s);
      if(s == "") continue;
      s += InpSymbolSuffix;
      if(!SymbolSelect(s, true))
        {
         PrintFormat("[Notif] Symbole %s introuvable chez ce broker : ignore dans le recap.", s);
         continue;
        }
      int k = ArraySize(gSyms);
      ArrayResize(gSyms, k + 1);
      ArrayResize(gMa, k + 1);
      ArrayResize(gRsi, k + 1);
      ArrayResize(gAtr, k + 1);
      gSyms[k] = s;
      gMa[k]   = iMA(s, PERIOD_D1, 200, 0, MODE_SMA, PRICE_CLOSE);
      gRsi[k]  = iRSI(s, PERIOD_D1, 2, PRICE_CLOSE);
      gAtr[k]  = iATR(s, PERIOD_D1, 14);
     }

   gAutoWasOn    = (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
   gWasConnected = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   gDayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   gParisDay     = DayKey(NowParis());

   if(InpAnalysis)
     {
      FolderCreate(InpOutboxDir);
      FolderCreate(InpOutboxArchive);
     }
   if(InpAI && InpAiKey == "")
      Print("[Analyse] IA activee mais cle API vide : commentaire automatique a la place.");
   gTestPending = (InpAnalysis && InpTestAnalysis && !MQLInfoInteger(MQL_TESTER));
   gInitMs = GetTickCount();

   EventSetTimer(1);

   if(InpTestOnStart && !MQLInfoInteger(MQL_TESTER))
      Notify("TradeNotifier lance", StringFormat("✅ TradeNotifier lance sur le compte %I64d (%s). Tu recevras un message a chaque ouverture et fermeture de trade, et un recap a %02dh%02d (Paris).",
             AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), InpRecapHour, InpRecapMinute));

   ScanDeals();
   Panel();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i = 0; i < ArraySize(gSyms); i++)
     {
      if(gMa[i]  != INVALID_HANDLE) IndicatorRelease(gMa[i]);
      if(gRsi[i] != INVALID_HANDLE) IndicatorRelease(gRsi[i]);
      if(gAtr[i] != INVALID_HANDLE) IndicatorRelease(gAtr[i]);
     }
   // on tente d'envoyer ce qui reste en file d'attente
   for(int i = 0; i < ArraySize(gPushQueue) && i < 2; i++)
      SendNotification(gPushQueue[i]);
   Comment("");
  }

void OnTrade()
  {
   ScanDeals();
  }

void OnTimer()
  {
   ScanDeals();
   ScanOutbox();
   Watchdog();
   ProcessPushQueue();
   Panel();
  }

void OnTick()
  {
   // rien : tout se passe dans OnTimer et OnTrade
  }
//+------------------------------------------------------------------+
