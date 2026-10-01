"""
Automatic PAPER trader for Gamma Blast.

This script NEVER places a broker order.
It:
- checks NIFTY/SENSEX once per minute
- only acts on actual expiry day
- waits for the 3-minute signal
- selects the live FYERS option
- opens a PAPER trade automatically
- monitors live LTP
- applies -40% initial stop
- starts trailing at +50%
- trails 25% below the highest premium
- logs +200% Hero milestone without forcing an exit
- exits paper position on stop or hard exit
- records everything in SQLite

Run:
    python auto_paper.py
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()

from config import StrategyConfig, INDEXES, DB_PATH, FYERS_APP_ID, FYERS_ACCESS_TOKEN
from db import DB
from fyers_broker import FyersBroker
from fyers_stream import MarketStream
from engine import scan_index, execute_plan, monitor_trade, in_entry_window, now_ist

IST = ZoneInfo("Asia/Kolkata")

def main():
    cfg = StrategyConfig()
    db = DB(DB_PATH)
    broker = FyersBroker(FYERS_APP_ID, FYERS_ACCESS_TOKEN)

    print("Gamma Blast automatic PAPER trader started.")
    print("No real FYERS orders will be placed.")
    print("India time:", datetime.now(IST).isoformat(timespec="seconds"))
    print("Entry window:", cfg.entry_start, "-", cfg.entry_end)
    print("Hard exit:", cfg.hard_exit)
    print()

    last_scan_minute = None
    streams = {}

    while True:
        now = datetime.now(IST)
        minute_key = now.strftime("%Y-%m-%d %H:%M")

        # Scan once each minute inside the entry window.
        if in_entry_window(cfg, now) and minute_key != last_scan_minute:
            last_scan_minute = minute_key
            for index_name in INDEXES:
                try:
                    out = scan_index(db, broker, index_name, cfg, force_scan=False)
                    if out and not out.get("no_trade"):
                        tid = execute_plan(db, broker, out, "PAPER", cfg)
                        print(
                            f"[{now.strftime('%H:%M:%S')}] PAPER ENTRY "
                            f"{index_name} {out['option_type']} "
                            f"{out['symbol']} ref={out['reference_price']} trade_id={tid}"
                        )
                    elif out and out.get("no_trade"):
                        print(
                            f"[{now.strftime('%H:%M:%S')}] {index_name}: "
                            f"{out.get('reason')}"
                        )
                except Exception as e:
                    db.event("ERROR", f"auto_paper scan {index_name}: {e}")
                    print(f"[{now.strftime('%H:%M:%S')}] {index_name} scan error: {e}")

        # Monitor all open paper trades.
        for trade in db.open_trades():
            if trade["mode"] != "PAPER":
                continue
            try:
                symbol = trade["symbol"]

                if symbol not in streams:
                    streams[symbol] = MarketStream(
                        FYERS_APP_ID,
                        FYERS_ACCESS_TOKEN,
                        [symbol]
                    ).start()
                    time.sleep(0.5)

                ltp = streams[symbol].ltp(symbol, max_age=10)
                if ltp is None:
                    ltp = broker.ltp(symbol)

                before_stop = float(trade["current_stop"])
                before_peak = float(trade["peak_price"])

                result = monitor_trade(
                    db, broker, trade, ltp=ltp, cfg=cfg
                )

                if result.get("closed"):
                    print(
                        f"[{datetime.now(IST).strftime('%H:%M:%S')}] PAPER EXIT "
                        f"trade_id={trade['id']} reason={result.get('reason')} "
                        f"ltp={result.get('exit_price', ltp):.2f}"
                    )
                    streams.pop(symbol, None)
                elif result["stop"] != before_stop or result["peak"] != before_peak:
                    print(
                        f"[{datetime.now(IST).strftime('%H:%M:%S')}] "
                        f"{symbol} ltp={ltp:.2f} peak={result['peak']:.2f} "
                        f"stop={result['stop']:.2f} "
                        f"trail={'ON' if result['trail_active'] else 'OFF'} "
                        f"hero200={'YES' if result['hero_reached'] else 'NO'}"
                    )

            except Exception as e:
                db.event("ERROR", f"auto_paper monitor trade #{trade['id']}: {e}", trade["id"])
                print(f"Monitor error trade #{trade['id']}: {e}")

        time.sleep(1)

if __name__ == "__main__":
    main()
