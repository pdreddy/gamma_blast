import pandas as pd

def atr(df, period=10):
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def supertrend(df, period=10, multiplier=3.0):
    df = df.reset_index(drop=True).copy()
    hl2 = (df["high"] + df["low"]) / 2
    a = atr(df, period)
    upper = hl2 + multiplier * a
    lower = hl2 - multiplier * a
    final_upper = upper.copy()
    final_lower = lower.copy()
    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = lower.iloc[i]
            direction.iloc[i] = 1
            continue

        final_upper.iloc[i] = upper.iloc[i] if (
            upper.iloc[i] < final_upper.iloc[i-1] or
            df["close"].iloc[i-1] > final_upper.iloc[i-1]
        ) else final_upper.iloc[i-1]

        final_lower.iloc[i] = lower.iloc[i] if (
            lower.iloc[i] > final_lower.iloc[i-1] or
            df["close"].iloc[i-1] < final_lower.iloc[i-1]
        ) else final_lower.iloc[i-1]

        if st.iloc[i-1] == final_upper.iloc[i-1]:
            if df["close"].iloc[i] <= final_upper.iloc[i]:
                st.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = -1
            else:
                st.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1
        else:
            if df["close"].iloc[i] >= final_lower.iloc[i]:
                st.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1
            else:
                st.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = -1

    return st, direction

def heikin_ashi(df):
    ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    ha_open = pd.Series(index=df.index, dtype=float)
    ha_open.iloc[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2
    for i in range(1, len(df)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
    return ha_open, ha_close


def rsi(series, period=14):
    """Wilder RSI with neutral values during the warm-up period."""
    delta = series.diff()
    gains = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    relative_strength = gains / losses.replace(0, float("nan"))
    values = 100 - (100 / (1 + relative_strength))
    values = values.mask((losses == 0) & (gains > 0), 100)
    values = values.mask((gains == 0) & (losses > 0), 0)
    return values.fillna(50)


def prepare_signal_frame(
    candles,
    period=10,
    multiplier=3.0,
    lookback=5,
    min_ha_body_atr=0.10,
    max_breakout_atr=0.75,
    min_close_location=0.70,
    rsi_period=14,
    bullish_rsi_min=55,
    bearish_rsi_max=45,
):
    """Build one canonical signal frame for live scans and historical tests."""
    df = candles.sort_values("timestamp").reset_index(drop=True).copy()
    st, direction = supertrend(df, period, multiplier)
    hao, hac = heikin_ashi(df)

    df["atr"] = atr(df, period)
    df["st"] = st
    df["direction"] = direction
    df["ha_open"] = hao
    df["ha_close"] = hac
    df["rsi"] = rsi(df["close"], rsi_period)
    df["prev_high"] = df["high"].shift(1).rolling(lookback).max()
    df["prev_low"] = df["low"].shift(1).rolling(lookback).min()

    safe_atr = df["atr"].replace(0, float("nan"))
    candle_range = (df["high"] - df["low"]).replace(0, float("nan"))
    df["ha_body_atr"] = (df["ha_close"] - df["ha_open"]).abs() / safe_atr
    df["close_location"] = ((df["close"] - df["low"]) / candle_range).fillna(0.5)
    df["bull_breakout_atr"] = (df["close"] - df["prev_high"]) / safe_atr
    df["bear_breakout_atr"] = (df["prev_low"] - df["close"]) / safe_atr

    conviction = df["ha_body_atr"] >= min_ha_body_atr
    df["bull"] = (
        (df["direction"] == 1)
        & (df["ha_close"] > df["ha_open"])
        & df["bull_breakout_atr"].between(0, max_breakout_atr, inclusive="right")
        & conviction
        & (df["close_location"] >= min_close_location)
        & (df["rsi"] >= bullish_rsi_min)
    )
    df["bear"] = (
        (df["direction"] == -1)
        & (df["ha_close"] < df["ha_open"])
        & df["bear_breakout_atr"].between(0, max_breakout_atr, inclusive="right")
        & conviction
        & (df["close_location"] <= 1 - min_close_location)
        & (df["rsi"] <= bearish_rsi_max)
    )
    return df


def signal_from_candles(
    candles, period=10, multiplier=3.0, lookback=5, **quality_filters
):
    required = max(period + 2, lookback + 2, quality_filters.get("rsi_period", 14) + 2)
    if candles is None or len(candles) < required:
        return None
    df = prepare_signal_frame(candles, period, multiplier, lookback, **quality_filters)

    b = df.iloc[-1]
    bull = bool(b["bull"])
    bear = bool(b["bear"])

    if bull:
        return {
            "option_type": "CE",
            "spot": float(b["close"]),
            "reason": f"Quality-filtered bullish {lookback}-bar breakout (RSI {b['rsi']:.1f})",
        }
    if bear:
        return {
            "option_type": "PE",
            "spot": float(b["close"]),
            "reason": f"Quality-filtered bearish {lookback}-bar breakdown (RSI {b['rsi']:.1f})",
        }
    return None

def choose_option(option_chain_rows, option_type, premium_min=5.0, premium_max=30.0):
    spot_rows = [r for r in option_chain_rows if r.get("option_type", "") == ""]
    spot = float(spot_rows[0].get("ltp", 0)) if spot_rows else 0.0

    candidates = []
    for r in option_chain_rows:
        if r.get("option_type") != option_type:
            continue
        ltp = r.get("ltp")
        if ltp is None:
            continue
        ltp = float(ltp)
        if not (premium_min <= ltp <= premium_max):
            continue
        g = r.get("greeks") or {}
        candidates.append({
            "symbol": r.get("symbol"),
            "strike": float(r.get("strike_price") or 0),
            "option_type": option_type,
            "ltp": ltp,
            "bid": float(r.get("bid") or 0),
            "ask": float(r.get("ask") or 0),
            "oi": int(r.get("oi") or 0),
            "oich": int(r.get("oich") or 0),
            "volume": int(r.get("volume") or 0),
            "delta": float(g.get("delta") or 0),
            "gamma": float(g.get("gamma") or 0),
            "theta": float(g.get("theta") or 0),
            "iv": float(g.get("iv") or 0),
            "spot": spot,
        })

    if not candidates:
        return None

    # V1: nearest ATM in our cheap premium band, tie-break by liquidity.
    candidates.sort(
        key=lambda x: (
            abs(x["strike"] - spot),
            -(x["volume"]),
            -(x["oi"]),
        )
    )
    return candidates[0]

def update_trailing(entry_price, old_peak, old_stop, ltp,
                    initial_stop_pct=0.40,
                    trail_trigger_pct=0.50,
                    trail_gap_pct=0.25,
                    hero_threshold_pct=2.00):
    entry = float(entry_price)
    ltp = float(ltp)
    peak = max(float(old_peak or entry), ltp)

    base_stop = entry * (1 - initial_stop_pct)
    stop = max(float(old_stop or base_stop), base_stop)

    trail_active = peak >= entry * (1 + trail_trigger_pct)
    if trail_active:
        stop = max(stop, peak * (1 - trail_gap_pct))

    hero_reached = peak >= entry * (1 + hero_threshold_pct)

    return {
        "peak": peak,
        "stop": stop,
        "trail_active": trail_active,
        "hero_reached": hero_reached,
        "exit_now": ltp <= stop,
        "pnl_pct": (ltp / entry - 1) * 100,
    }


def signal_diagnostics(
    candles, period=10, multiplier=3.0, lookback=5, **quality_filters
):
    """
    Returns current 3-minute signal diagnostics even when no trade signal exists.
    """
    required = max(period + 2, lookback + 2, quality_filters.get("rsi_period", 14) + 2)
    if candles is None or len(candles) < required:
        return {
            "ready": False,
            "reason": "Not enough 3-minute candles yet",
        }

    df = prepare_signal_frame(candles, period, multiplier, lookback, **quality_filters)

    b = df.iloc[-1]
    bull_st = bool(b["direction"] == 1)
    bear_st = bool(b["direction"] == -1)
    ha_bull = bool(b["ha_close"] > b["ha_open"])
    ha_bear = bool(b["ha_close"] < b["ha_open"])
    bull_break = bool(b["close"] > b["prev_high"]) if pd.notna(b["prev_high"]) else False
    bear_break = bool(b["close"] < b["prev_low"]) if pd.notna(b["prev_low"]) else False

    signal = "CE" if bool(b["bull"]) else "PE" if bool(b["bear"]) else None

    return {
        "ready": True,
        "timestamp": str(b["timestamp"]),
        "close": float(b["close"]),
        "supertrend_value": float(b["st"]),
        "supertrend_direction": "BULLISH" if bull_st else "BEARISH",
        "ha_open": float(b["ha_open"]),
        "ha_close": float(b["ha_close"]),
        "ha_direction": "BULLISH" if ha_bull else "BEARISH",
        "previous_5bar_high": float(b["prev_high"]) if pd.notna(b["prev_high"]) else None,
        "previous_5bar_low": float(b["prev_low"]) if pd.notna(b["prev_low"]) else None,
        "bull_breakout": bull_break,
        "bear_breakdown": bear_break,
        "rsi": float(b["rsi"]),
        "ha_body_atr": float(b["ha_body_atr"]),
        "close_location": float(b["close_location"]),
        "bull_breakout_atr": float(b["bull_breakout_atr"]) if pd.notna(b["bull_breakout_atr"]) else None,
        "bear_breakout_atr": float(b["bear_breakout_atr"]) if pd.notna(b["bear_breakout_atr"]) else None,
        "signal": signal,
        "bull_conditions": {
            "supertrend_bullish": bull_st,
            "ha_bullish": ha_bull,
            "five_bar_breakout": bull_break,
            "quality_filters_passed": bool(b["bull"]),
        },
        "bear_conditions": {
            "supertrend_bearish": bear_st,
            "ha_bearish": ha_bear,
            "five_bar_breakdown": bear_break,
            "quality_filters_passed": bool(b["bear"]),
        },
    }
