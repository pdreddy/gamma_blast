from dotenv import load_dotenv
load_dotenv()

from config import FYERS_APP_ID, FYERS_SECRET_ID, FYERS_REDIRECT_URI
from fyers_auth import login_url, exchange_auth_code

if not all([FYERS_APP_ID, FYERS_SECRET_ID, FYERS_REDIRECT_URI]):
    raise SystemExit(
        "Set FYERS_APP_ID, FYERS_SECRET_ID and FYERS_REDIRECT_URI in your local .env first."
    )

print("Open this URL in your browser and log in to FYERS:")
print(login_url(FYERS_APP_ID, FYERS_SECRET_ID, FYERS_REDIRECT_URI))
print()
code = input("Paste ONLY the auth_code returned to your redirect URL: ").strip()
resp = exchange_auth_code(
    FYERS_APP_ID, FYERS_SECRET_ID, FYERS_REDIRECT_URI, code
)
print(resp)
print("\nCopy access_token into FYERS_ACCESS_TOKEN in your LOCAL .env. Do not share it.")
