# Gamma Blast FYERS — end-to-end V2

This version removes Upstox completely. FYERS is the only broker/data connection.

## Strategy currently coded

- NIFTY + SENSEX index options
- Expiry-day only by default
- 3-minute underlying candles
- SuperTrend(10,3)
- Heikin-Ashi direction
- 5-bar breakout/breakdown
- RSI momentum confirmation (55 CE / 45 PE by default)
- ATR-normalized Heikin-Ashi body strength filter
- Directional close-location filter to reject weak breakout candles
- Maximum ATR breakout extension to avoid chasing exhausted moves
- Long CE/PE only
- Option premium band ₹5–₹30
- Initial premium stop: -40%
- At +50%: trailing turns ON
- Trail stays 25% below the highest premium
- Stop never moves downward
- +200% is a milestone, NOT a forced profit exit
- Runner can continue +300%, +500%, etc. until trail or 15:25 IST hard exit
- No averaging down
- Maximum deployed premium is configurable; default ₹12,000

The quality thresholds are configurable in `.env`. They deliberately trade less
often to filter weak or overextended entries. They are hypotheses—not a promise
of better returns—so compare them on unseen dates before enabling live trading.

Example, entry premium ₹20:
- initial SL ₹12
- peak ₹30 (+50%) -> trailing stop ₹22.50
- peak ₹40 -> stop ₹30
- peak ₹60 (+200%) -> stop ₹45 and HERO milestone is logged
- peak ₹100 (+400%) -> stop ₹75

## FYERS APIs used

The code is built around official FYERS API v3 / `fyers-apiv3`:

- `history()` for 3-minute index candles
- `optionchain()` with Greeks/IV
- `quotes()` for one-shot snapshots
- FYERS Data WebSocket for live option monitoring
- broker-native SL-M protective order immediately after a live entry
- `modify_order()` to trail that broker-side stop upward
- `place_order()` for live market orders
- `orderbook()` for fill reconciliation
- `funds()`, `get_profile()`, `market_status()`, `positions()`
- Daily FYERS symbol master for exact option validation and lot size

## Important 2026 FYERS API requirement

For live order placement, the FYERS API app must be the new compliant app. FYERS says legacy apps are data-only after April 1, 2026. Live orders also require the validated/whitelisted static IP setup.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Put credentials in `.env` on YOUR machine. Never send your secret or access token in chat.

If you need a new daily access token:

```bash
python auth_cli.py
```

Then put the returned access token into:

```text
FYERS_ACCESS_TOKEN=...
```

## First validation: no orders

```bash
python preflight.py
```

It checks:
1. FYERS login/profile
2. funds API
3. market status
4. nearest FYERS expiry for NIFTY
5. nearest FYERS expiry for SENSEX
6. option-chain + Greeks response

It places ZERO orders.

## UI

For a fresh launch, run the one-command startup script. It creates `.venv` when
needed, installs changed requirements, clears local Python bytecode, and starts
Streamlit without deleting your `.env` or trading database:

```bash
./run.sh
```

On the first run, the script creates a safe `.env` template. Add your FYERS App
ID and Secret ID, then complete the browser login and validate the connection:

```bash
./run.sh --login
./run.sh --preflight
./run.sh
```

FYERS access tokens expire, so use `./run.sh --login` again whenever the UI says
the connection is not configured. The script updates only your local `.env`.

You can override the interface or port when needed:

```bash
STREAMLIT_ADDRESS=0.0.0.0 STREAMLIT_PORT=8502 ./run.sh
```

Alternatively, start Streamlit directly from an already configured environment:

```bash
streamlit run app.py
```

Pages:
- Today / Preflight
- Scanner & Plans
- Active Trades
- Trade Journal
- Events

The planned-trade screen records the exact upcoming:
- underlying
- expiry
- CE/PE
- strike
- FYERS contract symbol
- lot size
- reference premium
- bid/ask
- OI
- volume
- IV
- gamma
- reason for the signal

## Paper validation

Keep:

```text
TRADING_MODE=PAPER
AUTO_EXECUTE=false
ALLOW_LIVE_TRADING=false
```

Scan from the UI and execute the plan as PAPER. The journal and trailing logic work without sending an order.

## Live validation

Before first live order, confirm all of these:

- FYERS new/compliant API app is active for trading.
- Static IP is validated/whitelisted in FYERS.
- The program is running from that exact static IP.
- F&O segment is active for the exchange being traded.
- `preflight.py` passes.
- The scanner returns the exact intended expiry/strike/symbol.
- FYERS symbol master validates the exact symbol and lot size.
- You have enough available funds.
- You reviewed the planned quantity and initial stop.

Then locally set:

```text
TRADING_MODE=LIVE
ALLOW_LIVE_TRADING=true
```

The Streamlit UI still requires:
- a live-order review checkbox
- typing `EXECUTE LIVE`

For automatic live entries later, you would additionally set:

```text
AUTO_EXECUTE=true
```

Do not enable that for the first live expiry validation.

## Continuous monitor

```bash
python runner.py
```

The runner:
- scans once per minute inside the configured window
- writes qualifying setups to Planned Trades
- uses FYERS WebSocket prices for active options
- switches trailing on at +50%
- moves the stop upward with the peak
- logs +200% Hero milestone
- exits at the stop or hard exit
- records the completed trade in SQLite

## Today's-expiry rule

The bot does not hard-code “Tuesday/Thursday.” It asks FYERS `expiryData` for the actual nearest expiry and compares that expiry date with today in IST. This protects us from future exchange expiry-day changes and holiday shifts.

## Security

Do not put these into screenshots/chat:
- FYERS_SECRET_ID
- FYERS_ACCESS_TOKEN
- passwords/PIN/OTP
- full API callback URL containing auth code

The App ID is not used as a password, but there is no reason to post it publicly either.


## Protective-stop design

For a LIVE trade the program does not rely only on a Python/software stop.

After the BUY fill:
1. It calculates `fill × 60%`.
2. Rounds the stop to the contract's FYERS symbol-master tick size.
3. Places a separate SELL SL-M protective order at FYERS.
4. At +50%, the calculated trailing stop starts moving.
5. Every upward stop change modifies the existing FYERS SL-M order.
6. The stop is never modified downward.
7. At hard exit the bot first cancels the protective stop, then sends the market SELL.

This is materially safer than relying on REST/WebSocket logic alone, but it still cannot guarantee a maximum 40% loss during gaps, exchange/broker outages, rejected orders, or extreme illiquidity.


## Easiest local login

For the non-trading FYERS data app, set the dashboard Redirect URL to:

```text
http://localhost:8080/
```

Use the same value in `.env`, then run:

```bash
python login_local.py
```

The script opens FYERS login, receives the callback on your Mac, exchanges the auth code, stores the access token in `.env`, and validates the profile API. It does not print the access token.


## Signal diagnostics

If the UI says `No qualifying 3-minute signal`, use:

**Scanner & Plans → Why no signal?**

It shows the exact current state of:
- SuperTrend direction
- Heikin-Ashi direction
- previous 5-bar high/low
- breakout / breakdown status
- current 3-minute close
- nearest expiry and whether it is today

Do not weaken the strategy just because a signal is absent.

For plumbing validation only, the UI also has **Create PAPER test plan**. It deliberately ignores the strategy signal so you can test the journal and the -40% / +50% trailing / +200% runner logic. Those test plans are explicitly marked `TEST ONLY` and should never be executed LIVE.


## Backtest page in the UI

Start the dashboard:

```bash
python3 -m streamlit run app.py
```

Choose **Backtest** from the left sidebar.

Select:
- SENSEX or NIFTY
- start date
- end date
- approximate expiry weekday only or all trading days

Click **Run backtest**.

The UI will display:
- number of signals
- CE / PE counts
- 5 / 10 / 20 / 30-minute directional win rates
- average forward move
- favorable excursion
- adverse excursion
- directional curve
- monthly results
- every individual signal
- CSV download

The current UI backtest validates the entry signal using FYERS historical 3-minute underlying candles. It is intentionally not labeled as option P&L because exact expired-option candles are required for that calculation.
