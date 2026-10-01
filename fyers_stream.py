"""
FYERS WebSocket price store.

Use this for live option monitoring instead of looping REST quotes.
"""
import threading
import time
from fyers_apiv3.FyersWebsocket import data_ws

class PriceStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._prices = {}

    def set(self, symbol, ltp, message=None):
        with self._lock:
            self._prices[symbol] = {
                "ltp": float(ltp),
                "ts": time.time(),
                "message": message or {},
            }

    def get(self, symbol):
        with self._lock:
            return self._prices.get(symbol)

class MarketStream:
    def __init__(self, app_id, access_token, symbols):
        self.app_id = app_id
        self.access_token = access_token
        self.symbols = list(dict.fromkeys(symbols))
        self.store = PriceStore()
        self.socket = None
        self.thread = None
        self.error = None

    def _on_message(self, msg):
        symbol = msg.get("symbol")
        ltp = msg.get("ltp")
        if symbol and ltp is not None:
            self.store.set(symbol, ltp, msg)

    def _on_error(self, msg):
        self.error = msg

    def _on_close(self, msg):
        pass

    def _on_open(self):
        self.socket.subscribe(symbols=self.symbols, data_type="SymbolUpdate")
        self.socket.keep_running()

    def start(self):
        token = f"{self.app_id}:{self.access_token}"
        self.socket = data_ws.FyersDataSocket(
            access_token=token,
            log_path="",
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=self._on_open,
            on_close=self._on_close,
            on_error=self._on_error,
            on_message=self._on_message,
        )
        self.thread = threading.Thread(target=self.socket.connect, daemon=True)
        self.thread.start()
        return self

    def ltp(self, symbol, max_age=10):
        row = self.store.get(symbol)
        if not row:
            return None
        if time.time() - row["ts"] > max_age:
            return None
        return row["ltp"]
