# Easy FYERS Setup

## On the FYERS "Create App" screen

Enter:

Name:
```text
GammaBlastTest
```

Redirect URL:
```text
http://localhost:8080/
```

Leave **Webhook** empty.

Check **I Accept the API Terms and Conditions**.

Click **Create**.

If FYERS rejects `http://localhost:8080/`, stop there and send a screenshot of the error. Do not enter a random URL.

## After the app is created

FYERS will show an App ID and Secret ID.

Keep the Secret ID private.

On your Mac:

```bash
cp .env.example .env
nano .env
```

Fill:

```text
FYERS_APP_ID=YOUR_APP_ID
FYERS_SECRET_ID=YOUR_SECRET_ID
FYERS_REDIRECT_URI=http://localhost:8080/
```

Leave:

```text
FYERS_ACCESS_TOKEN=
TRADING_MODE=PAPER
AUTO_EXECUTE=false
ALLOW_LIVE_TRADING=false
```

Then run:

```bash
python login_local.py
```

A browser opens automatically. Complete FYERS login/2FA. The callback returns to your Mac automatically and the script saves the access token into `.env`.

Then run:

```bash
python preflight.py
```

Paste only the `preflight.py` output into ChatGPT. Do not paste `.env`.
