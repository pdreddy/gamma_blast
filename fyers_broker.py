from datetime import datetime
from zoneinfo import ZoneInfo
import time
import pandas as pd
from fyers_apiv3 import fyersModel

from symbol_master import validate_option, lot_size, tick_size, round_to_tick

IST = ZoneInfo("Asia/Kolkata")

class FyersBroker:
    def __init__(self, app_id, access_token):
        if not app_id or not access_token:
            raise ValueError("FYERS_APP_ID and FYERS_ACCESS_TOKEN are required")
        self.app_id = app_id
        self.access_token = access_token
        self.api = fyersModel.FyersModel(
            client_id=app_id,
            token=access_token,
            is_async=False,
            log_path="",
        )

    def profile(self):
        return self.api.get_profile()

    def funds(self):
        return self.api.funds()

    def market_status(self):
        return self.api.market_status()

    def positions(self):
        return self.api.positions()

    def orderbook(self):
        return self.api.orderbook()

    def tradebook(self):
        return self.api.tradebook()

    def history(self, symbol, resolution="3", start_date=None, end_date=None, oi=False):
        today = datetime.now(IST).date().isoformat()
        data = {
            "symbol": symbol,
            "resolution": str(resolution),
            "date_format": "1",
            "range_from": start_date or today,
            "range_to": end_date or today,
            "cont_flag": "1",
        }
        if oi:
            data["oi_flag"] = "1"

        resp = self.api.history(data=data)
        if resp.get("s") != "ok":
            raise RuntimeError(f"FYERS history failed: {resp}")
        candles = resp.get("candles") or []
        cols = ["epoch","open","high","low","close","volume"]
        if candles and len(candles[0]) >= 7:
            cols.append("oi")
        df = pd.DataFrame(candles, columns=cols)
        if df.empty:
            return pd.DataFrame(columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert(IST)
        return df.drop(columns=["epoch"]).sort_values("timestamp").reset_index(drop=True)

    def quotes(self, symbols):
        if isinstance(symbols, (list, tuple)):
            symbols = ",".join(symbols)
        return self.api.quotes(data={"symbols": symbols})

    def ltp(self, symbol):
        r = self.quotes([symbol])
        if r.get("s") != "ok":
            raise RuntimeError(f"FYERS quote failed: {r}")
        items = r.get("d") or []
        if not items:
            raise RuntimeError(f"No quote for {symbol}")
        return float(items[0].get("v", {}).get("lp"))

    def option_chain(self, underlying, strikecount=20, expiry_epoch="", greeks=True):
        data = {
            "symbol": underlying,
            "strikecount": int(strikecount),
            "timestamp": str(expiry_epoch or ""),
        }
        if greeks:
            data["greeks"] = "1"
        r = self.api.optionchain(data=data)
        if r.get("s") != "ok":
            raise RuntimeError(f"FYERS option chain failed: {r}")
        return r

    def expiry_list(self, underlying):
        r = self.option_chain(underlying, strikecount=1, expiry_epoch="", greeks=False)
        return r.get("data", {}).get("expiryData", [])

    def nearest_expiry(self, underlying):
        expiries = self.expiry_list(underlying)
        if not expiries:
            return None
        return expiries[0]

    def place_market_order(self, symbol, qty, side, order_tag="gamma_blast"):
        data = {
            "symbol": symbol,
            "qty": int(qty),
            "type": 2,
            "side": 1 if side.upper() == "BUY" else -1,
            "productType": "INTRADAY",
            "limitPrice": 0,
            "stopPrice": 0,
            "disclosedQty": 0,
            "validity": "DAY",
            "offlineOrder": False,
            "stopLoss": 0,
            "takeProfit": 0,
            "orderTag": order_tag[:30],
            "isSliceOrder": False,
        }
        r = self.api.place_order(data=data)
        if r.get("s") != "ok":
            raise RuntimeError(f"FYERS place_order failed: {r}")
        return r

    def find_order(self, order_id):
        book = self.orderbook()
        rows = book.get("orderBook") or []
        for r in rows:
            if str(r.get("id")) == str(order_id):
                return r
        return None

    def wait_for_fill(self, order_id, fallback_ltp, timeout=8):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                row = self.find_order(order_id)
                if row and int(row.get("status") or 0) == 2:
                    avg = float(row.get("tradedPrice") or row.get("avgPrice") or 0)
                    if avg > 0:
                        return avg
            except Exception:
                pass
            time.sleep(0.6)
        return float(fallback_ltp)


    def tick_size(self, master, symbol):
        return tick_size(master, symbol)

    def place_stop_market_order(self, symbol, qty, stop_price, order_tag="gamma_sl"):
        data = {
            "symbol": symbol,
            "qty": int(qty),
            "type": 3,  # SL-M
            "side": -1,
            "productType": "INTRADAY",
            "limitPrice": 0,
            "stopPrice": float(stop_price),
            "disclosedQty": 0,
            "validity": "DAY",
            "offlineOrder": False,
            "stopLoss": 0,
            "takeProfit": 0,
            "orderTag": order_tag[:30],
            "isSliceOrder": False,
        }
        r = self.api.place_order(data=data)
        if r.get("s") != "ok":
            raise RuntimeError(f"FYERS protective stop order failed: {r}")
        return r

    def modify_stop_market_order(self, order_id, qty, stop_price):
        data = {
            "id": str(order_id),
            "type": 3,
            "qty": int(qty),
            "stopPrice": float(stop_price),
            "limitPrice": 0,
        }
        r = self.api.modify_order(data=data)
        if r.get("s") != "ok":
            raise RuntimeError(f"FYERS stop modification failed: {r}")
        return r

    def cancel_order(self, order_id):
        r = self.api.cancel_order(data={"id": str(order_id)})
        return r

    def order_state(self, order_id):
        row = self.find_order(order_id)
        if not row:
            return None
        return {
            "status": int(row.get("status") or 0),
            "avg_price": float(row.get("tradedPrice") or row.get("avgPrice") or 0),
            "raw": row,
        }

    def rounded_stop(self, master, symbol, price):
        return round_to_tick(price, self.tick_size(master, symbol))

    def validate_contract(self, master, symbol, option_type):
        rec = validate_option(master, symbol, option_type=option_type)
        return rec

    def lot_size(self, master, symbol):
        return lot_size(master, symbol)
