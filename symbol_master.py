import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://public.fyers.in/sym_details/{}_sym_master.json"
CACHE = Path.home() / ".fyers" / "sym_master"

def load_master(master, force=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{master}.json"

    fresh = False
    if path.exists():
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
        fresh = (mtime == datetime.now(timezone.utc).date())

    if force or not fresh:
        req = urllib.request.Request(
            BASE.format(master),
            headers={"User-Agent": "gamma-blast-fyers/1.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)

    with open(path, encoding="utf-8") as f:
        return json.load(f)

def info(master, symbol):
    return load_master(master).get(symbol)

def lot_size(master, symbol):
    rec = info(master, symbol)
    if not rec:
        raise ValueError(f"{symbol} not found in {master} FYERS symbol master")
    lot = int(rec.get("minLotSize") or 0)
    if lot <= 0:
        raise ValueError(f"Invalid lot size for {symbol}")
    return lot

def validate_option(master, symbol, option_type=None):
    rec = info(master, symbol)
    if not rec:
        raise ValueError(f"{symbol} not found in FYERS {master} master")
    if option_type and rec.get("optType") != option_type:
        raise ValueError(f"{symbol} optType is {rec.get('optType')}, expected {option_type}")
    return rec


def tick_size(master, symbol):
    rec = info(master, symbol)
    if not rec:
        raise ValueError(f"{symbol} not found in {master} FYERS symbol master")
    tick = float(rec.get("tickSize") or 0.05)
    return tick if tick > 0 else 0.05

def round_to_tick(price, tick):
    # Round to nearest valid exchange tick.
    return round(round(float(price) / float(tick)) * float(tick), 8)
