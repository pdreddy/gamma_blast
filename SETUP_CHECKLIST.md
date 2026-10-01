# What I need from you to validate the FYERS setup

Do NOT send any password, FYERS Secret ID, access token, OTP, PIN, or auth code.

Please send only:

1. **API app status**
   - Tell me whether you already created/activated the new FYERS API app for order placement.
   - A screenshot is fine, but redact App Secret, access token, auth code and personal identifiers.

2. **Static IP**
   - Tell me only: `configured` or `not configured`.
   - Do not send the actual IP unless you specifically need networking help.

3. **Derivative segments**
   - Is NSE F&O enabled?
   - Is BSE F&O enabled?

4. **Capital / sizing confirmation**
   - Starting test capital: currently configured ₹30,000.
   - Maximum premium deployed per trade: currently configured ₹12,000.
   - Confirm or give a different maximum.

5. **Indexes**
   - NIFTY only, SENSEX only, or both.

6. **First execution mode**
   - PAPER first, or LIVE after preflight.

After that, run locally:

```bash
python preflight.py
```

Paste the OUTPUT into chat. The output contains no API secret/token in this project.

Then we can inspect:
- market status
- nearest expiry
- whether today is actually expiry
- option-chain availability
- and only then review a planned trade.
