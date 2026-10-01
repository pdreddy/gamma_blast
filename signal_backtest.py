"""
Backtest the SIGNAL layer on FYERS underlying history.

This does NOT claim option-premium P&L. It answers:
- how often the 3-minute SuperTrend + Heikin-Ashi + 5-bar breakout signal occurred
- bullish vs bearish signal counts
- forward underlying move after 5/10/20/30 minutes
- favorable/adverse excursion after the signal

Why signal-only?
The normal FYERS live option-chain interface does not expose old expired option
chains. Exact historical option P&L should therefore be validated using FYERS
Automate's F&O backtest or another expired-options dataset.

Run:
    python signal_backtest.py --index SENSEX --from 2025-10-01 --to 2026-09-30
"""
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
from dotenv import load_dotenv
load_dotenv()

from config import (
    StrategyConfig, INDEXES,
    FYERS_APP_ID, FYERS_ACCESS_TOKEN
)
from fyers_broker import FyersBroker
from strategy import supertrend, heikin_ashi

IST = ZoneInfo("Asia/Kolkata")

def prepare(df, cfg):
    x = df.copy().sort_values("timestamp").reset_index(drop=True)
    st, direction = supertrend(
        x, cfg.supertrend_period, cfg.supertrend_multiplier
    )
    hao, hac = heikin_ashi(x)
    x["st"] = st
    x["direction"] = direction
    x["ha_open"] = hao
    x["ha_close"] = hac
    x["prev_high"] = x["high"].shift(1).rolling(cfg.breakout_lookback).max()
    x["prev_low"] = x["low"].shift(1).rolling(cfg.breakout_lookback).min()
    x["bull"] = (
        (x["direction"] == 1) &
        (x["ha_close"] > x["ha_open"]) &
        (x["close"] > x["prev_high"])
    )
    x["bear"] = (
        (x["direction"] == -1) &
        (x["ha_close"] < x["ha_open"]) &
        (x["close"] < x["prev_low"])
    )
    return x

def forward_metrics(day, idx, side, entry_price):
    out = {}
    sign = 1 if side == "CE" else -1

    for mins in (5, 10, 20, 30):
        bars = max(1, mins // 3)
        j = min(idx + bars, len(day) - 1)
        future = float(day.iloc[j]["close"])
        out[f"fwd_{mins}m_pct"] = sign * (future / entry_price - 1) * 100

    future_slice = day.iloc[idx:min(idx + 11, len(day))]
    if side == "CE":
        mfe = (future_slice["high"].max() / entry_price - 1) * 100
        mae = (future_slice["low"].min() / entry_price - 1) * 100
    else:
        mfe = (entry_price / future_slice["low"].min() - 1) * 100
        mae = (entry_price / future_slice["high"].max() - 1) * 100

    out["mfe_30m_pct"] = float(mfe)
    out["mae_30m_pct"] = float(mae)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", choices=["NIFTY", "SENSEX"], default="SENSEX")
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--expiry-weekday-only", action="store_true",
                    help="Filter by weekday only. Does not account for holiday-shifted expiries.")
    args = ap.parse_args()

    cfg = StrategyConfig()
    broker = FyersBroker(FYERS_APP_ID, FYERS_ACCESS_TOKEN)
    symbol = INDEXES[args.index]["underlying"]

    print(f"Downloading FYERS 3-minute history for {args.index}...")
    df = broker.history(
        symbol,
        resolution="3",
        start_date=args.date_from,
        end_date=args.date_to,
    )
    if df.empty:
        raise SystemExit("No history returned.")

    df["date"] = df["timestamp"].dt.date
    results = []

    # Current schedule helper only. For exact historical expiry calendars,
    # use FYERS Automate's F&O backtest.
    weekday = 1 if args.index == "NIFTY" else 3  # Tue / Thu current context

    for d, day in df.groupby("date"):
        day = day.sort_values("timestamp").reset_index(drop=True)

        if args.expiry_weekday_only and d.weekday() != weekday:
            continue

        x = prepare(day, cfg)

        hhmm = x["timestamp"].dt.strftime("%H:%M")
        eligible = x[
            (hhmm >= cfg.entry_start) &
            (hhmm <= cfg.entry_end)
        ]

        chosen = None
        for idx, row in eligible.iterrows():
            if row["bull"]:
                chosen = (idx, "CE", row)
                break
            if row["bear"]:
                chosen = (idx, "PE", row)
                break

        if not chosen:
            continue

        idx, side, row = chosen
        entry = float(row["close"])
        m = forward_metrics(x, idx, side, entry)

        results.append({
            "date": d.isoformat(),
            "timestamp": str(row["timestamp"]),
            "index": args.index,
            "signal": side,
            "underlying_entry": entry,
            **m,
        })

    out = pd.DataFrame(results)
    outfile = f"signal_backtest_{args.index}_{args.date_from}_{args.date_to}.csv"
    out.to_csv(outfile, index=False)

    print()
    print("Signal backtest complete.")
    print("Trades/signals:", len(out))
    if len(out):
        print("CE signals:", int((out["signal"] == "CE").sum()))
        print("PE signals:", int((out["signal"] == "PE").sum()))
        for c in ["fwd_5m_pct", "fwd_10m_pct", "fwd_20m_pct", "fwd_30m_pct",
                  "mfe_30m_pct", "mae_30m_pct"]:
            print(f"{c}: mean={out[c].mean():.3f}% median={out[c].median():.3f}%")
    print("CSV:", outfile)
    print()
    print("Important: this tests the signal layer only, not historical option-premium P&L.")

if __name__ == "__main__":
    main()
