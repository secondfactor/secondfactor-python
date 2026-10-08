"""secondfactor.ai for Python servers. Standard library only.

This library runs on **your server**. It holds your API key, which must never
reach a browser or a mobile app, and calls secondfactor.ai for you.

There are two ways to verify a phone number with it.

**Verification sessions (recommended).** Your server creates a session and
either redirects the user to our hosted page or hands a short-lived token to
your own frontend. When the user is done, your server confirms the session,
once::

    from secondfactor import SecondFactor, SecondFactorError

    sf = SecondFactor(api_key=os.environ["SECONDFACTOR_API_KEY"])

    # Hosted: redirect the user to our page.
    session = sf.create_session("+9779841000001", return_url="https://app.example.com/verified")
    store_for_this_browser(session["sid"])
    return redirect(session["url"])

    # Back on https://app.example.com/verified?sf_session_id=...&sf_return_token=...
    try:
        result = sf.verify_session(stored_sid, request.args.get("sf_return_token"))
    except SecondFactorError as error:
        ...  # not verified: error.code says why
    sign_in(phone=result["phone"])

**Direct sends.** Your server sends a code and checks the one your user typed
in your own form::

    verification = sf.send("+9779841000001")
    result = sf.check(verification["sid"], user_input)
    if result["verified"]:
        ...

Every refused request raises `SecondFactorError`, whose `code` is a stable
string to branch on. A wrong code is not an error: `check` returns it with
`verified` false and the attempts remaining.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
import warnings

__all__ = ["SecondFactor", "SecondFactorError"]
__version__ = "0.2.0"

DEFAULT_BASE_URL = "https://api.secondfactor.ai"
USER_AGENT = f"secondfactor-python/{__version__}"

# A check answered 409 carries the verification, whose status says why it can
# never succeed. Each becomes an error code, so a caller branches on one field.
_DEAD_VERIFICATION_CODES = {
    "EXPIRED": "expired",
    "LOCKED": "locked",
    "VERIFIED": "already_verified",
}

# Plain http:// is accepted only for these hosts, so a local stub or tunnel can
# be used in development while the API key never crosses a network unencrypted.
_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Treat every redirect as an error instead of following it.

    urllib would otherwise resend the request's headers, the API key among
    them, to whatever host the `Location` names, including over plain HTTP.
    The API never redirects, so a redirect means something between this client
    and the API is wrong, and the safe answer is to stop.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_RefuseRedirects)


class SecondFactorError(Exception):
    """A request secondfactor.ai refused, or could not be reached for.

    `code` is the stable string to branch on, such as `rate_limited`,
    `insufficient_funds`, `not_verified` or `network_error`. `status` is the
    HTTP status of a refusal, or `None` when no answer arrived or a successful
    answer could not be trusted. The message is written for
    developers and is safe to log; never show it to your end users.
    """

    def __init__(self, message, code=None, status=None):
        super().__init__(message)
        self.code = code
        self.status = status


class SecondFactor:
    """A client for one organization's API key.

    `service_sid` (`VA…`) is optional. Every organization has exactly one
    Service, so when it is omitted the client looks it up on first use.
    """

    def __init__(self, api_key, service_sid=None, base_url=DEFAULT_BASE_URL, timeout=10):
        if not api_key:
            raise ValueError("api_key is required.")
        parts = urllib.parse.urlsplit(base_url)
        if not parts.hostname or not (
            parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in _LOOPBACK_HOSTS)
        ):
            raise ValueError("base_url must be an https:// URL; plain http:// is accepted only for localhost.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._service_sid = service_sid

    # ─────────────────────────── verification sessions ───────────────────────────

    def create_session(
        self, to, mode="hosted", return_url=None, client_reference_id=None, template_sid=None
    ):
        """Start verifying `to` (E.164, for example `+9779841000001`).

        A hosted session needs `return_url`, on an origin listed under
        Settings → Hosted verification, and answers with `url`: redirect the
        user there. A headless session (`mode="headless"`) takes no
        `return_url` and answers with `client_token`: give it to your own
        frontend. Either is returned only this once.

        Store the returned `sid` against the user's pending sign-in; it is what
        you confirm with `verify_session` later. Creating a session is free;
        each code it sends is charged.
        """
        body = {
            "To": to,
            "Mode": mode,
            "ReturnUrl": return_url,
            "ClientReferenceId": client_reference_id,
            "TemplateSid": template_sid,
        }
        return self._request("POST", self._service_path("VerificationSessions"), body)

    def retrieve_session(self, sid):
        """The session's current state. Reading a session proves nothing about
        who verified it; use `verify_session` for that."""
        return self._request("GET", self._service_path(f"VerificationSessions/{_segment(sid)}"))

    def verify_session(self, stored_sid, return_token=None):
        """Accept the outcome of the session you stored, exactly once.

        Pass the `sid` you stored when you created the session, never the
        `sf_session_id` from the return URL: that parameter only helps you find
        your stored session, and anyone can edit a URL. For a hosted session,
        pass the `sf_return_token` from the return URL; a headless session
        needs none.

        Returns `{"phone", "client_reference_id", "session"}`, where `phone` is
        the number that was proven. Raises `SecondFactorError` otherwise, with
        `code` one of `missing_return_token`, `invalid_return_token`,
        `not_verified`, `already_confirmed` or `not_found`, among others.
        """
        body = {"ReturnToken": return_token} if return_token else {}
        session = self._request(
            "POST", self._service_path(f"VerificationSessions/{_segment(stored_sid)}/Confirm"), body
        )
        # The API answers 2xx only for a verified session, but a caller signs a
        # user in on what this returns, so it fails closed if that ever changes.
        if session.get("status") != "VERIFIED":
            raise SecondFactorError("secondfactor.ai confirmed a session that is not verified.", "not_verified")
        return {
            "phone": session["to"],
            "client_reference_id": session.get("client_reference_id"),
            "session": session,
        }

    # ───────────────────────────────── direct sends ─────────────────────────────────

    def send(self, to, code=None, template_sid=None, idempotency_key=None):
        """Send a code to `to` (E.164). Returns the verification; keep its `sid`.

        Sending again to the same number is a new verification, with a new
        `sid` and code, and is charged again; that is how a resend works. Pass
        `idempotency_key`, new for each user action, to retry one safely. Pass
        `code` only if you generate codes yourself; you then check it yourself
        too.
        """
        body = {"To": to, "Code": code, "TemplateSid": template_sid}
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        return self._request("POST", self._service_path("Verifications"), body, headers=headers)

    def check(self, verification_sid, code):
        """Check the code your user typed.

        Returns the verification with `verified` added. `verified` is true only
        when the code was right. A wrong code returns `verified` false with
        `attempts_remaining`. A verification that can never succeed raises
        `SecondFactorError` with `code` `expired`, `locked` or
        `already_verified`; only a new send helps.
        """
        try:
            body = self._request(
                "POST",
                self._service_path("VerificationCheck"),
                {"VerificationSid": verification_sid, "Code": str(code).strip()},
                answers=(422,),
            )
        except SecondFactorError as error:
            if error.status == 409 and error.code in _DEAD_VERIFICATION_CODES:
                error.code = _DEAD_VERIFICATION_CODES[error.code]
            raise
        return {**body, "verified": body.get("status") == "VERIFIED"}

    def start(self, to, code=None, template_sid=None):
        """Deprecated: use `send`."""
        warnings.warn("start() is deprecated; use send().", DeprecationWarning, stacklevel=2)
        return self.send(to, code=code, template_sid=template_sid)

    # ─────────────────────────────────── internals ───────────────────────────────────

    def service_sid(self):
        """Your Service SID (`VA…`), looked up once when not given."""
        if self._service_sid is None:
            services = self._request("GET", "/v2/Services")["services"]
            self._service_sid = services[0]["sid"]
        return self._service_sid

    def _service_path(self, path):
        return f"/v2/Services/{_segment(self.service_sid())}/{path}"

    def _request(self, method, path, body=None, headers=None, answers=()):
        """One call. Returns the JSON body of a 2xx, or of a status in `answers`.

        Anything else raises `SecondFactorError`. A 409 from the check endpoint
        carries a verification rather than an error envelope; its `status`
        becomes the error code, which `check` then names.
        """
        data = None
        all_headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **(headers or {}),
        }
        if body is not None:
            data = json.dumps({key: value for key, value in body.items() if value is not None}).encode()
            all_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=all_headers, method=method
        )
        try:
            with _opener.open(request, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                payload = json.load(exc)
            except ValueError:
                payload = {}
            finally:
                exc.close()
            if exc.code in answers and "sid" in payload:
                return payload
            code = payload.get("code") or payload.get("status")
            message = payload.get("message") or f"secondfactor.ai answered HTTP {exc.code}."
            raise SecondFactorError(message, code if isinstance(code, str) else None, exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SecondFactorError(f"secondfactor.ai unreachable: {exc}", "network_error") from exc


def _segment(value):
    """A path segment, quoted so an identifier cannot change the path."""
    return urllib.parse.quote(str(value), safe="")
