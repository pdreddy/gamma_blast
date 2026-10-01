from datetime import datetime, timedelta
import math

from config import StrategyConfig
from gamma_blast_v2.exits import new_position, update_exit
from gamma_blast_v2.features import detect_walls, score_features, straddle_non_decay, wall_break
from gamma_blast_v2.pricing import delta, implied_volatility, option_price
from engine import execute_plan


def test_black_scholes_and_iv_round_trip():
    price = option_price(100, 100, 1, 0.05, 0.2, "CE")
    assert math.isclose(price, 10.4506, rel_tol=1e-4)
    assert math.isclose(delta(100, 100, 1, 0.05, 0.2, "CE"), 0.6368, rel_tol=1e-4)
    assert math.isclose(implied_volatility(price, 100, 100, 1, 0.05, "CE"), 0.2, rel_tol=1e-5)


def test_walls_and_short_covering():
    chain = [
        {"option_type": "CE", "strike_price": 101, "oi": 100},
        {"option_type": "CE", "strike_price": 102, "oi": 300},
        {"option_type": "PE", "strike_price": 99, "oi": 400},
    ]
    walls = detect_walls(chain, 100)
    assert walls["call_wall"] == 102
    assert walls["put_wall"] == 99
    assert wall_break("CE", 103, 102, 90, 100, 12, 10, 3)
    assert not wall_break("CE", 103, 102, 110, 100, 12, 10, 3)


def test_straddle_and_missing_feature_scoring():
    assert straddle_non_decay([100, 100, 101], bars=2)
    assert straddle_non_decay([100], bars=2) is None
    scored = score_features({"straddle_non_decay": True, "wall_break": None, "velocity": True})
    assert scored["score"] == 3
    assert "wall_break" in scored["unavailable"]


def test_exit_rules_scale_out_straddle_and_hard_exit():
    cfg = StrategyConfig()
    entered = datetime(2026, 1, 1, 14, 0)
    state = new_position(10, entered, "CE", 100, 10, cfg.v2_initial_stop)
    stopped, actions = update_exit(state, entered + timedelta(minutes=1), 101, 6, 0, cfg)
    assert stopped.reason == "PREMIUM_STOP"
    state, actions = update_exit(state, entered + timedelta(minutes=3), 101, 20, 0, cfg)
    assert actions == [("SCALE_OUT", 5)] and state.stop >= 10
    state, actions = update_exit(state, entered + timedelta(minutes=6), 101, 19, 2, cfg)
    assert state.reason == "STRADDLE_DECAY"
    fresh = new_position(10, entered, "CE", 100, 10, cfg.v2_initial_stop)
    closed, _ = update_exit(fresh, entered.replace(hour=15, minute=20), 101, 15, 0, cfg)
    assert closed.reason == "HARD_EXIT"


def test_wall_invalidation_and_time_stop():
    cfg = StrategyConfig()
    entered = datetime(2026, 1, 1, 14, 0)
    state = new_position(10, entered, "CE", 100, 10, cfg.v2_initial_stop)
    invalid, _ = update_exit(state, entered + timedelta(minutes=1), 99, 10, 0, cfg)
    assert invalid.reason == "WALL_INVALIDATION"
    timed, _ = update_exit(state, entered + timedelta(minutes=9), 101, 11, 0, cfg)
    assert timed.reason == "TIME_STOP"


def test_no_lookahead_and_v2_live_safety():
    prefix = [100, 101, 102]
    before = straddle_non_decay(prefix, bars=2)
    after = straddle_non_decay((prefix + [1_000])[:3], bars=2)
    assert before == after

    cfg = StrategyConfig()
    cfg.strategy_version = "v2"

    class NeverBroker:
        def __getattr__(self, name):
            raise AssertionError(f"broker must not be called: {name}")

    try:
        execute_plan(None, NeverBroker(), {}, "LIVE", cfg)
    except RuntimeError as error:
        assert "PAPER-only" in str(error)
    else:
        raise AssertionError("v2 LIVE execution was not rejected")
