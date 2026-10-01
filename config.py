from dataclasses import dataclass
import os

@dataclass
class StrategyConfig:
    strategy_version: str = os.getenv("STRATEGY_VERSION", "v1").lower()
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
    all_signals: bool = os.getenv("ALL_SIGNALS", "false").lower() == "true"
    backtest_days: str = os.getenv("BACKTEST_DAYS", "expiry").lower()
    train_fraction: float = float(os.getenv("TRAIN_FRACTION", "0.7"))
    map_time: str = os.getenv("MAP_TIME", "13:30")
    range_lookback_expiries: int = int(os.getenv("RANGE_LOOKBACK_EXPIRIES", "20"))
    straddle_bars: int = int(os.getenv("STRADDLE_BARS", "2"))
    straddle_min_change_pct: float = float(os.getenv("STRADDLE_MIN_CHANGE_PCT", "0"))
    wall_oi_drop_pct: float = float(os.getenv("WALL_OI_DROP_PCT", "3"))
    velocity_bars: int = int(os.getenv("VELOCITY_BARS", "3"))
    velocity_straddle_mult: float = float(os.getenv("VELOCITY_STRADDLE_MULT", "0.6"))
    fut_vol_mult: float = float(os.getenv("FUT_VOL_MULT", "2.0"))
    max_range_percentile: float = float(os.getenv("MAX_RANGE_PERCENTILE", "60"))
    min_score: float = float(os.getenv("MIN_SCORE", "4"))
    v2_entry_start: str = os.getenv("V2_ENTRY_START", "14:00")
    v2_entry_end: str = os.getenv("V2_ENTRY_END", "15:05")
    max_trades_per_expiry: int = int(os.getenv("MAX_TRADES_PER_EXPIRY", "1"))
    target_delta: float = float(os.getenv("TARGET_DELTA", "0.42"))
    delta_min: float = float(os.getenv("DELTA_MIN", "0.35"))
    delta_max: float = float(os.getenv("DELTA_MAX", "0.50"))
    risk_free_rate: float = float(os.getenv("RISK_FREE_RATE", "0.065"))
    max_spread_pct: float = float(os.getenv("MAX_SPREAD_PCT", "5"))
    max_loss_per_expiry_rs: float = float(os.getenv("MAX_LOSS_PER_EXPIRY_RS", "2000"))
    v2_initial_stop: float = float(os.getenv("V2_INITIAL_STOP", "0.35"))
    time_stop_target_pct: float = float(os.getenv("TIME_STOP_TARGET_PCT", "40"))
    time_stop_minutes: int = int(os.getenv("TIME_STOP_MINUTES", "9"))
    scale_out_pct: float = float(os.getenv("SCALE_OUT_PCT", "100"))
    scale_out_fraction: float = float(os.getenv("SCALE_OUT_FRACTION", "0.5"))
    v2_trail_pct: float = float(os.getenv("V2_TRAIL_PCT", "30"))
    straddle_exit_bars: int = int(os.getenv("STRADDLE_EXIT_BARS", "2"))
    v2_hard_exit: str = os.getenv("V2_HARD_EXIT", "15:20")
    scale_in: bool = os.getenv("SCALE_IN", "false").lower() == "true"
    slippage_ticks: int = int(os.getenv("SLIPPAGE_TICKS", "1"))

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
