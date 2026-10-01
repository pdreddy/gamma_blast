from datetime import datetime

from .pricing import delta, implied_volatility


def choose_option_v2(rows, option_type, spot, expiry, lot_size, cfg, now=None):
    now = now or datetime.now()
    expiry_dt = expiry if isinstance(expiry, datetime) else datetime.combine(expiry, datetime.strptime("15:30", "%H:%M").time())
    years = max((expiry_dt - now).total_seconds(), 60) / (365 * 24 * 3600)
    candidates = []
    for row in rows:
        if row.get("option_type") != option_type:
            continue
        bid, ask = float(row.get("bid") or 0), float(row.get("ask") or 0)
        mid = (bid + ask) / 2
        if mid <= 0 or ask < bid:
            continue
        spread_pct = (ask - bid) / mid * 100
        if spread_pct > cfg.max_spread_pct:
            continue
        strike = float(row.get("strike_price") or 0)
        greeks = row.get("greeks") or {}
        option_delta = greeks.get("delta")
        if option_delta is None:
            iv = implied_volatility(mid, spot, strike, years, cfg.risk_free_rate, option_type)
            option_delta = delta(spot, strike, years, cfg.risk_free_rate, iv, option_type) if iv else None
        absolute_delta = abs(float(option_delta)) if option_delta is not None else None
        if absolute_delta is None or not cfg.delta_min <= absolute_delta <= cfg.delta_max:
            continue
        lots = int(cfg.max_loss_per_expiry_rs // (mid * cfg.v2_initial_stop * lot_size))
        if lots < 1:
            continue
        candidates.append({**row, "mid": mid, "delta": absolute_delta, "spread_pct": spread_pct,
                           "lots": lots, "qty": lots * lot_size})
    return min(candidates, key=lambda x: (abs(x["delta"] - cfg.target_delta), x["spread_pct"],
                                          -int(x.get("volume") or 0), -int(x.get("oi") or 0)), default=None)
