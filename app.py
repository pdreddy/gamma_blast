from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from config import (
    StrategyConfig, INDEXES, MODE, DB_PATH,
    FYERS_APP_ID, FYERS_ACCESS_TOKEN, ALLOW_LIVE_TRADING
)
from db import DB
from fyers_broker import FyersBroker
from engine import scan_index, execute_plan, monitor_trade, parse_expiry_date, diagnose_index, create_plumbing_test_plan
from backtest_engine import run_signal_backtest, monthly_summary

IST = ZoneInfo("Asia/Kolkata")
cfg = StrategyConfig()

st.set_page_config(
    page_title="Gamma Blast | Trading Console",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background: #f6f8fc; }
    [data-testid="stSidebar"] { background: #101827; }
    [data-testid="stSidebar"] * { color: #e5e7eb; }
    [data-testid="stSidebar"] [data-baseweb="radio"] label {
        padding: .55rem .65rem; border-radius: .65rem;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:hover { background: #1f2937; }
    .block-container { max-width: 1440px; padding-top: 2rem; padding-bottom: 4rem; }
    .hero {
        background: linear-gradient(125deg, #111827 0%, #172554 58%, #1e3a8a 100%);
        border-radius: 1.25rem; padding: 1.6rem 1.8rem; color: white;
        box-shadow: 0 18px 50px rgba(15, 23, 42, .16); margin-bottom: 1.4rem;
    }
    .hero h1 { font-size: 2rem; margin: 0 0 .3rem; color: white; }
    .hero p { color: #bfdbfe; margin: 0; }
    .eyebrow { color: #60a5fa; font-size: .75rem; font-weight: 700; letter-spacing: .12em; }
    [data-testid="stMetric"] {
        background: white; border: 1px solid #e5e7eb; border-radius: .9rem;
        padding: 1rem 1.1rem; box-shadow: 0 4px 16px rgba(15, 23, 42, .04);
    }
    [data-testid="stMetricLabel"] { color: #64748b; }
    [data-testid="stMetricValue"] { color: #0f172a; font-weight: 700; }
    [data-testid="stDataFrame"], [data-testid="stVegaLiteChart"] {
        background: white; border: 1px solid #e5e7eb; border-radius: .9rem; padding: .4rem;
    }
    h2, h3 { color: #172033; letter-spacing: -.02em; }
    .section-note { color: #64748b; margin-top: -.65rem; margin-bottom: 1rem; }
    .status-pill {
        display: inline-block; padding: .3rem .65rem; border-radius: 999px;
        background: #dcfce7; color: #166534; font-size: .75rem; font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db(path):
    return DB(path)


@st.cache_resource
def broker():
    if not FYERS_APP_ID or not FYERS_ACCESS_TOKEN:
        return None
    return FyersBroker(FYERS_APP_ID, FYERS_ACCESS_TOKEN)


@st.cache_data(ttl=900, show_spinner=False)
def cached_backtest(_broker, index_name, date_from, date_to, expiry_filter, config):
    """Avoid re-downloading identical FYERS history on every Streamlit rerun."""
    return run_signal_backtest(
        _broker,
        index_name,
        date_from,
        date_to,
        expiry_filter=expiry_filter,
        cfg=config,
    )


db = get_db(DB_PATH)
b = broker()

st.markdown("""
<div class="hero">
  <div class="eyebrow">FYERS · OPTIONS COMMAND CENTER</div>
  <h1>Gamma Blast</h1>
  <p>Scan expiry-day momentum, validate signals and manage risk from one focused workspace.</p>
</div>
""", unsafe_allow_html=True)

page = st.sidebar.radio(
    "WORKSPACE",
    ["Today / Preflight", "Backtest", "Scanner & Plans", "Active Trades", "Trade Journal", "Events"]
)
st.sidebar.divider()
st.sidebar.markdown(f"**{datetime.now(IST).strftime('%d %b %Y · %H:%M')} IST**")
st.sidebar.caption("MARKET CLOCK")
st.sidebar.markdown(f"`{MODE}` &nbsp; mode")
st.sidebar.caption(f"₹{cfg.max_capital_per_trade:,.0f} maximum premium / trade")
st.sidebar.divider()
st.sidebar.caption("Risk rules · 40% initial stop · trail at +50% · 25% gap")

if page == "Today / Preflight":
    st.subheader("Connection")
    c1, c2, c3 = st.columns(3)
    c1.metric("App ID configured", "Yes" if FYERS_APP_ID else "No")
    c2.metric("Access token configured", "Yes" if FYERS_ACCESS_TOKEN else "No")
    c3.metric("Live unlocked", "Yes" if ALLOW_LIVE_TRADING else "No")

    if st.button("Run FYERS preflight"):
        if not b:
            st.error("Configure FYERS_APP_ID and FYERS_ACCESS_TOKEN locally first.")
        else:
            try:
                st.success("FYERS API authenticated.")
                st.json(b.profile())
                st.json(b.funds())
                st.json(b.market_status())

                rows = []
                today = datetime.now(IST).date()
                for name, meta in INDEXES.items():
                    exp = b.nearest_expiry(meta["underlying"])
                    d = parse_expiry_date(exp) if exp else None
                    rows.append({
                        "index": name,
                        "underlying": meta["underlying"],
                        "nearest_expiry": str(d) if d else None,
                        "expiry_flag": exp.get("expiry_flag") if exp else None,
                        "is_today_expiry": d == today if d else False,
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            except Exception as e:
                st.error(str(e))

    st.warning("Do not paste FYERS secret ID or access token into chat. Keep them only in your local .env/secret manager.")


elif page == "Backtest":
    st.subheader("Strategy lab")
    st.markdown(
        '<p class="section-note">Test directional signal quality against historical 3-minute index candles.</p>',
        unsafe_allow_html=True,
    )
    st.info(
        "Runs the exact 3-minute ENTRY SIGNAL on FYERS historical index candles. "
        "The return numbers below measure directional movement of the underlying, "
        "not exact historical option-premium P&L.",
        icon="ℹ️",
    )

    if not b:
        st.error("FYERS connection is not configured.", icon="🔐")
        st.markdown("""
        **Connect FYERS in three steps:**
        1. Add `FYERS_APP_ID` and `FYERS_SECRET_ID` to your local `.env` file.
        2. Set the FYERS app redirect URL to `http://localhost:8080/`.
        3. Stop this app, run `./run.sh --login`, then restart with `./run.sh`.

        Your access token is saved locally and is never required in this screen.
        """)
    else:
        with st.container(border=True):
            st.markdown("#### Test configuration")
            st.caption("Choose a market, date range and trading-day universe.")
            c1, c2, c3 = st.columns(3)
            bt_index = c1.selectbox("Index", ["SENSEX", "NIFTY"], key="bt_index")
            bt_from = c2.date_input("From", value=pd.Timestamp.today().date() - pd.Timedelta(days=365))
            bt_to = c3.date_input("To", value=pd.Timestamp.today().date())
            expiry_choice = st.radio(
                "Days to test",
                ["Approx expiry weekday only", "All trading days"],
                horizontal=True,
            )

        if expiry_choice == "Approx expiry weekday only":
            expiry_filter = "approx_expiry_weekday"
            st.info(
                "Approximation: NIFTY Tuesday, SENSEX Thursday. "
                "Historical holiday-shifted expiries are not reconstructed here."
            )
        else:
            expiry_filter = "all_days"

        if st.button("Run backtest", type="primary", use_container_width=True):
            if bt_from >= bt_to:
                st.error("From date must be before To date.")
            else:
                try:
                    with st.spinner(
                        f"Downloading FYERS 3-minute history and backtesting {bt_index}..."
                    ):
                        results, summary = cached_backtest(
                            b,
                            bt_index,
                            bt_from.isoformat(),
                            bt_to.isoformat(),
                            expiry_filter,
                            cfg,
                        )
                    st.session_state["bt_results"] = results
                    st.session_state["bt_summary"] = summary
                except Exception as e:
                    st.error(f"Backtest failed: {e}")

        results = st.session_state.get("bt_results")
        summary = st.session_state.get("bt_summary")

        if summary:
            st.divider()
            left, right = st.columns([3, 1], vertical_alignment="center")
            left.subheader("Backtest results")
            right.markdown('<div class="status-pill">● ANALYSIS COMPLETE</div>', unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Signals", summary.get("signals", 0))
            m2.metric("CE signals", summary.get("ce_signals", 0))
            m3.metric("PE signals", summary.get("pe_signals", 0))
            m4.metric(
                "30-min directional win rate",
                f"{summary.get('win_rate_30m', 0):.1f}%"
                if summary.get("signals", 0) else "-"
            )

            if summary.get("signals", 0):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Avg 5-min move", f"{summary.get('avg_5m_pct', 0):.3f}%")
                c2.metric("Avg 10-min move", f"{summary.get('avg_10m_pct', 0):.3f}%")
                c3.metric("Avg 20-min move", f"{summary.get('avg_20m_pct', 0):.3f}%")
                c4.metric("Avg 30-min move", f"{summary.get('avg_30m_pct', 0):.3f}%")

                c5, c6, c7, c8 = st.columns(4)
                c5.metric("5-min win rate", f"{summary.get('win_rate_5m', 0):.1f}%")
                c6.metric("10-min win rate", f"{summary.get('win_rate_10m', 0):.1f}%")
                c7.metric("20-min win rate", f"{summary.get('win_rate_20m', 0):.1f}%")
                c8.metric("30-min win rate", f"{summary.get('win_rate_30m', 0):.1f}%")

                c9, c10 = st.columns(2)
                c9.metric("Avg favorable excursion, 30m", f"{summary.get('avg_mfe_30m_pct', 0):.3f}%")
                c10.metric("Avg adverse excursion, 30m", f"{summary.get('avg_mae_30m_pct', 0):.3f}%")

                st.markdown("### Directional growth")
                st.caption("Compounded 30-minute directional returns. Baseline = 1.00.")
                chart_df = results[["timestamp", "directional_curve"]].copy()
                chart_df = chart_df.set_index("timestamp")
                st.line_chart(chart_df, color="#2563eb", height=360)

                tab_monthly, tab_signals, tab_export = st.tabs(
                    ["Monthly breakdown", "Signal ledger", "Export"]
                )
                with tab_monthly:
                    monthly = monthly_summary(results)
                    st.dataframe(
                        monthly,
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "win_rate_30m_pct": st.column_config.ProgressColumn(
                                "30m win rate", format="%.1f%%", min_value=0, max_value=100
                            ),
                            "avg_30m_move_pct": st.column_config.NumberColumn("Avg 30m", format="%.3f%%"),
                            "median_30m_move_pct": st.column_config.NumberColumn("Median 30m", format="%.3f%%"),
                        },
                    )

                display_cols = [
                    "date", "timestamp", "signal", "underlying_entry",
                    "fwd_5m_pct", "fwd_10m_pct", "fwd_20m_pct", "fwd_30m_pct",
                    "mfe_30m_pct", "mae_30m_pct"
                ]
                with tab_signals:
                    st.dataframe(
                        results[display_cols],
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "timestamp": st.column_config.DatetimeColumn("Time", format="DD MMM YYYY, hh:mm a"),
                            "underlying_entry": st.column_config.NumberColumn("Entry", format="%.2f"),
                            **{
                                col: st.column_config.NumberColumn(col.replace("_", " ").title(), format="%.3f%%")
                                for col in display_cols if col.endswith("_pct")
                            },
                        },
                    )

                with tab_export:
                    st.write("Download the complete signal-level dataset for deeper analysis.")
                    st.download_button(
                        "Download backtest CSV",
                        results.to_csv(index=False),
                        f"gamma_blast_{bt_index}_signal_backtest.csv",
                        "text/csv",
                        use_container_width=True,
                    )

                st.warning(
                    "This page validates signal quality using the underlying. "
                    "It does NOT yet calculate the exact ₹30,000 option-account P&L, "
                    "because that requires historical expired-option candles."
                )
            else:
                st.info("No qualifying signals were found for the selected period/filter.")


elif page == "Scanner & Plans":
    if not b:
        st.error("FYERS connection is not configured.")
    else:
        idx = st.selectbox("Index", ["NIFTY", "SENSEX"])
        cscan, cdiag = st.columns(2)
        if cscan.button("Scan current setup"):
            try:
                out = scan_index(db, b, idx, cfg, force_scan=True)
                if not out:
                    st.info("No plan generated.")
                elif out.get("no_trade"):
                    st.info(out["reason"])
                else:
                    st.success(f"Plan #{out['id']} generated")
                    st.json(out)
            except Exception as e:
                st.error(str(e))

        if cdiag.button("Why no signal?"):
            try:
                d = diagnose_index(b, idx, cfg)
                st.subheader("Current 3-minute diagnostics")
                st.json(d)
                if d.get("signal"):
                    st.success(f"Current qualifying signal: {d['signal']}")
                else:
                    bull = d.get("bull_conditions", {})
                    bear = d.get("bear_conditions", {})
                    st.write("Bullish path:", bull)
                    st.write("Bearish path:", bear)
            except Exception as e:
                st.error(str(e))

        st.divider()
        st.subheader("PAPER plumbing test")
        st.caption("Use this only to test contract selection, journaling, and trailing-stop behavior. It is NOT a trading signal.")
        test_type = st.selectbox("Test option type", ["CE", "PE"], key="plumbing_type")
        if st.button("Create PAPER test plan"):
            try:
                p = create_plumbing_test_plan(db, b, idx, test_type, cfg)
                st.success(f"Paper test plan #{p['id']} created. Do not execute this plan LIVE.")
                st.json(p)
            except Exception as e:
                st.error(str(e))

    st.subheader("Planned trades")
    plans = db.plans()
    if plans:
        df = pd.DataFrame(plans)
        st.dataframe(df, hide_index=True, use_container_width=True)

        actionable = [p for p in plans if p["status"] in ("PLANNED", "ARMED")]
        if actionable:
            pid = st.selectbox("Selected plan", [p["id"] for p in actionable])
            plan = db.plan(pid)
            x, y = st.columns(2)
            if x.button("Arm selected plan"):
                db.update_plan_status(pid, "ARMED")
                st.rerun()

            selected_mode = y.selectbox("Execution", ["PAPER", "LIVE"])

            if selected_mode == "LIVE":
                consent = st.checkbox("I reviewed the exact symbol, expiry, strike, quantity, premium and stop rules.")
                phrase = st.text_input("Type EXECUTE LIVE to enable the button")
                live_ok = consent and phrase.strip().upper() == "EXECUTE LIVE"
            else:
                live_ok = True

            if st.button("Execute selected plan", disabled=not live_ok):
                if not b:
                    st.error("FYERS is not configured.")
                else:
                    try:
                        tid = execute_plan(db, b, plan, selected_mode, cfg)
                        st.success(f"Trade #{tid} opened.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
    else:
        st.info("No planned trades recorded yet.")

elif page == "Active Trades":
    trades = db.open_trades()
    if not trades:
        st.info("No active trades.")
    else:
        st.dataframe(pd.DataFrame(trades), hide_index=True, use_container_width=True)
        tid = st.selectbox("Trade", [t["id"] for t in trades])
        trade = next(t for t in trades if t["id"] == tid)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Entry", f"₹{trade['entry_price']:.2f}")
        c2.metric("Peak", f"₹{trade['peak_price']:.2f}")
        c3.metric("Current stop", f"₹{trade['current_stop']:.2f}")
        c4.metric("+200% reached", "Yes" if trade["hero_reached"] else "No")

        if trade["mode"] == "PAPER":
            manual_ltp = st.number_input(
                "Paper LTP",
                min_value=0.01,
                value=float(trade["last_price"] or trade["entry_price"]),
                step=0.5
            )
            if st.button("Apply paper tick"):
                try:
                    out = monitor_trade(db, b, trade, ltp=manual_ltp, cfg=cfg)
                    st.json(out)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        else:
            if st.button("Refresh live LTP + trailing logic"):
                try:
                    out = monitor_trade(db, b, trade, cfg=cfg)
                    st.json(out)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

elif page == "Trade Journal":
    rows = db.trades()
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.download_button(
            "Download trade journal CSV",
            df.to_csv(index=False),
            "gamma_blast_fyers_journal.csv",
            "text/csv"
        )
    else:
        st.info("No trades yet.")

elif page == "Events":
    rows = db.events()
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("No events yet.")
