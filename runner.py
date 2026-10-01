"""
Continuous FYERS runner.

Default is PAPER. It records planned trades and active paper/live trades.
For production option monitoring it starts a FYERS data WebSocket per open symbol.

Important:
- Keep AUTO_EXECUTE=false for initial validation.
- Live requires ALLOW_LIVE_TRADING=true.
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()

from config import (
    StrategyConfig, INDEXES, MODE, AUTO_EXECUTE, DB_PATH,
    FYERS_APP_ID, FYERS_ACCESS_TOKEN
)
from db import DB
from fyers_broker import FyersBroker
from fyers_stream import MarketStream
from engine import scan_index, execute_plan, monitor_trade, in_entry_window

IST = ZoneInfo("Asia/Kolkata")

def main():
    cfg = StrategyConfig()
    db = DB(DB_PATH)
    broker = FyersBroker(FYERS_APP_ID, FYERS_ACCESS_TOKEN)

    streams = {}
    last_scan_minute = None

    while True:
        now = datetime.now(IST)
        minute_key = now.strftime("%Y-%m-%d %H:%M")

        if in_entry_window(cfg, now) and minute_key != last_scan_minute:
            last_scan_minute = minute_key
            for index_name in INDEXES:
                try:
                    out = scan_index(db, broker, index_name, cfg)
                    if out and not out.get("no_trade") and AUTO_EXECUTE:
                        execute_plan(db, broker, out, MODE, cfg)
                except Exception as e:
                    db.event("ERROR", f"Scanner {index_name}: {e}")

        for trade in db.open_trades():
            try:
                symbol = trade["symbol"]
                if symbol not in streams:
                    streams[symbol] = MarketStream(
                        FYERS_APP_ID, FYERS_ACCESS_TOKEN, [symbol]
                    ).start()
                    time.sleep(0.5)

                ltp = streams[symbol].ltp(symbol, max_age=10)
                if ltp is None:
                    # one-shot REST fallback only if WS has not populated yet
                    ltp = broker.ltp(symbol)

                monitor_trade(db, broker, trade, ltp=ltp, cfg=cfg)
            except Exception as e:
                db.event("ERROR", f"Monitor trade #{trade['id']}: {e}", trade["id"])

        time.sleep(1)

if __name__ == "__main__":
    main()
