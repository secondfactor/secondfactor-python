# secondfactor.ai for Python

Verify phone numbers from your Python server with
[secondfactor.ai](https://secondfactor.ai). One file, standard library only,
Python 3.9 or later.

This library runs on **your server**. It holds your API key, which must never
reach a browser or a mobile app.

## Install

```bash
pip install secondfactor      # or: uv add secondfactor
```

## Set up

From the secondfactor.ai dashboard you need an **API key** (API keys page). For
the hosted page you also need a **return origin**, such as
`https://app.example.com`, under **Settings → Hosted verification**.

```python
import os
from secondfactor import SecondFactor, SecondFactorError

sf = SecondFactor(api_key=os.environ["SECONDFACTOR_API_KEY"])
```

## Hosted verification

Redirect the user to our page; we send the code, check it, and send them back.

```python
# 1. When the user reaches the step that needs a verified number.
created = sf.create_session(
    "+9779841000001",
    return_url="https://app.example.com/verified",
    client_reference_id=str(user.id),
)
session["sf_sid"] = created["sid"]          # keep it for this browser
return redirect(created["url"], code=303)

# 2. On https://app.example.com/verified?sf_session_id=…&sf_return_token=…
try:
    result = sf.verify_session(session.pop("sf_sid"), request.args.get("sf_return_token"))
except SecondFactorError as error:
    return start_again(reason=error.code)
mark_phone_verified(user, result["phone"])
```

**Always confirm the `sid` you stored**, never the `sf_session_id` from the URL:
anyone can edit a URL. `verify_session` succeeds once. A second call raises
`already_confirmed`, so a replayed return URL cannot sign anyone in.

## Headless verification

Draw the screens yourself. Your server creates the session and gives its token
to your frontend, which calls our session endpoints directly (see the
[`@secondfactor/js`](https://github.com/secondfactor/secondfactor-js)
client). No proxy is needed, and your API key stays on your server.

```python
created = sf.create_session("+9779841000001", mode="headless")
store_for_this_user(created["sid"])
return {"client_token": created["client_token"]}   # to your frontend

# When your frontend says the user is done:
result = sf.verify_session(stored_sid)             # raises unless VERIFIED
```

## Direct sends

Send a code and check what the user typed in your own form.

```python
verification = sf.send("+9779841000001", idempotency_key=str(uuid.uuid4()))
result = sf.check(verification["sid"], user_input)
if result["verified"]:
    ...
else:
    show_wrong_code(result["attempts_remaining"])
```

Sending again to the same number is a new verification with a new `sid` and is
charged again. Pass a fresh `idempotency_key` per user action so a retried
request is never charged twice.

## Errors

Every refused request raises `SecondFactorError` with:

- `code`: the string to branch on;
- `status`: the HTTP status, or `None` if no answer arrived;
- a message for your logs. Never show the message to your users.

| `code` | Raised by | Meaning |
|---|---|---|
| `no_return_origin`, `origin_not_allowed` | `create_session` | Add the return URL's origin under Settings → Hosted verification. |
| `missing_return_token`, `invalid_return_token` | `verify_session` | The user did not finish verifying on this browser. Start again. |
| `not_verified` | `verify_session` | The session is open, cancelled, failed or expired. |
| `already_confirmed` | `verify_session` | Confirmed before; treat as a replay. |
| `expired`, `locked`, `already_verified` | `check` | This verification can never succeed. Send a new code. |
| `unroutable` | `send`, `create_session` | Not a valid E.164 number. |
| `rate_limited`, `burst` | `send` | Too many codes to this number. Try later. |
| `insufficient_funds` | `send` | Top up your balance. |
| `network_error` | any | secondfactor.ai could not be reached. |

The full list is in the [API reference](https://secondfactor.ai/docs).

## Example

[`examples/flask_app.py`](examples/flask_app.py) is a runnable Flask app with
both flows.

## Development

The project is managed with [uv](https://docs.astral.sh/uv/). The library
lives in `src/secondfactor/` and its tests in `tests/`.

```bash
uv run python -m unittest discover -s tests -v
uv build          # the sdist and wheel, into dist/
```

The tests run against a local stub of the API and need no network or key.

## Upgrading from the dashboard download (0.1.0)

- `start()` is now `send()`. `start()` still works and warns.
- `check()` adds `verified`, and **raises** for a verification that can never
  succeed (`expired`, `locked`, `already_verified`) instead of returning it.
- `service_sid` is optional.
- Requests are sent as JSON.

## License

MIT
