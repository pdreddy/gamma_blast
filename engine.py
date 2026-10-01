from datetime import datetime
from zoneinfo import ZoneInfo
import json
import time

from config import StrategyConfig, INDEXES, ALLOW_LIVE_TRADING
from strategy import signal_from_candles, choose_option, update_trailing, signal_diagnostics

IST = ZoneInfo("Asia/Kolkata")

def now_ist():
    return datetime.now(IST)

def in_entry_window(cfg, now=None):
    now = now or now_ist()
    hhmm = now.strftime("%H:%M")
    return cfg.entry_start <= hhmm <= cfg.entry_end

def after_hard_exit(cfg, now=None):
    now = now or now_ist()
    return now.strftime("%H:%M") >= cfg.hard_exit

def parse_expiry_date(exp):
    return datetime.strptime(exp["date"], "%d-%m-%Y").date()

def scan_index(db, broker, index_name, cfg=None, force_scan=False):
    cfg = cfg or StrategyConfig()
    meta = INDEXES[index_name]
    today = now_ist().date()

    if db.existing_plan(today.isoformat(), index_name):
        return None

    if not force_scan and not in_entry_window(cfg):
        return None

    if cfg.strategy_version == "v2":
        return {
            "no_trade": True,
            "reason": (
                "v2 PAPER research requires synchronized historical/live option OI, "
                "ATM straddle, cross-index and futures-volume bars. These fields are "
                "unavailable from the current broker feed, so scoring was skipped."
            ),
            "strategy_version": "v2",
            "unavailable_features": [
                "straddle_non_decay", "wall_oi_drop", "cross_index", "futures_volume"
            ],
        }

    nearest = broker.nearest_expiry(meta["underlying"])
    if not nearest:
        raise RuntimeError(f"No FYERS expiry returned for {index_name}")

    expiry_date = parse_expiry_date(nearest)
    if cfg.expiry_day_only and expiry_date != today:
        return {
            "no_trade": True,
            "reason": f"{index_name} nearest expiry is {expiry_date}; today is {today}",
            "nearest_expiry": nearest,
        }

    candles = broker.history(meta["underlying"], resolution="3")
    sig = signal_from_candles(
        candles,
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
    if not sig:
        return {"no_trade": True, "reason": "No qualifying 3-minute signal"}

    chain_resp = broker.option_chain(
        meta["underlying"],
        strikecount=20,
        expiry_epoch=nearest["expiry"],
        greeks=True
    )
    rows = chain_resp.get("data", {}).get("optionsChain", [])
    candidate = choose_option(
        rows,
        sig["option_type"],
        cfg.premium_min,
        cfg.premium_max
    )
    if not candidate:
        return {"no_trade": True, "reason": "No option in premium/liquidity selection band"}

    rec = broker.validate_contract(meta["master"], candidate["symbol"], sig["option_type"])
    lot = int(rec.get("minLotSize") or 0)
    if lot <= 0:
        raise RuntimeError(f"Invalid lot size for {candidate['symbol']}")

    pid = db.add_plan(
        created_at=datetime.utcnow().isoformat(),
        trade_date=today.isoformat(),
        index_name=index_name,
        underlying=meta["underlying"],
        expiry_date=expiry_date.isoformat(),
        expiry_epoch=nearest["expiry"],
        option_type=sig["option_type"],
        strike=candidate["strike"],
        symbol=candidate["symbol"],
        lot_size=lot,
        reference_price=candidate["ltp"],
        bid=candidate["bid"],
        ask=candidate["ask"],
        oi=candidate["oi"],
        volume=candidate["volume"],
        iv=candidate["iv"],
        gamma=candidate["gamma"],
        trigger_reason=sig["reason"],
        status="PLANNED",
        notes="Generated from FYERS live data",
    )
    db.event(
        "PLAN_CREATED",
        f"{index_name} {sig['option_type']} plan #{pid}: {candidate['symbol']} @ {candidate['ltp']}",
        payload=json.dumps(candidate)
    )
    return db.plan(pid)

def execute_plan(db, broker, plan, mode, cfg=None):
    cfg = cfg or StrategyConfig()
    mode = mode.upper()

    if cfg.strategy_version == "v2" and mode == "LIVE":
        raise RuntimeError("Gamma Blast v2 is research/PAPER-only; LIVE execution is disabled.")

    if mode == "LIVE" and not ALLOW_LIVE_TRADING:
        raise RuntimeError(
            "LIVE trading is locked. Set ALLOW_LIVE_TRADING=true locally only after preflight."
        )

    reference = broker.ltp(plan["symbol"])
    if reference <= 0:
        raise RuntimeError("Invalid live option premium")

    lot = int(plan["lot_size"])
    lots = int(cfg.max_capital_per_trade // (reference * lot))
    if lots < 1:
        raise RuntimeError(
            f"One lot costs about ₹{reference * lot:.2f}, above MAX_CAPITAL_PER_TRADE"
        )

    qty = lots * lot
    order_id = None
    stop_order_id = None
    entry = reference
    initial_stop = entry * (1 - cfg.initial_stop_pct)

    if mode == "LIVE":
        response = broker.place_market_order(
            plan["symbol"], qty, "BUY", order_tag=f"gamma_{plan['id']}"
        )
        order_id = response.get("id")
        entry = broker.wait_for_fill(order_id, reference)

        # Recalculate from actual fill and place a broker-native protective SL-M.
        initial_stop = entry * (1 - cfg.initial_stop_pct)
        master = INDEXES[plan["index_name"]]["master"]
        initial_stop = broker.rounded_stop(master, plan["symbol"], initial_stop)
        stop_resp = broker.place_stop_market_order(
            plan["symbol"], qty, initial_stop, order_tag=f"gamma_sl_{plan['id']}"
        )
        stop_order_id = stop_resp.get("id")

    tid = db.add_trade(
        plan_id=plan["id"],
        broker_order_id=order_id,
        stop_order_id=stop_order_id,
        mode=mode,
        opened_at=datetime.utcnow().isoformat(),
        index_name=plan["index_name"],
        symbol=plan["symbol"],
        option_type=plan["option_type"],
        strike=plan["strike"],
        expiry_date=plan["expiry_date"],
        qty=qty,
        entry_price=entry,
        peak_price=entry,
        current_stop=initial_stop,
        trail_active=False,
        hero_reached=False,
        last_price=entry,
        status="OPEN",
        notes="Hero/Zero FYERS trade",
    )
    db.update_plan_status(plan["id"], "EXECUTED")
    db.event(
        "ENTRY",
        f"Trade #{tid}: {mode} BUY {qty} {plan['symbol']} @ {entry:.2f}; protective stop {initial_stop:.2f}",
        tid
    )
    if stop_order_id:
        db.event(
            "PROTECTIVE_STOP",
            f"Trade #{tid}: broker SL-M order {stop_order_id} placed at {initial_stop:.2f}",
            tid
        )
    return tid

def _reconcile_stop_fill(db, broker, trade):
    sid = trade.get("stop_order_id")
    if not sid:
        return None
    state = broker.order_state(sid)
    if not state:
        return None
    # FYERS status 2 = filled/traded
    if state["status"] == 2:
        px = state["avg_price"] or float(trade["current_stop"])
        db.close_trade(trade["id"], px, "BROKER_STOP_FILLED")
        db.event(
            "EXIT",
            f"Trade #{trade['id']}: broker protective stop filled @ {px:.2f}",
            trade["id"]
        )
        return {"closed": True, "reason": "BROKER_STOP_FILLED", "exit_price": px}
    return state

def monitor_trade(db, broker, trade, ltp=None, cfg=None):
    cfg = cfg or StrategyConfig()

    # First reconcile any broker-side stop fill.
    if trade["mode"] == "LIVE":
        rec = _reconcile_stop_fill(db, broker, trade)
        if rec and rec.get("closed"):
            return rec

    ltp = float(ltp if ltp is not None else broker.ltp(trade["symbol"]))

    state = update_trailing(
        trade["entry_price"],
        trade["peak_price"],
        trade["current_stop"],
        ltp,
        cfg.initial_stop_pct,
        cfg.trail_trigger_pct,
        cfg.trail_gap_pct,
        cfg.hero_threshold_pct,
    )

    old_stop = float(trade["current_stop"])
    new_stop = state["stop"]

    if trade["mode"] == "LIVE":
        master = INDEXES[trade["index_name"]]["master"]
        new_stop = broker.rounded_stop(master, trade["symbol"], new_stop)
        # Never move stop backwards after tick rounding.
        new_stop = max(old_stop, new_stop)
        state["stop"] = new_stop

        if trade.get("stop_order_id") and new_stop > old_stop:
            broker.modify_stop_market_order(
                trade["stop_order_id"], trade["qty"], new_stop
            )
            db.event(
                "STOP_MOVED",
                f"Trade #{trade['id']}: broker SL-M moved {old_stop:.2f} -> {new_stop:.2f}",
                trade["id"]
            )

    old_trail = bool(trade["trail_active"])
    old_hero = bool(trade["hero_reached"])

    db.update_trade_mark(
        trade["id"],
        state["peak"],
        state["stop"],
        state["trail_active"],
        state["hero_reached"],
        ltp,
    )

    if state["trail_active"] and not old_trail:
        db.event(
            "TRAIL_ON",
            f"Trade #{trade['id']}: +50% reached. Trailing activated; stop {state['stop']:.2f}",
            trade["id"]
        )

    if state["hero_reached"] and not old_hero:
        db.event(
            "HERO_200",
            f"Trade #{trade['id']}: +200% milestone reached. Runner remains open.",
            trade["id"]
        )

    if trade["mode"] == "PAPER" and state["exit_now"]:
        reason = "TRAIL_STOP" if state["trail_active"] else "INITIAL_STOP"
        db.close_trade(trade["id"], ltp, reason)
        db.event("EXIT", f"Trade #{trade['id']}: {reason} @ {ltp:.2f}", trade["id"])
        return {"closed": True, "reason": reason, "exit_price": ltp, **state}

    if after_hard_exit(cfg):
        if trade["mode"] == "LIVE":
            # Cancel protective stop before the market exit to avoid a duplicate sell.
            if trade.get("stop_order_id"):
                try:
                    broker.cancel_order(trade["stop_order_id"])
                    time.sleep(0.3)
                except Exception:
                    pass
            response = broker.place_market_order(
                trade["symbol"], trade["qty"], "SELL",
                order_tag=f"gamma_exit_{trade['id']}"
            )
            exit_id = response.get("id")
            exit_price = broker.wait_for_fill(exit_id, ltp)
        else:
            exit_price = ltp

        db.close_trade(trade["id"], exit_price, "HARD_EXIT")
        db.event(
            "EXIT",
            f"Trade #{trade['id']}: HARD_EXIT @ {exit_price:.2f}",
            trade["id"]
        )
        return {"closed": True, "reason": "HARD_EXIT", "exit_price": exit_price, **state}

    # In LIVE mode, the broker-native SL-M is responsible for stop execution.
    return {"closed": False, "ltp": ltp, **state}


def diagnose_index(broker, index_name, cfg=None):
    """
    Data-only diagnostic: explains exactly why the current 3-minute bar does or
    does not qualify. Never places an order or creates a plan.
    """
    cfg = cfg or StrategyConfig()
    meta = INDEXES[index_name]
    nearest = broker.nearest_expiry(meta["underlying"])
    expiry_date = parse_expiry_date(nearest) if nearest else None
    candles = broker.history(meta["underlying"], resolution="3")
    d = signal_diagnostics(
        candles,
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
    d["index_name"] = index_name
    d["nearest_expiry"] = expiry_date.isoformat() if expiry_date else None
    d["today_expiry"] = bool(expiry_date == now_ist().date()) if expiry_date else False
    return d

def create_plumbing_test_plan(db, broker, index_name, option_type, cfg=None):
    """
    PAPER-ONLY plumbing test. Ignores the strategy signal and selects a live
    option from the current chain so contract selection, journal, and trailing
    logic can be tested without waiting for a real setup.

    This must never be used as a trading signal.
    """
    cfg = cfg or StrategyConfig()
    meta = INDEXES[index_name]
    today = now_ist().date()

    nearest = broker.nearest_expiry(meta["underlying"])
    if not nearest:
        raise RuntimeError(f"No FYERS expiry returned for {index_name}")

    expiry_date = parse_expiry_date(nearest)
    chain_resp = broker.option_chain(
        meta["underlying"],
        strikecount=20,
        expiry_epoch=nearest["expiry"],
        greeks=True
    )
    rows = chain_resp.get("data", {}).get("optionsChain", [])
    candidate = choose_option(
        rows,
        option_type,
        cfg.premium_min,
        cfg.premium_max
    )
    if not candidate:
        raise RuntimeError("No option in the current ₹5–₹30 test premium band")

    rec = broker.validate_contract(meta["master"], candidate["symbol"], option_type)
    lot = int(rec.get("minLotSize") or 0)
    if lot <= 0:
        raise RuntimeError(f"Invalid lot size for {candidate['symbol']}")

    pid = db.add_plan(
        created_at=datetime.utcnow().isoformat(),
        trade_date=today.isoformat(),
        index_name=index_name,
        underlying=meta["underlying"],
        expiry_date=expiry_date.isoformat(),
        expiry_epoch=nearest["expiry"],
        option_type=option_type,
        strike=candidate["strike"],
        symbol=candidate["symbol"],
        lot_size=lot,
        reference_price=candidate["ltp"],
        bid=candidate["bid"],
        ask=candidate["ask"],
        oi=candidate["oi"],
        volume=candidate["volume"],
        iv=candidate["iv"],
        gamma=candidate["gamma"],
        trigger_reason="TEST ONLY - plumbing/trailing validation, NOT a strategy signal",
        status="PLANNED",
        notes="PAPER TEST ONLY. Do not execute LIVE.",
    )
    db.event(
        "TEST_PLAN_CREATED",
        f"{index_name} {option_type} PAPER test plan #{pid}: {candidate['symbol']} @ {candidate['ltp']}",
        payload=json.dumps(candidate)
    )
    return db.plan(pid)
