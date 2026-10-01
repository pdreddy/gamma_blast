"""
Local FYERS OAuth helper.

Keep FYERS_SECRET_ID and FYERS_ACCESS_TOKEN on your own machine only.
Do NOT paste them into chat.
"""
from fyers_apiv3 import fyersModel

def session(app_id, secret_id, redirect_uri):
    return fyersModel.SessionModel(
        client_id=app_id,
        secret_key=secret_id,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
        state="gamma_blast",
    )

def login_url(app_id, secret_id, redirect_uri):
    return session(app_id, secret_id, redirect_uri).generate_authcode()

def exchange_auth_code(app_id, secret_id, redirect_uri, auth_code):
    s = session(app_id, secret_id, redirect_uri)
    s.set_token(auth_code)
    return s.generate_token()
