from math import erf, exp, log, sqrt


def _norm_cdf(x):
    return 0.5 * (1 + erf(x / sqrt(2)))


def option_price(spot, strike, years, rate, volatility, option_type):
    if min(spot, strike, years, volatility) <= 0:
        return max(0.0, spot - strike) if option_type == "CE" else max(0.0, strike - spot)
    d1 = (log(spot / strike) + (rate + volatility * volatility / 2) * years) / (volatility * sqrt(years))
    d2 = d1 - volatility * sqrt(years)
    if option_type == "CE":
        return spot * _norm_cdf(d1) - strike * exp(-rate * years) * _norm_cdf(d2)
    return strike * exp(-rate * years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def delta(spot, strike, years, rate, volatility, option_type):
    if min(spot, strike, years, volatility) <= 0:
        return 0.0
    d1 = (log(spot / strike) + (rate + volatility * volatility / 2) * years) / (volatility * sqrt(years))
    return _norm_cdf(d1) if option_type == "CE" else _norm_cdf(d1) - 1


def implied_volatility(price, spot, strike, years, rate, option_type, tolerance=1e-7):
    intrinsic = max(0.0, spot - strike) if option_type == "CE" else max(0.0, strike - spot)
    if price < intrinsic or min(spot, strike, years) <= 0:
        return None
    low, high = 1e-6, 5.0
    for _ in range(100):
        mid = (low + high) / 2
        estimate = option_price(spot, strike, years, rate, mid, option_type)
        if abs(estimate - price) <= tolerance:
            return mid
        if estimate < price:
            low = mid
        else:
            high = mid
    return (low + high) / 2
