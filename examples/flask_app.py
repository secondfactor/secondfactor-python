"""A minimal Flask app verifying a phone number with secondfactor.ai.

    pip install flask secondfactor
    export SECONDFACTOR_API_KEY=sf_...
    export FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    flask --app flask_app run --port 3000

List `http://localhost:3000` as a return origin under Settings → Hosted
verification first. Every code sent is charged; pressing "Not your number?" on
the hosted page ends a session at no cost.

The phone number would normally come from your user's account; here a form
asks for it so the example runs on its own.
"""

import os

from flask import Flask, abort, redirect, request, session, url_for

from secondfactor import SecondFactor, SecondFactorError

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]
sf = SecondFactor(api_key=os.environ["SECONDFACTOR_API_KEY"])


@app.get("/")
def index():
    return """
        <form method="post" action="/verify">
          <input name="phone" placeholder="+9779841000001" required>
          <button>Verify with the hosted page</button>
        </form>
        <form method="post" action="/headless/start">
          <input name="phone" placeholder="+9779841000001" required>
          <button>Start a headless session</button>
        </form>
    """


# ── Hosted ──────────────────────────────────────────────────────────────────


@app.post("/verify")
def start_hosted():
    try:
        created = sf.create_session(
            request.form["phone"], return_url=url_for("verified", _external=True)
        )
    except SecondFactorError as error:
        app.logger.warning("secondfactor create_session refused: %s", error.code)
        abort(400)
    # The session id stays on the server, bound to this browser's session.
    session["sf_sid"] = created["sid"]
    return redirect(created["url"], code=303)


@app.get("/verified")
def verified():
    stored_sid = session.pop("sf_sid", None)
    if stored_sid is None:
        return "No verification in progress.", 400
    try:
        # The stored id, never request.args["sf_session_id"].
        result = sf.verify_session(stored_sid, request.args.get("sf_return_token"))
    except SecondFactorError as error:
        return f"Not verified ({error.code}). <a href='/'>Try again</a>", 400
    return f"Verified {result['phone']}."


# ── Headless ────────────────────────────────────────────────────────────────


@app.post("/headless/start")
def start_headless():
    created = sf.create_session(request.form["phone"], mode="headless")
    session["sf_sid"] = created["sid"]
    # Your frontend passes this token to @secondfactor/otp's withSession().
    return {"client_token": created["client_token"]}


@app.post("/headless/done")
def headless_done():
    stored_sid = session.pop("sf_sid", None)
    if stored_sid is None:
        abort(400)
    try:
        result = sf.verify_session(stored_sid)
    except SecondFactorError as error:
        return {"verified": False, "reason": error.code}, 400
    return {"verified": True, "phone": result["phone"]}
