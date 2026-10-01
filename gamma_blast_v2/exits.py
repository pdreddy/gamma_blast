from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True)
class ExitState:
    entry: float
    entry_time: datetime
    side: str
    wall: float
    quantity: int
    remaining: int
    peak: float
    stop: float
    scaled_out: bool = False
    closed: bool = False
    reason: str | None = None


def new_position(entry, entry_time, side, wall, quantity, initial_stop=0.35):
    return ExitState(entry, entry_time, side, wall, quantity, quantity, entry, entry * (1 - initial_stop))


def update_exit(state, timestamp, spot_close, premium, straddle_decline_bars, cfg):
    if state.closed:
        return state, []
    actions = []
    invalid = spot_close <= state.wall if state.side == "CE" else spot_close >= state.wall
    if invalid:
        return replace(state, closed=True, remaining=0, reason="WALL_INVALIDATION"), [("EXIT", state.remaining)]
    if premium <= state.stop:
        return replace(state, closed=True, remaining=0, reason="PREMIUM_STOP"), [("EXIT", state.remaining)]
    if timestamp.strftime("%H:%M") >= cfg.v2_hard_exit:
        return replace(state, closed=True, remaining=0, reason="HARD_EXIT"), [("EXIT", state.remaining)]
    elapsed = (timestamp - state.entry_time).total_seconds() / 60
    target = state.entry * (1 + cfg.time_stop_target_pct / 100)
    if elapsed >= cfg.time_stop_minutes and state.peak < target:
        return replace(state, closed=True, remaining=0, reason="TIME_STOP"), [("EXIT", state.remaining)]
    peak = max(state.peak, premium)
    next_state = replace(state, peak=peak)
    if not state.scaled_out and premium >= state.entry * (1 + cfg.scale_out_pct / 100):
        amount = min(state.remaining, max(1, round(state.quantity * cfg.scale_out_fraction)))
        next_state = replace(next_state, scaled_out=True, remaining=state.remaining - amount, stop=state.entry)
        actions.append(("SCALE_OUT", amount))
    if next_state.scaled_out:
        next_state = replace(next_state, stop=max(next_state.stop, peak * (1 - cfg.v2_trail_pct / 100)))
        if straddle_decline_bars >= cfg.straddle_exit_bars and next_state.remaining:
            actions.append(("EXIT", next_state.remaining))
            next_state = replace(next_state, closed=True, remaining=0, reason="STRADDLE_DECAY")
    return next_state, actions
