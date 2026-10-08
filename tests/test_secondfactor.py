"""Tests against a stub of the secondfactor.ai API on localhost.

Run with `python -m unittest -v`. The stub answers with the exact shapes the
real API documents, so these tests hold two things: what the library sends
(paths, headers, bodies) and how it turns each answer into a return value or a
`SecondFactorError`. The second matters most, because a caller signs a user in
on what `verify_session` and `check` return.
"""

import json
import threading
import unittest
import warnings
from http.server import BaseHTTPRequestHandler, HTTPServer

from secondfactor import USER_AGENT, SecondFactor, SecondFactorError

SERVICE = "VA0a1b2c3d4e5f60718293a4b5c6d7e8f9"
SESSION = {
    "sid": "VSN26H7K3MQ2XWZ8RT4",
    "mode": "hosted",
    "status": "VERIFIED",
    "to": "+9779841000001",
    "client_reference_id": "signup-8812",
    "confirmed": True,
}


def envelope(status, code, message="Refused."):
    return status, {"status": status, "code": code, "message": message}


class Stub(BaseHTTPRequestHandler):
    """Records every request and answers from `Stub.routes`.

    A route maps `(method, path)` to `(status, body)`. A `str` body is sent as
    it is, to imitate a proxy's HTML error page. Anything unrouted is a 404 in
    the API's error envelope.
    """

    routes = {}
    requests = []

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else ""
        Stub.requests.append({
            "method": self.command,
            "path": self.path,
            "headers": self.headers,  # case-insensitive, as HTTP header names are
            "body": json.loads(raw) if raw else None,
        })
        status, payload = Stub.routes.get((self.command, self.path), envelope(404, "not_found"))
        self.send_response(status)
        self.send_header("Content-Type", "text/html" if isinstance(payload, str) else "application/json")
        self.end_headers()
        self.wfile.write((payload if isinstance(payload, str) else json.dumps(payload)).encode())

    do_GET = do_POST = _handle

    def log_message(self, *args):
        pass


class StubTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Stub.routes = {("GET", "/v2/Services"): (200, {"services": [{"sid": SERVICE}]})}
        Stub.requests = []
        self.sf = SecondFactor("sf_key.secret", base_url=self.base)

    def route(self, method, path, answer):
        Stub.routes[(method, f"/v2/Services/{SERVICE}/{path}")] = answer

    def last(self):
        return Stub.requests[-1]


class ServiceLookupTest(StubTestCase):
    def test_the_service_is_looked_up_once_and_reused(self):
        self.route("POST", "Verifications", (201, {"sid": "VE1"}))

        self.sf.send("+9779841000001")
        self.sf.send("+9779841000002")

        lookups = [r for r in Stub.requests if r["path"] == "/v2/Services"]
        self.assertEqual(len(lookups), 1)
        self.assertEqual(self.sf.service_sid(), SERVICE)

    def test_a_given_service_sid_needs_no_lookup(self):
        sf = SecondFactor("sf_key.secret", service_sid=SERVICE, base_url=self.base)
        self.route("POST", "Verifications", (201, {"sid": "VE1"}))

        sf.send("+9779841000001")

        self.assertEqual([r["path"] for r in Stub.requests], [f"/v2/Services/{SERVICE}/Verifications"])

    def test_an_api_key_is_required(self):
        with self.assertRaises(ValueError):
            SecondFactor("")


class WireTest(StubTestCase):
    def test_every_request_carries_the_key_the_user_agent_and_json(self):
        self.route("POST", "Verifications", (201, {"sid": "VE1"}))

        self.sf.send("+9779841000001", idempotency_key="click-1")

        headers = self.last()["headers"]
        self.assertEqual(headers["X-API-Key"], "sf_key.secret")
        self.assertEqual(headers["User-Agent"], USER_AGENT)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Idempotency-Key"], "click-1")
        # Parameters left unset are not sent at all, rather than sent as null.
        self.assertEqual(self.last()["body"], {"To": "+9779841000001"})


class SessionTest(StubTestCase):
    def test_create_a_hosted_session(self):
        self.route("POST", "VerificationSessions", (201, {"sid": SESSION["sid"], "url": "https://verify/#vst_x"}))

        session = self.sf.create_session(
            "+9779841000001", return_url="https://app.example.com/verified", client_reference_id="signup-8812"
        )

        self.assertEqual(session["url"], "https://verify/#vst_x")
        self.assertEqual(self.last()["body"], {
            "To": "+9779841000001",
            "Mode": "hosted",
            "ReturnUrl": "https://app.example.com/verified",
            "ClientReferenceId": "signup-8812",
        })

    def test_create_a_headless_session(self):
        self.route("POST", "VerificationSessions", (201, {"sid": SESSION["sid"], "client_token": "vst_x"}))

        session = self.sf.create_session("+9779841000001", mode="headless")

        self.assertEqual(session["client_token"], "vst_x")
        self.assertEqual(self.last()["body"], {"To": "+9779841000001", "Mode": "headless"})

    def test_a_refused_create_raises_with_the_servers_code_and_message(self):
        self.route("POST", "VerificationSessions", envelope(400, "no_return_origin", "Add a return origin."))

        with self.assertRaises(SecondFactorError) as caught:
            self.sf.create_session("+9779841000001", return_url="https://app.example.com/")

        self.assertEqual((caught.exception.code, caught.exception.status), ("no_return_origin", 400))
        self.assertEqual(str(caught.exception), "Add a return origin.")

    def test_verify_session_confirms_the_stored_sid_and_returns_the_proven_phone(self):
        self.route("POST", f"VerificationSessions/{SESSION['sid']}/Confirm", (200, SESSION))

        result = self.sf.verify_session(SESSION["sid"], "vsr_token")

        self.assertEqual(result["phone"], "+9779841000001")
        self.assertEqual(result["client_reference_id"], "signup-8812")
        self.assertEqual(result["session"], SESSION)
        self.assertEqual(self.last()["method"], "POST")
        self.assertEqual(self.last()["body"], {"ReturnToken": "vsr_token"})

    def test_a_headless_confirm_sends_no_token(self):
        self.route("POST", f"VerificationSessions/{SESSION['sid']}/Confirm", (200, SESSION))

        self.sf.verify_session(SESSION["sid"])

        self.assertEqual(self.last()["body"], {})

    def test_every_refused_confirm_raises_so_nobody_is_signed_in_by_mistake(self):
        for status, code in [
            (400, "missing_return_token"),
            (409, "not_verified"),
            (409, "already_confirmed"),
            (422, "invalid_return_token"),
            (404, "not_found"),
        ]:
            with self.subTest(code=code):
                self.route("POST", f"VerificationSessions/{SESSION['sid']}/Confirm", envelope(status, code))
                with self.assertRaises(SecondFactorError) as caught:
                    self.sf.verify_session(SESSION["sid"], "vsr_token")
                self.assertEqual((caught.exception.code, caught.exception.status), (code, status))

    def test_a_session_id_stays_one_path_segment(self):
        with self.assertRaises(SecondFactorError):
            self.sf.retrieve_session("../../Verifications")

        self.assertEqual(
            self.last()["path"], f"/v2/Services/{SERVICE}/VerificationSessions/..%2F..%2FVerifications"
        )

    def test_retrieve_session(self):
        self.route("GET", f"VerificationSessions/{SESSION['sid']}", (200, SESSION))

        self.assertEqual(self.sf.retrieve_session(SESSION["sid"])["status"], "VERIFIED")


class DirectSendTest(StubTestCase):
    def test_send_then_a_right_code(self):
        self.route("POST", "Verifications", (201, {"sid": "VE1", "status": "PENDING"}))
        self.route("POST", "VerificationCheck", (200, {"sid": "VE1", "status": "VERIFIED"}))

        sid = self.sf.send("+9779841000001")["sid"]
        result = self.sf.check(sid, " 123456 ")

        self.assertTrue(result["verified"])
        self.assertEqual(self.last()["body"], {"VerificationSid": "VE1", "Code": "123456"})

    def test_a_wrong_code_is_an_answer_not_an_error(self):
        self.route("POST", "VerificationCheck", (422, {"sid": "VE1", "status": "PENDING", "attempts_remaining": 4}))

        result = self.sf.check("VE1", "000000")

        self.assertFalse(result["verified"])
        self.assertEqual(result["attempts_remaining"], 4)

    def test_a_verification_that_can_never_succeed_raises_with_a_named_code(self):
        for status, code in [("EXPIRED", "expired"), ("LOCKED", "locked"), ("VERIFIED", "already_verified")]:
            with self.subTest(status=status):
                self.route("POST", "VerificationCheck", (409, {"sid": "VE1", "status": status}))
                with self.assertRaises(SecondFactorError) as caught:
                    self.sf.check("VE1", "123456")
                self.assertEqual((caught.exception.code, caught.exception.status), (code, 409))

    def test_a_code_you_supplied_cannot_be_checked_here(self):
        self.route("POST", "VerificationCheck", envelope(409, "client_code"))

        with self.assertRaises(SecondFactorError) as caught:
            self.sf.check("VE1", "123456")

        self.assertEqual(caught.exception.code, "client_code")

    def test_a_refused_send_raises_with_its_code(self):
        self.route("POST", "Verifications", envelope(402, "insufficient_funds"))

        with self.assertRaises(SecondFactorError) as caught:
            self.sf.send("+9779841000001")

        self.assertEqual((caught.exception.code, caught.exception.status), ("insufficient_funds", 402))

    def test_start_still_works_but_warns(self):
        self.route("POST", "Verifications", (201, {"sid": "VE1"}))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertEqual(self.sf.start("+9779841000001")["sid"], "VE1")

        self.assertTrue(any(issubclass(w.category, DeprecationWarning) for w in caught))


class FailureTest(StubTestCase):
    def test_a_non_json_error_page_is_still_a_secondfactor_error(self):
        self.route("POST", "Verifications", (502, "<html>Bad gateway</html>"))

        with self.assertRaises(SecondFactorError) as caught:
            self.sf.send("+9779841000001")

        self.assertEqual((caught.exception.code, caught.exception.status), (None, 502))

    def test_no_answer_at_all_is_a_network_error(self):
        closed = SecondFactor("sf_key.secret", service_sid=SERVICE, base_url="http://127.0.0.1:9", timeout=1)

        with self.assertRaises(SecondFactorError) as caught:
            closed.send("+9779841000001")

        self.assertEqual((caught.exception.code, caught.exception.status), ("network_error", None))


if __name__ == "__main__":
    unittest.main()
