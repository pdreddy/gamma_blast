from datetime import datetime, timedelta
import pandas as pd
from math import sqrt

from config import StrategyConfig, INDEXES
from strategy import prepare_signal_frame

def _fetch_history_chunked(broker, symbol, date_from, date_to, chunk_days=30):
    """
    Fetch FYERS historical candles in smaller chunks and de-duplicate timestamps.
    """
    start = pd.to_datetime(date_from).date()
    end = pd.to_datetime(date_to).date()
    frames = []

    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        df = broker.history(
            symbol,
            resolution="3",
            start_date=cur.isoformat(),
            end_date=chunk_end.isoformat(),
        )
        if df is not None and not df.empty:
            frames.append(df)
        cur = chunk_end + timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return out

def _prepare_day(day, cfg):
    return prepare_signal_frame(
        day,
        cfg.supertrend_period,
        cfg.supertrend_multiplier,
        cfg.breakout_lookback,
        min_ha_body_atr=cfg.min_ha_body_atr,
        max_breakout_atr=cfg.max_breakout_atr,
        min_close_location=cfg.min_close_location,
        rsi_period=cfg.rsi_period,
        bullish_rsi_min=cfg.bullish_rsi_min,
        bearish_rsi_max=cfg.bearish_rsi_max,
    )

HORIZONS = (3, 5, 6, 9, 10, 12, 15, 20, 30)


def _forward_metrics(day, idx, side, entry_price):
    result = {}
    sign = 1 if side == "CE" else -1

    for mins in HORIZONS:
        bars = max(1, round(mins / 3))
        j = min(idx + bars, len(day) - 1)
        future = float(day.iloc[j]["close"])
        result[f"fwd_{mins}m_pct"] = sign * (future / entry_price - 1) * 100

    future_slice = day.iloc[idx:min(idx + 11, len(day))]
    if side == "CE":
        mfe = (float(future_slice["high"].max()) / entry_price - 1) * 100
        mae = (float(future_slice["low"].min()) / entry_price - 1) * 100
    else:
        mfe = (entry_price / float(future_slice["low"].min()) - 1) * 100
        mae = (entry_price / float(future_slice["high"].max()) - 1) * 100

    result["mfe_30m_pct"] = float(mfe)
    result["mae_30m_pct"] = float(mae)
    return result

def run_signal_backtest(
    broker,
    index_name,
    date_from,
    date_to,
    expiry_filter="approx_expiry_weekday",
    cfg=None,
    all_signals=False,
):
    """
    Backtest the exact ENTRY SIGNAL on 3-minute underlying candles.

    Important:
    This is NOT exact historical option-premium P&L.
    It measures whether the underlying moved in the direction implied by
    the CE/PE signal after entry.

    expiry_filter:
      - "all_days"
      - "approx_expiry_weekday"

    Current weekday mapping used for the approximation:
      NIFTY   -> Tuesday
      SENSEX  -> Thursday

    This does not reconstruct historical holiday-shifted expiry dates.
    """
    cfg = cfg or StrategyConfig()
    symbol = INDEXES[index_name]["underlying"]

    df = _fetch_history_chunked(
        broker,
        symbol,
        date_from,
        date_to,
        chunk_days=30,
    )

    if df.empty:
        return pd.DataFrame(), {
            "index": index_name,
            "date_from": str(date_from),
            "date_to": str(date_to),
            "signals": 0,
            "warning": "No historical candles returned by FYERS.",
        }

    df["date"] = df["timestamp"].dt.date
    results = []

    # Current expiry weekday approximation based on current contracts:
    # NIFTY Tuesday (1), SENSEX Thursday (3)
    expiry_weekday = 1 if index_name == "NIFTY" else 3

    for d, raw_day in df.groupby("date"):
        if expiry_filter == "approx_expiry_weekday" and d.weekday() != expiry_weekday:
            continue

        day = _prepare_day(raw_day, cfg)
        hhmm = day["timestamp"].dt.strftime("%H:%M")

        eligible = day[
            (hhmm >= cfg.entry_start) &
            (hhmm <= cfg.entry_end)
        ]

        # Select the first signal with a vectorized mask. This avoids constructing
        # a pandas Series for every candle in long, all-trading-day backtests.
        signal_rows = eligible.loc[eligible["bull"] | eligible["bear"]]
        if signal_rows.empty:
            continue

        # The default remains the exact v1 behavior. Research mode can retain
        # later signals after a 30-minute evaluation window has closed.
        chosen_rows = []
        last_idx = None
        for idx, row in signal_rows.iterrows():
            if not all_signals and chosen_rows:
                break
            if last_idx is None or idx > last_idx + 10:
                chosen_rows.append((idx, row))
                last_idx = idx

        for signal_number, (idx, row) in enumerate(chosen_rows, start=1):
            side = "CE" if bool(row["bull"]) else "PE"
            entry = float(row["close"])
            metrics = _forward_metrics(day, idx, side, entry)
            results.append({
            "date": d.isoformat(),
            "timestamp": row["timestamp"],
            "index": index_name,
            "signal": side,
            "underlying_entry": entry,
            "st_direction": "BULLISH" if int(row["direction"]) == 1 else "BEARISH",
            "ha_direction": "BULLISH" if float(row["ha_close"]) > float(row["ha_open"]) else "BEARISH",
            "prev_5bar_high": float(row["prev_high"]),
            "prev_5bar_low": float(row["prev_low"]),
            "rsi": float(row["rsi"]),
            "ha_body_atr": float(row["ha_body_atr"]),
            "close_location": float(row["close_location"]),
            "breakout_atr": float(
                row["bull_breakout_atr"] if side == "CE" else row["bear_breakout_atr"]
            ),
            "signal_order": "first" if signal_number == 1 else "later",
            **metrics,
            })

    out = pd.DataFrame(results)

    summary = {
        "index": index_name,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "expiry_filter": expiry_filter,
        "signals": int(len(out)),
        "ce_signals": int((out["signal"] == "CE").sum()) if not out.empty else 0,
        "pe_signals": int((out["signal"] == "PE").sum()) if not out.empty else 0,
    }

    if not out.empty:
        for mins in HORIZONS:
            col = f"fwd_{mins}m_pct"
            summary[f"win_rate_{mins}m"] = float((out[col] > 0).mean() * 100)
            summary[f"avg_{mins}m_pct"] = float(out[col].mean())
            summary[f"median_{mins}m_pct"] = float(out[col].median())

        summary["avg_mfe_30m_pct"] = float(out["mfe_30m_pct"].mean())
        summary["avg_mae_30m_pct"] = float(out["mae_30m_pct"].mean())
        summary["median_mfe_30m_pct"] = float(out["mfe_30m_pct"].median())
        summary["median_mae_30m_pct"] = float(out["mae_30m_pct"].median())

        # A directional-index-return curve only; this is NOT option-account P&L.
        out["directional_return_30m_pct"] = out["fwd_30m_pct"]
        out["directional_curve"] = (1 + out["directional_return_30m_pct"] / 100).cumprod()

        out["month"] = pd.to_datetime(out["date"]).dt.to_period("M").astype(str)

    return out, summary


def _wilson(wins, total, z=1.96):
    if not total:
        return (0.0, 0.0)
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return ((center - margin) * 100, (center + margin) * 100)


def diagnostic_slices(results, train_fraction=0.7):
    """Long-form, chronological train/test diagnostics for dashboard/reporting."""
    if results is None or results.empty:
        return pd.DataFrame()
    data = results.sort_values("timestamp").copy()
    cutoff = max(1, min(len(data) - 1, round(len(data) * train_fraction))) if len(data) > 1 else 1
    data["sample"] = "test"
    data.iloc[:cutoff, data.columns.get_loc("sample")] = "train"
    times = pd.to_datetime(data["timestamp"]).dt.strftime("%H:%M")
    data["time_bucket"] = pd.cut(
        pd.to_timedelta(times + ":00"),
        bins=pd.to_timedelta(["13:45:00", "14:15:00", "14:45:00", "15:11:00"]),
        labels=["13:45–14:15", "14:15–14:45", "14:45–15:10"], include_lowest=True,
    ).astype(str)
    dimensions = {"overall": pd.Series("all", index=data.index), "side": data["signal"],
                  "entry_time": data["time_bucket"], "index": data["index"]}
    if "signal_order" in data:
        dimensions["signal_order"] = data["signal_order"]
    rows = []
    for sample, sample_data in data.groupby("sample"):
        for dimension, values in dimensions.items():
            sample_values = values.loc[sample_data.index]
            for value in sample_values.unique():
                group = sample_data.loc[sample_values == value]
                for mins in HORIZONS:
                    returns = group[f"fwd_{mins}m_pct"]
                    wins = int((returns > 0).sum())
                    low, high = _wilson(wins, len(group))
                    rows.append({"sample": sample, "dimension": dimension, "slice": value,
                                 "horizon_min": mins, "count": len(group), "win_rate_pct": wins / len(group) * 100,
                                 "win_ci_low_pct": low, "win_ci_high_pct": high,
                                 "mean_return_pct": returns.mean(), "median_return_pct": returns.median(),
                                 "mfe_pct": group["mfe_30m_pct"].mean(), "mae_pct": group["mae_30m_pct"].mean(),
                                 "sample_quality": "sufficient" if len(group) >= 30 else "insufficient sample"})
    return pd.DataFrame(rows)

def monthly_summary(results):
    if results is None or results.empty:
        return pd.DataFrame()

    rows = []
    for month, g in results.groupby("month"):
        rows.append({
            "month": month,
            "signals": len(g),
            "win_rate_30m_pct": (g["fwd_30m_pct"] > 0).mean() * 100,
            "avg_30m_move_pct": g["fwd_30m_pct"].mean(),
            "median_30m_move_pct": g["fwd_30m_pct"].median(),
            "avg_mfe_30m_pct": g["mfe_30m_pct"].mean(),
            "avg_mae_30m_pct": g["mae_30m_pct"].mean(),
        })
    return pd.DataFrame(rows)
