import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS plans(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    index_name TEXT NOT NULL,
    underlying TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    expiry_epoch TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike REAL NOT NULL,
    symbol TEXT NOT NULL,
    lot_size INTEGER NOT NULL,
    reference_price REAL NOT NULL,
    bid REAL,
    ask REAL,
    oi INTEGER,
    volume INTEGER,
    iv REAL,
    gamma REAL,
    trigger_reason TEXT,
    status TEXT NOT NULL DEFAULT 'PLANNED',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS trades(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER,
    broker_order_id TEXT,
    stop_order_id TEXT,
    mode TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    index_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike REAL NOT NULL,
    expiry_date TEXT NOT NULL,
    qty INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    peak_price REAL NOT NULL,
    current_stop REAL NOT NULL,
    trail_active INTEGER NOT NULL DEFAULT 0,
    hero_reached INTEGER NOT NULL DEFAULT 0,
    last_price REAL,
    exit_price REAL,
    exit_reason TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    pnl REAL,
    notes TEXT,
    FOREIGN KEY(plan_id) REFERENCES plans(id)
);

CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    trade_id INTEGER,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload TEXT,
    FOREIGN KEY(trade_id) REFERENCES trades(id)
);

CREATE INDEX IF NOT EXISTS idx_plans_trade_lookup
ON plans(trade_date, index_name, status, id DESC);

CREATE INDEX IF NOT EXISTS idx_trades_status
ON trades(status, id);

CREATE INDEX IF NOT EXISTS idx_events_recent
ON events(id DESC);
"""

class DB:
    def __init__(self, path):
        self.path = path
        self.init()

    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def init(self):
        with self.conn() as c:
            c.executescript(SCHEMA)

    def add_plan(self, **p):
        cols = [
            "created_at","trade_date","index_name","underlying","expiry_date",
            "expiry_epoch","option_type","strike","symbol","lot_size",
            "reference_price","bid","ask","oi","volume","iv","gamma",
            "trigger_reason","status","notes"
        ]
        vals = [p.get(k) for k in cols]
        vals[0] = vals[0] or datetime.utcnow().isoformat()
        vals[18] = vals[18] or "PLANNED"
        q = f"INSERT INTO plans({','.join(cols)}) VALUES({','.join(['?'] * len(cols))})"
        with self.conn() as c:
            cur = c.execute(q, vals)
            return cur.lastrowid

    def plans(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM plans ORDER BY id DESC").fetchall()]

    def plan(self, plan_id):
        with self.conn() as c:
            r = c.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
            return dict(r) if r else None

    def existing_plan(self, trade_date, index_name):
        with self.conn() as c:
            r = c.execute("""
                SELECT * FROM plans
                WHERE trade_date=? AND index_name=?
                AND status IN ('PLANNED','ARMED','EXECUTED')
                ORDER BY id DESC LIMIT 1
            """, (trade_date, index_name)).fetchone()
            return dict(r) if r else None

    def update_plan_status(self, plan_id, status):
        with self.conn() as c:
            c.execute("UPDATE plans SET status=? WHERE id=?", (status, plan_id))

    def add_trade(self, **t):
        cols = [
            "plan_id","broker_order_id","stop_order_id","mode","opened_at","index_name","symbol",
            "option_type","strike","expiry_date","qty","entry_price","peak_price",
            "current_stop","trail_active","hero_reached","last_price","status","notes"
        ]
        vals = [t.get(k) for k in cols]
        vals[4] = vals[4] or datetime.utcnow().isoformat()
        vals[14] = int(bool(vals[14]))
        vals[15] = int(bool(vals[15]))
        vals[17] = vals[17] or "OPEN"
        q = f"INSERT INTO trades({','.join(cols)}) VALUES({','.join(['?'] * len(cols))})"
        with self.conn() as c:
            cur = c.execute(q, vals)
            return cur.lastrowid

    def open_trades(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM trades WHERE status='OPEN' ORDER BY id"
            ).fetchall()]

    def trades(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM trades ORDER BY id DESC"
            ).fetchall()]

    def update_trade_mark(self, trade_id, peak, stop, trail_active, hero_reached, last_price):
        with self.conn() as c:
            c.execute("""
                UPDATE trades SET peak_price=?, current_stop=?, trail_active=?,
                hero_reached=?, last_price=? WHERE id=?
            """, (peak, stop, int(trail_active), int(hero_reached), last_price, trade_id))

    def set_stop_order(self, trade_id, stop_order_id):
        with self.conn() as c:
            c.execute("UPDATE trades SET stop_order_id=? WHERE id=?", (stop_order_id, trade_id))

    def close_trade(self, trade_id, exit_price, reason):
        with self.conn() as c:
            row = c.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            if not row:
                return
            pnl = (float(exit_price) - float(row["entry_price"])) * int(row["qty"])
            c.execute("""
                UPDATE trades
                SET closed_at=?, exit_price=?, exit_reason=?, status='CLOSED',
                    pnl=?, last_price=?
                WHERE id=?
            """, (
                datetime.utcnow().isoformat(),
                float(exit_price),
                reason,
                pnl,
                float(exit_price),
                trade_id
            ))

    def event(self, event_type, message, trade_id=None, payload=None):
        with self.conn() as c:
            c.execute(
                "INSERT INTO events(ts,trade_id,event_type,message,payload) VALUES(?,?,?,?,?)",
                (datetime.utcnow().isoformat(), trade_id, event_type, message, payload)
            )

    def events(self, limit=300):
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()]
