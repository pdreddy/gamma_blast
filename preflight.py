"""
Run BEFORE any live trade:
    python preflight.py

This script does not place an order.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()

from config import FYERS_APP_ID, FYERS_ACCESS_TOKEN, INDEXES
from fyers_broker import FyersBroker
from engine import parse_expiry_date

IST = ZoneInfo("Asia/Kolkata")

def main():
    print("=== Gamma Blast FYERS Preflight ===")
    print("India time:", datetime.now(IST).isoformat(timespec="seconds"))

    if not FYERS_APP_ID:
        raise SystemExit("FAIL: FYERS_APP_ID is missing")
    if not FYERS_ACCESS_TOKEN:
        raise SystemExit("FAIL: FYERS_ACCESS_TOKEN is missing")

    b = FyersBroker(FYERS_APP_ID, FYERS_ACCESS_TOKEN)

    profile = b.profile()
    print("\nProfile:", profile.get("s"), profile.get("message", ""))

    funds = b.funds()
    print("Funds API:", funds.get("s"), funds.get("message", ""))

    status = b.market_status()
    print("Market status API:", status.get("s"), status.get("message", ""))

    today = datetime.now(IST).date()

    print("\nExpiry validation:")
    for name, meta in INDEXES.items():
        try:
            exp = b.nearest_expiry(meta["underlying"])
            if not exp:
                print(f"  {name}: FAIL - no expiry returned")
                continue
            d = parse_expiry_date(exp)
            same = d == today
            print(
                f"  {name}: nearest {d} ({exp.get('expiry_flag')}); "
                f"{'TODAY EXPIRY' if same else 'NOT TODAY'}"
            )
            chain = b.option_chain(
                meta["underlying"],
                strikecount=3,
                expiry_epoch=exp["expiry"],
                greeks=True
            )
            rows = chain.get("data", {}).get("optionsChain", [])
            print(f"         option-chain rows: {len(rows)}")
        except Exception as e:
            print(f"  {name}: FAIL - {e}")

    print("\nNo order was placed.")
    print("For live order eligibility, also confirm in FYERS dashboard:")
    print("  1) new/compliant API app is active for order placement")
    print("  2) static IP is validated/whitelisted")
    print("  3) NSE/BSE F&O segments you want to trade are enabled")
    print("  4) sufficient funds are available")

if __name__ == "__main__":
    main()
