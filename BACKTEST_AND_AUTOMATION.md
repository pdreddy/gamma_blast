# Gamma Blast: Automation + Backtest

## 1. Fully automatic PAPER test

Run:

```bash
python auto_paper.py
```

Leave the terminal open.

The program will:
- scan once per minute during the configured entry window
- enforce `EXPIRY_DAY_ONLY=true`
- auto-create a plan only when the full signal exists
- auto-open the plan in PAPER mode
- monitor the live option premium
- use a -40% initial paper stop
- activate trailing after +50%
- trail 25% below the highest premium
- keep the trade open beyond +200%
- hard-exit at the configured time
- save every event and trade in the SQLite journal

No FYERS order is sent by this script.

You can keep the Streamlit UI open at the same time:

```bash
streamlit run app.py
```

The UI reads the same database, so planned trades, active trades, events and the journal update there.

## 2. Signal backtest from the FYERS API

Example:

```bash
python signal_backtest.py \
  --index SENSEX \
  --from 2025-10-01 \
  --to 2026-09-30
```

This tests the exact 3-minute entry logic on historical underlying candles and exports a CSV.

It reports:
- signal dates/times
- CE vs PE
- forward underlying move at 5/10/20/30 minutes
- 30-minute favorable excursion
- 30-minute adverse excursion

It does NOT calculate historical option-premium P&L.

## 3. Exact option P&L backtest: use FYERS Automate

For historical options, the cleanest FYERS-native path is **FYERS Automate → Backtest**.

FYERS Automate supports Equity Derivatives (F&O) backtesting and FYERS states historical data is available from 1 April 2024.

Suggested backtest configuration:

- Underlying: SENSEX first, then NIFTY
- Schedule window: 13:45 to 15:25 IST
- Days to expiry: 0
- Direction logic:
  - bullish path -> long CE
  - bearish path -> long PE
- Initial capital: ₹30,000
- Slippage: start with 1.0%, then stress-test 2.0%
- Initial stop: 40% option premium
- Trailing stop: configure to protect the position once profit expands
- Hard exit: 15:25
- One entry per index per expiry

Our custom rule starts trailing only after +50% and then keeps the stop 25% below the peak. If FYERS Automate's trailing node cannot express that exact delayed-activation behavior, use the closest native version for the first platform backtest and compare it against the custom live-paper journal.

## 4. What to compare

Do not optimize only for return.

Record:
- number of expiry sessions
- signals
- target/runner frequency
- stop frequency
- net P&L
- profit factor
- maximum drawdown
- consecutive losses
- average winner
- average loser
- percentage of trades that reach +50%
- percentage that reach +100%
- percentage that reach +200%
- results at 1% and 2% slippage

## 5. Live order automation later

Your current FYERS app is data-only, which is perfect for paper automation and backtesting.

Live API orders require the separate FYERS compliant algo-trading app and static-IP setup. Do not change the data-only app just to test the strategy.
