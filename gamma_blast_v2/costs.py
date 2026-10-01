from dataclasses import dataclass
import os


@dataclass(frozen=True)
class CostRates:
    brokerage_per_order: float = float(os.getenv("COST_BROKERAGE_PER_ORDER", "20"))
    stt_sell_pct: float = float(os.getenv("COST_STT_SELL_PCT", "0.1"))
    exchange_pct: float = float(os.getenv("COST_EXCHANGE_PCT", "0.03503"))
    sebi_pct: float = float(os.getenv("COST_SEBI_PCT", "0.0001"))
    stamp_buy_pct: float = float(os.getenv("COST_STAMP_BUY_PCT", "0.003"))
    gst_pct: float = float(os.getenv("COST_GST_PCT", "18"))


def indian_option_costs(buy_value, sell_value, orders=2, rates=CostRates()):
    brokerage = rates.brokerage_per_order * orders
    exchange = (buy_value + sell_value) * rates.exchange_pct / 100
    sebi = (buy_value + sell_value) * rates.sebi_pct / 100
    return {
        "brokerage": brokerage,
        "stt": sell_value * rates.stt_sell_pct / 100,
        "exchange": exchange,
        "sebi": sebi,
        "stamp": buy_value * rates.stamp_buy_pct / 100,
        "gst": (brokerage + exchange) * rates.gst_pct / 100,
    }
