"""
Easy FYERS local login helper.

Set the FYERS app Redirect URL to:
    http://localhost:8080/

This script:
1. starts a local callback listener
2. opens the FYERS login page
3. captures auth_code automatically
4. exchanges it for an access token
5. saves FYERS_ACCESS_TOKEN into .env
6. validates the token using the profile API

It never prints your access token.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import threading
import webbrowser
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from config import FYERS_APP_ID, FYERS_SECRET_ID, FYERS_REDIRECT_URI
from fyers_auth import login_url, exchange_auth_code
from fyers_apiv3 import fyersModel

HOST = "127.0.0.1"
PORT = 8080
ENV_PATH = Path(".env")
state = {"auth_code": None, "error": None}

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if params.get("auth_code"):
            state["auth_code"] = params["auth_code"][0]
            body = """
            <html><body style="font-family:Arial;padding:40px">
            <h2>FYERS login received successfully.</h2>
            <p>You can close this browser tab and return to Terminal.</p>
            </body></html>
            """
            self.send_response(200)
        else:
            state["error"] = params.get("message", ["FYERS callback did not contain auth_code"])[0]
            body = """
            <html><body style="font-family:Arial;padding:40px">
            <h2>FYERS callback received, but no auth_code was found.</h2>
            <p>Return to Terminal for details.</p>
            </body></html>
            """
            self.send_response(400)

        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        return

def update_env_token(token):
    if not ENV_PATH.exists():
        raise RuntimeError(".env file not found. Run: cp .env.example .env")

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    output = []
    replaced = False

    for line in lines:
        if line.startswith("FYERS_ACCESS_TOKEN="):
            output.append("FYERS_ACCESS_TOKEN=" + token)
            replaced = True
        else:
            output.append(line)

    if not replaced:
        output.append("FYERS_ACCESS_TOKEN=" + token)

    ENV_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")

def main():
    if not FYERS_APP_ID:
        raise SystemExit("FYERS_APP_ID is missing in .env")
    if not FYERS_SECRET_ID:
        raise SystemExit("FYERS_SECRET_ID is missing in .env")
    if not FYERS_REDIRECT_URI:
        raise SystemExit("FYERS_REDIRECT_URI is missing in .env")

    expected = f"http://localhost:{PORT}/"
    if FYERS_REDIRECT_URI.rstrip("/") != expected.rstrip("/"):
        raise SystemExit(
            "Set this exact value in .env:\n"
            f"FYERS_REDIRECT_URI={expected}\n"
            "and use the exact same Redirect URL in the FYERS dashboard."
        )

    server = HTTPServer((HOST, PORT), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = login_url(FYERS_APP_ID, FYERS_SECRET_ID, FYERS_REDIRECT_URI)

    print("FYERS local login is ready.")
    print("A browser window will open. Complete FYERS login/2FA there.")
    print("Waiting for FYERS to redirect back to this Mac...")
    webbrowser.open(url)

    timeout = time.time() + 180
    while time.time() < timeout and not state["auth_code"] and not state["error"]:
        time.sleep(0.25)

    server.shutdown()

    if state["error"]:
        raise SystemExit("Login callback error: " + str(state["error"]))
    if not state["auth_code"]:
        raise SystemExit("Timed out waiting for FYERS login. Run python login_local.py again.")

    token_response = exchange_auth_code(
        FYERS_APP_ID,
        FYERS_SECRET_ID,
        FYERS_REDIRECT_URI,
        state["auth_code"],
    )

    token = token_response.get("access_token")
    if not token:
        raise SystemExit(
            "FYERS did not return an access token. "
            "Check that App ID, Secret ID and Redirect URL exactly match the FYERS dashboard."
        )

    update_env_token(token)

    fyers = fyersModel.FyersModel(
        client_id=FYERS_APP_ID,
        token=token,
        is_async=False,
        log_path="",
    )
    profile = fyers.get_profile()

    if profile.get("s") == "ok":
        print("SUCCESS: FYERS login completed.")
        print("Access token saved to .env.")
        print("Profile API validation: OK")
        print("Next command: python preflight.py")
    else:
        print("Access token was saved, but profile validation returned:")
        print(profile)

if __name__ == "__main__":
    main()
