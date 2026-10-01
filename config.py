from dataclasses import dataclass
import os

@dataclass
class StrategyConfig:
    starting_capital: float = float(os.getenv("STARTING_CAPITAL", "30000"))
    initial_stop_pct: float = float(os.getenv("INITIAL_STOP_PCT", "0.40"))
    trail_trigger_pct: float = float(os.getenv("TRAIL_TRIGGER_PCT", "0.50"))
    trail_gap_pct: float = float(os.getenv("TRAIL_GAP_PCT", "0.25"))
    hero_threshold_pct: float = float(os.getenv("HERO_THRESHOLD_PCT", "2.00"))
    premium_min: float = float(os.getenv("PREMIUM_MIN", "5"))
    premium_max: float = float(os.getenv("PREMIUM_MAX", "30"))
    entry_start: str = os.getenv("ENTRY_START", "13:45")
    entry_end: str = os.getenv("ENTRY_END", "15:10")
    hard_exit: str = os.getenv("HARD_EXIT", "15:25")
    supertrend_period: int = int(os.getenv("SUPERTREND_PERIOD", "10"))
    supertrend_multiplier: float = float(os.getenv("SUPERTREND_MULTIPLIER", "3"))
    breakout_lookback: int = int(os.getenv("BREAKOUT_LOOKBACK", "5"))
    min_ha_body_atr: float = float(os.getenv("MIN_HA_BODY_ATR", "0.10"))
    max_breakout_atr: float = float(os.getenv("MAX_BREAKOUT_ATR", "0.75"))
    min_close_location: float = float(os.getenv("MIN_CLOSE_LOCATION", "0.70"))
    rsi_period: int = int(os.getenv("RSI_PERIOD", "14"))
    bullish_rsi_min: float = float(os.getenv("BULLISH_RSI_MIN", "55"))
    bearish_rsi_max: float = float(os.getenv("BEARISH_RSI_MAX", "45"))
    max_capital_per_trade: float = float(os.getenv("MAX_CAPITAL_PER_TRADE", "12000"))
    max_trades_per_index_per_day: int = int(os.getenv("MAX_TRADES_PER_INDEX_PER_DAY", "1"))
    expiry_day_only: bool = os.getenv("EXPIRY_DAY_ONLY", "true").lower() == "true"

INDEXES = {
    "NIFTY": {
        "underlying": os.getenv("NIFTY_UNDERLYING", "NSE:NIFTY50-INDEX"),
        "master": "NSE_FO",
    },
    "SENSEX": {
        "underlying": os.getenv("SENSEX_UNDERLYING", "BSE:SENSEX-INDEX"),
        "master": "BSE_FO",
    },
}

MODE = os.getenv("TRADING_MODE", "PAPER").upper()
AUTO_EXECUTE = os.getenv("AUTO_EXECUTE", "false").lower() == "true"
ALLOW_LIVE_TRADING = os.getenv("ALLOW_LIVE_TRADING", "false").lower() == "true"
DB_PATH = os.getenv("GAMMA_DB_PATH", "gamma_blast_fyers.db")

FYERS_APP_ID = os.getenv("FYERS_APP_ID", "")
FYERS_SECRET_ID = os.getenv("FYERS_SECRET_ID", "")
FYERS_REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI", "")
FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN", "")
