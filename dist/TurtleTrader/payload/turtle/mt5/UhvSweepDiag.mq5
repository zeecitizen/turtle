//+------------------------------------------------------------------+
//| UhvSweepDiag.mq5 — Smoke test for UhvSweepExhaustion architecture |
//|                                                                   |
//| Tests the FULL async lifecycle in isolation, no entry-signal      |
//| dependency:                                                       |
//|   1. OrderSendAsync entry                                         |
//|   2. TRADE_TRANSACTION_REQUEST acknowledgement                    |
//|   3. TRADE_TRANSACTION_DEAL_ADD with magic match                  |
//|   4. TRADE_TRANSACTION_POSITION confirmation                      |
//|   5. ModifySl (the BE move logic — fixes -$1.09 deficit)          |
//|   6. OrderSendAsync close                                         |
//|   7. Re-bind on EA restart (Amnesia test)                         |
//|                                                                   |
//| USAGE:                                                            |
//|   1. Attach to a separate XAUUSD chart (NOT the same as           |
//|      UhvSweepExhaustion to avoid magic-number collision)          |
//|   2. Set InpRunTest = true                                        |
//|   3. Watch Experts log for [DIAG] tagged messages                 |
//|   4. EA fires: BUY 0.01 → waits 5s → modify SL to BE → 5s → close |
//|   5. Verify each step logs in correct order                       |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — smoke test for UhvSweepExhaustion"
#property version   "1.00"
#property strict

input bool   InpRunTest      = false;  // set true to actually fire trades — start with false to dry-check
input bool   InpCleanupOpen  = true;   // if existing test position found on init, CLOSE it (don't run new test)
input double InpTestLots     = 0.01;   // smallest lot for safety
input int    InpMagicNumber  = 99001;  // DIFFERENT from main EA's 88001
input int    InpHoldSec      = 8;      // seconds between phases (entry → BE → close)

enum ETestPhase {
   PHASE_IDLE        = 0,
   PHASE_ENTRY_SENT  = 1,
   PHASE_ENTRY_FILLED= 2,
   PHASE_BE_MOVED    = 3,
   PHASE_CLOSED      = 4,
   PHASE_DONE        = 5
};

ETestPhase  g_phase = PHASE_IDLE;
ulong       g_request_id = 0;
ulong       g_open_ticket = 0;
double      g_open_price = 0;
datetime    g_phase_start_ts = 0;
double      g_contract_size = 100.0;
bool        g_test_started = false;

void Log(string msg) { Print("[DIAG] ", msg); }

ENUM_ORDER_TYPE_FILLING GetAllowedFillingMode() {
   int filling = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0) return ORDER_FILLING_FOK;
   if((filling & SYMBOL_FILLING_IOC) != 0) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

bool FireBuyEntry() {
   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = _Symbol;
   req.volume       = InpTestLots;
   req.type         = ORDER_TYPE_BUY;
   req.price        = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   req.sl           = req.price - (15.0 / (g_contract_size * InpTestLots)); // -$15 hard SL
   req.deviation    = 20;
   req.magic        = InpMagicNumber;
   req.type_filling = GetAllowedFillingMode();
   req.comment      = "UhvSweepDiag";
   if(!OrderSendAsync(req, res)) {
      Log("[STEP 1 FAIL] OrderSendAsync entry — retcode=" + IntegerToString(res.retcode));
      return false;
   }
   g_request_id = res.request_id;
   Log("[STEP 1] Entry sent. request_id=" + IntegerToString((long)g_request_id) +
       " price=" + DoubleToString(req.price, _Digits) +
       " sl=" + DoubleToString(req.sl, _Digits) +
       " filling=" + IntegerToString(req.type_filling));
   return true;
}

bool MoveToBE() {
   if(g_open_ticket == 0) { Log("[STEP 3 SKIP] no ticket"); return false; }
   if(!PositionSelectByTicket(g_open_ticket)) {
      Log("[STEP 3 FAIL] PositionSelectByTicket — ticket=" + IntegerToString((long)g_open_ticket));
      return false;
   }
   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action   = TRADE_ACTION_SLTP;
   req.position = g_open_ticket;
   req.symbol   = _Symbol;
   req.sl       = g_open_price;  // break-even
   req.tp       = PositionGetDouble(POSITION_TP);
   if(!OrderSendAsync(req, res)) {
      Log("[STEP 3 FAIL] OrderSendAsync modify — retcode=" + IntegerToString(res.retcode));
      return false;
   }
   Log("[STEP 3] BE modify sent. new_sl=" + DoubleToString(g_open_price, _Digits) +
       " request_id=" + IntegerToString((long)res.request_id));
   return true;
}

bool FireClose() {
   if(g_open_ticket == 0) { Log("[STEP 5 SKIP] no ticket"); return false; }
   if(!PositionSelectByTicket(g_open_ticket)) {
      Log("[STEP 5 FAIL] PositionSelectByTicket");
      return false;
   }
   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action       = TRADE_ACTION_DEAL;
   req.position     = g_open_ticket;
   req.symbol       = _Symbol;
   req.volume       = PositionGetDouble(POSITION_VOLUME);
   req.type         = ORDER_TYPE_SELL;  // opposite of BUY to close
   req.price        = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   req.deviation    = 50;
   req.magic        = InpMagicNumber;  // BUG FIX: magic was 0 → close DEAL_ADD failed magic filter
   req.type_filling = GetAllowedFillingMode();
   req.comment      = "UhvSweepDiag_close";
   if(!OrderSendAsync(req, res)) {
      Log("[STEP 5 FAIL] OrderSendAsync close — retcode=" + IntegerToString(res.retcode));
      return false;
   }
   Log("[STEP 5] Close sent. request_id=" + IntegerToString((long)res.request_id));
   return true;
}

//+------------------------------------------------------------------+
int OnInit() {
   g_contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(g_contract_size <= 0) g_contract_size = 100.0;
   int fill = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   Log("Init — Symbol=" + _Symbol +
       " ContractSize=" + DoubleToString(g_contract_size, 2) +
       " FillingBits=" + IntegerToString(fill) +
       " (FOK=" + ((fill & SYMBOL_FILLING_FOK)?"Y":"N") +
       " IOC=" + ((fill & SYMBOL_FILLING_IOC)?"Y":"N") + ")" +
       " RunTest=" + (InpRunTest?"YES":"DRY"));
   // Amnesia test: check if we already have an open test position from a previous run
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong tkt = PositionGetTicket(i);
      if(tkt == 0) continue;
      if(!PositionSelectByTicket(tkt)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      g_open_ticket = tkt;
      g_open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      g_phase = PHASE_ENTRY_FILLED;
      g_phase_start_ts = TimeCurrent();
      Log("[AMNESIA RECOVERED] Existing test position ticket=" + IntegerToString((long)tkt) +
          " entry=" + DoubleToString(g_open_price, _Digits) +
          " cur_pnl=" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2));
      if(InpCleanupOpen) {
         Log("[CLEANUP] Closing stuck test position immediately");
         FireClose();
      }
      break;
   }
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   Log("Deinit reason=" + IntegerToString(reason) +
       " phase=" + IntegerToString(g_phase));
}

// (OnTick defined further below — moved to handle DEAL_ADD bind fallback)

// Translate transaction type to readable string for verbose logging
string TransTypeStr(ENUM_TRADE_TRANSACTION_TYPE t) {
   switch(t) {
      case TRADE_TRANSACTION_ORDER_ADD: return "ORDER_ADD";
      case TRADE_TRANSACTION_ORDER_UPDATE: return "ORDER_UPDATE";
      case TRADE_TRANSACTION_ORDER_DELETE: return "ORDER_DELETE";
      case TRADE_TRANSACTION_DEAL_ADD: return "DEAL_ADD";
      case TRADE_TRANSACTION_DEAL_UPDATE: return "DEAL_UPDATE";
      case TRADE_TRANSACTION_DEAL_DELETE: return "DEAL_DELETE";
      case TRADE_TRANSACTION_HISTORY_ADD: return "HISTORY_ADD";
      case TRADE_TRANSACTION_HISTORY_UPDATE: return "HISTORY_UPDATE";
      case TRADE_TRANSACTION_HISTORY_DELETE: return "HISTORY_DELETE";
      case TRADE_TRANSACTION_POSITION: return "POSITION";
      case TRADE_TRANSACTION_REQUEST: return "REQUEST";
   }
   return "UNKNOWN(" + IntegerToString((int)t) + ")";
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result) {
   // VERBOSE: log EVERY incoming transaction with its key fields
   Log("[TRANS] type=" + TransTypeStr(trans.type) +
       " deal=" + IntegerToString((long)trans.deal) +
       " order=" + IntegerToString((long)trans.order) +
       " position=" + IntegerToString((long)trans.position) +
       " symbol=" + trans.symbol +
       " price=" + DoubleToString(trans.price, _Digits) +
       " req_id=" + IntegerToString((long)result.request_id));
   // STEP 2: REQUEST ack
   if(trans.type == TRADE_TRANSACTION_REQUEST) {
      if(result.request_id != 0 && result.request_id == g_request_id) {
         Log("[STEP 2] REQUEST ack. request_id=" + IntegerToString((long)result.request_id) +
             " retcode=" + IntegerToString(result.retcode));
         g_request_id = 0;
      }
      return;
   }
   // STEP 3: DEAL_ADD
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      if(!HistoryDealSelect(trans.deal)) {
         Log("[STEP 3 WARN] HistoryDealSelect failed for deal=" + IntegerToString((long)trans.deal));
         return;
      }
      long magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
      // Accept if magic matches OR position matches our known open ticket
      // (handles brokers where close deals don't preserve magic).
      bool is_ours = (magic == InpMagicNumber) ||
                     (g_open_ticket != 0 && trans.position == g_open_ticket);
      if(!is_ours) return;
      long deal_entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
      double deal_price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
      if(deal_entry == DEAL_ENTRY_IN) {
         g_open_ticket = trans.position;
         g_open_price = deal_price;
         Log("[STEP 3] DEAL_ADD (entry). ticket=" + IntegerToString((long)g_open_ticket) +
             " price=" + DoubleToString(g_open_price, _Digits));
         // FIX: Blueberry doesn't fire POSITION event on open. Bind here directly.
         // Verify position is registered (most brokers register before DEAL_ADD fires).
         if(PositionSelectByTicket(g_open_ticket)) {
            g_phase = PHASE_ENTRY_FILLED;
            g_phase_start_ts = TimeCurrent();
            Log("[STEP 4] Position verified at DEAL_ADD. ticket=" + IntegerToString((long)g_open_ticket) +
                " — will move SL to BE in " + IntegerToString(InpHoldSec) + "s");
         } else {
            Log("[STEP 4 PENDING] Position not yet selectable — waiting for POSITION event or next tick");
         }
      } else if(deal_entry == DEAL_ENTRY_OUT) {
         Log("[STEP 6] DEAL_ADD (close). ticket=" + IntegerToString((long)trans.position) +
             " exit_price=" + DoubleToString(deal_price, _Digits));
         g_phase = PHASE_CLOSED;
         g_open_ticket = 0;
         Log("=== UhvSweep Diagnostic Test COMPLETE ===");
         g_phase = PHASE_DONE;
      }
      return;
   }
   // STEP 4 fallback: POSITION event (for brokers that fire it)
   if(trans.type == TRADE_TRANSACTION_POSITION) {
      if(trans.position == g_open_ticket && g_phase == PHASE_ENTRY_SENT) {
         g_phase = PHASE_ENTRY_FILLED;
         g_phase_start_ts = TimeCurrent();
         Log("[STEP 4] POSITION confirmed (via POSITION event). ticket=" + IntegerToString((long)g_open_ticket) +
             " — will move SL to BE in " + IntegerToString(InpHoldSec) + "s");
      }
   }
}

void OnTick() {
   if(!InpRunTest) return;
   // Fallback bind: if DEAL_ADD set ticket but PositionSelectByTicket failed there,
   // retry on tick until position becomes selectable.
   if(g_phase == PHASE_ENTRY_SENT && g_open_ticket != 0 && PositionSelectByTicket(g_open_ticket)) {
      g_phase = PHASE_ENTRY_FILLED;
      g_phase_start_ts = TimeCurrent();
      Log("[STEP 4] Position verified via OnTick fallback. ticket=" + IntegerToString((long)g_open_ticket));
   }
   if(!g_test_started && g_phase == PHASE_IDLE) {
      g_test_started = true;
      Log("=== UhvSweep Diagnostic Test STARTING ===");
      g_phase_start_ts = TimeCurrent();
      if(FireBuyEntry()) {
         g_phase = PHASE_ENTRY_SENT;
      } else {
         g_phase = PHASE_DONE;
         Log("=== Test ABORTED at STEP 1 ===");
      }
      return;
   }
   long elapsed = (long)(TimeCurrent() - g_phase_start_ts);
   if(g_phase == PHASE_ENTRY_FILLED && elapsed >= InpHoldSec) {
      // Only attempt BE if currently in profit (mirrors production EA's tier-gate)
      double cur_pnl = 0;
      if(PositionSelectByTicket(g_open_ticket))
         cur_pnl = PositionGetDouble(POSITION_PROFIT);
      if(cur_pnl > 0) {
         if(MoveToBE()) {
            g_phase = PHASE_BE_MOVED;
            Log("[STEP 3 OK] Profit positive ($" + DoubleToString(cur_pnl, 2) + ") — BE moved");
         }
      } else {
         Log("[STEP 3 SKIP] Position underwater ($" + DoubleToString(cur_pnl, 2) + ") — skipping BE, going to close");
         g_phase = PHASE_BE_MOVED;  // skip directly to close phase
      }
      g_phase_start_ts = TimeCurrent();
   } else if(g_phase == PHASE_BE_MOVED && elapsed >= InpHoldSec) {
      if(FireClose()) {/* wait for fill */}
   }
}
//+------------------------------------------------------------------+
