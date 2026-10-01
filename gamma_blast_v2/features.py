from dataclasses import dataclass


def detect_walls(chain, spot):
    calls = [r for r in chain if r.get("option_type") == "CE" and float(r.get("strike_price", 0)) > spot]
    puts = [r for r in chain if r.get("option_type") == "PE" and float(r.get("strike_price", 0)) < spot]
    call = max(calls, key=lambda r: float(r.get("oi") or 0), default=None)
    put = max(puts, key=lambda r: float(r.get("oi") or 0), default=None)
    all_options = [r for r in chain if r.get("option_type") in ("CE", "PE")]
    totals = {}
    for row in all_options:
        strike = float(row.get("strike_price") or 0)
        totals[strike] = totals.get(strike, 0) + float(row.get("oi") or 0)
    return {
        "call_wall": float(call["strike_price"]) if call else None,
        "put_wall": float(put["strike_price"]) if put else None,
        "pin_strike": max(totals, key=totals.get) if totals else None,
    }


def wall_break(side, spot, wall, current_oi, previous_oi, premium, previous_premium, min_drop_pct=3):
    values = (wall, current_oi, previous_oi, premium, previous_premium)
    if any(value is None for value in values) or previous_oi <= 0:
        return None
    crossed = spot > wall if side == "CE" else spot < wall
    drop = (previous_oi - current_oi) / previous_oi * 100
    return bool(crossed and drop >= min_drop_pct and premium > previous_premium)


def straddle_non_decay(values, bars=2, min_change_pct=0):
    if values is None or len(values) < bars + 1 or any(v is None for v in values[-bars - 1:]):
        return None
    changes = [(values[i] / values[i - 1] - 1) * 100 for i in range(len(values) - bars, len(values))]
    return all(change >= min_change_pct for change in changes)


FEATURE_POINTS = {"straddle_non_decay": 2, "wall_break": 1, "velocity": 1, "cross_index": 1, "futures_volume": 1}


def score_features(features, minimum=4):
    available = {k: v for k, v in features.items() if k in FEATURE_POINTS and v is not None}
    score = sum(FEATURE_POINTS[k] for k, value in available.items() if value)
    available_points = sum(FEATURE_POINTS[k] for k in available)
    required = minimum * available_points / sum(FEATURE_POINTS.values()) if available_points else minimum
    return {"score": score, "available_points": available_points, "required_score": required,
            "qualifies": available_points > 0 and score >= required,
            "available": sorted(available), "unavailable": sorted(set(FEATURE_POINTS) - set(available))}
