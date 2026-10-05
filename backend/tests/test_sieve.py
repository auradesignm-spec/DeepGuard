"""Unit tests for the Sieve scrape integration (real logic; HTTP mocked).

Everything here runs the real ``app.services.sieve`` code. Only the single
HTTP boundary (``sieve._transport``) is replaced with a recorded fake, and the
durable store is pointed at a temp directory.

Runnable two ways:

    pytest tests/test_sieve.py          # the project's framework
    python tests/test_sieve.py          # stdlib-only fallback (no pytest dep)
"""
import contextlib
import json
import os
import shutil
import sys
import tempfile
import traceback
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import sieve, sieve_store  # noqa: E402
from app.services.sieve import SieveError  # noqa: E402


# ---------------------------------------------------------------------------
# HTTP boundary fakes
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code=200, payload=None, *, text="", headers=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers if headers is not None else {}
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class Recorder:
    """Records every transport call and replays a scripted outcome list."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, method, url, *, headers, json_body=None, files=None, data=None, timeout=None):
        self.calls.append({
            "method": method, "url": url, "headers": headers,
            "json": json_body, "files": files, "data": data, "timeout": timeout,
        })
        if not self.outcomes:
            raise AssertionError(f"unexpected extra HTTP call: {method} {url}")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@contextlib.contextmanager
def _temp_state():
    path = tempfile.mkdtemp(prefix="sieve-state-")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@contextlib.contextmanager
def _configured(key="dc_sk_test"):
    with mock.patch.object(sieve.settings, "SIEVE_API_KEY", key):
        yield


@contextlib.contextmanager
def _patched(recorder):
    with mock.patch.object(sieve, "_transport", recorder), \
            mock.patch.object(sieve.time, "sleep", lambda *_: None):
        yield


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------

def test_build_body_defaults_to_regular_compliance():
    body = sieve.build_scrape_body("Extract quotes")
    assert body == {"instruction": "Extract quotes", "compliance_mode": "regular"}


def test_build_body_accepts_and_carries_optional_fields():
    body = sieve.build_scrape_body(
        "  Extract quotes  ",
        target_urls=["https://quotes.toscrape.com"],
        fields=["text", "author"],
        schema={"type": "object"},
        output_schema={"type": "array"},
        table_shape="long",
        compliance_mode="conservative",
    )
    assert body["instruction"] == "Extract quotes"
    assert body["target_urls"] == ["https://quotes.toscrape.com"]
    assert body["fields"] == ["text", "author"]
    assert body["schema"] == {"type": "object"}
    assert body["output_schema"] == {"type": "array"}
    assert body["table_shape"] == "long"
    assert body["compliance_mode"] == "conservative"


def test_build_body_rejects_invalid_input():
    cases = [
        ("empty instruction", lambda: sieve.build_scrape_body("")),
        ("missing instruction", lambda: sieve.build_scrape_body(None)),
        ("non-http url", lambda: sieve.build_scrape_body("x", target_urls=["ftp://host"])),
        ("empty url list", lambda: sieve.build_scrape_body("x", target_urls=[])),
        ("bad fields", lambda: sieve.build_scrape_body("x", fields=[1, 2])),
        ("bad table shape", lambda: sieve.build_scrape_body("x", table_shape="tall")),
        ("bad compliance", lambda: sieve.build_scrape_body("x", compliance_mode="anything")),
        ("bad schema", lambda: sieve.build_scrape_body("x", schema="nope")),
        ("bad output_schema", lambda: sieve.build_scrape_body("x", output_schema=[1])),
    ]
    for label, fn in cases:
        try:
            fn()
        except SieveError as exc:
            assert exc.kind == "bad_request", label
            assert exc.http_status == 400, label
        else:
            raise AssertionError(f"expected bad_request for {label}")


def test_build_body_rejects_oversized_output_schema():
    big = {"type": "object", "description": "x" * (sieve.MAX_OUTPUT_SCHEMA_BYTES + 1)}
    try:
        sieve.build_scrape_body("x", output_schema=big)
    except SieveError as exc:
        assert exc.kind == "bad_request"
        assert "output_schema" in str(exc)
    else:
        raise AssertionError("expected bad_request for oversized schema")


# ---------------------------------------------------------------------------
# Request headers + secret handling
# ---------------------------------------------------------------------------

def test_request_sends_bearer_header_and_persists_without_key():
    recorder = Recorder(FakeResponse(202, {"status": "queued", "session_id": "s1", "poll": "/api/scrapes/s1"}))
    with _temp_state() as state, _configured("dc_sk_secret"), _patched(recorder):
        record = sieve.start_scrape("Do it", state_dir=state)
        call = recorder.calls[0]
        assert call["method"] == "POST"
        assert call["url"].endswith("/api/scrapes")
        assert call["headers"]["Authorization"] == "Bearer dc_sk_secret"
        assert call["json"] == {"instruction": "Do it", "compliance_mode": "regular"}
        # Persisted immediately, and the secret is nowhere in it.
        stored = sieve_store.load_session("s1", state_dir=state)
        assert stored["status"] == "queued"
        assert stored["request"]["instruction"] == "Do it"
        assert "dc_sk_secret" not in json.dumps(sieve_store.list_sessions(state_dir=state))
        assert record["session_id"] == "s1"


def test_not_configured_fails_before_any_http_call():
    recorder = Recorder()
    with _configured(""), _patched(recorder):
        try:
            sieve.poll_run("s1")
        except SieveError as exc:
            assert exc.kind == "not_configured"
            assert exc.http_status == 503
        else:
            raise AssertionError("expected not_configured")
        assert sieve.is_configured() is False
    assert recorder.calls == []


# ---------------------------------------------------------------------------
# Retry policy - the critical part
# ---------------------------------------------------------------------------

def test_start_scrape_never_retries_post_on_timeout():
    recorder = Recorder(sieve.requests.exceptions.Timeout("upstream slow"))
    with _temp_state() as state, _configured(), _patched(recorder):
        try:
            sieve.start_scrape("Do it", state_dir=state)
        except SieveError as exc:
            assert exc.kind == "timeout"
            assert exc.http_status == 504
        else:
            raise AssertionError("expected a timeout error")
    # Exactly one call: the first one may have created a run.
    assert len(recorder.calls) == 1


def test_start_scrape_never_retries_post_on_connection_error():
    recorder = Recorder(sieve.requests.exceptions.ConnectionError("reset by peer"))
    with _temp_state() as state, _configured(), _patched(recorder):
        try:
            sieve.start_scrape("Do it", state_dir=state)
        except SieveError as exc:
            assert exc.kind == "network"
        else:
            raise AssertionError("expected a network error")
    assert len(recorder.calls) == 1


def test_start_scrape_retries_429_because_no_run_was_created():
    recorder = Recorder(
        FakeResponse(429, {"error": "slow down"}, headers={"Retry-After": "0"}),
        FakeResponse(202, {"status": "queued", "session_id": "s1"}),
    )
    with _temp_state() as state, _configured(), _patched(recorder):
        record = sieve.start_scrape("Do it", state_dir=state)
    assert record["session_id"] == "s1"
    assert len(recorder.calls) == 2


def test_start_scrape_retries_5xx_then_maps_the_error():
    recorder = Recorder(*[FakeResponse(503, {"error": "sieve down"}) for _ in range(sieve.MAX_ATTEMPTS)])
    with _temp_state() as state, _configured(), _patched(recorder):
        try:
            sieve.start_scrape("Do it", state_dir=state)
        except SieveError as exc:
            assert exc.kind == "server"
            assert "sieve down" in str(exc)
        else:
            raise AssertionError("expected a server error")
    assert len(recorder.calls) == sieve.MAX_ATTEMPTS
    assert sieve_store.list_sessions(state_dir=state) == []


def test_poll_retries_network_errors():
    recorder = Recorder(
        sieve.requests.exceptions.ConnectionError("reset"),
        FakeResponse(200, {"status": "running", "session_id": "s1", "turns": 1}),
    )
    with _configured("dc_sk_secret"), _patched(recorder):
        run = sieve.poll_run("s1")
    assert run["status"] == "running"
    assert len(recorder.calls) == 2


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

def test_error_status_mapping():
    mapping = [
        (400, "bad_request", 400),
        (401, "unauthorized", 401),
        (402, "payment_required", 402),
        (404, "not_found", 404),
        (409, "conflict", 409),
        (429, "rate_limited", 429),
        (500, "server", 502),
        (503, "server", 502),
        (302, "protocol", 502),
    ]
    for status, kind, http_status in mapping:
        try:
            sieve._raise_for_status(FakeResponse(status, {"error": "upstream detail"}), "ctx")
        except SieveError as exc:
            assert exc.kind == kind, (status, exc.kind)
            assert exc.status == status
            assert exc.http_status == http_status
            assert "upstream detail" in str(exc)
        else:
            raise AssertionError(f"expected SieveError for HTTP {status}")


def test_429_error_carries_retry_after():
    try:
        sieve._raise_for_status(
            FakeResponse(429, {"error": "wait"}, headers={"Retry-After": "7"}), "ctx"
        )
    except SieveError as exc:
        assert exc.retry_after == 7.0
    else:
        raise AssertionError("expected rate_limited")


# ---------------------------------------------------------------------------
# Status handling
# ---------------------------------------------------------------------------

def test_normalize_running_keeps_polling_state():
    run = sieve.normalize_run({"status": "running", "session_id": "s", "turns": 1})
    assert run["status"] == "running"
    assert run["turns"] == 1


def test_normalize_done_exposes_files_and_result():
    run = sieve.normalize_run(
        {
            "status": "done",
            "session_id": "s",
            "turns": 2,
            "summary": "2 rows",
            "files": [{"name": "out.csv", "size": 12, "ext": "csv", "url": "/api/scrapes/s/files/out.csv"}],
            "schema_conformance": {"status": "pass"},
            "result": [{"text": "hi", "author": "a"}],
        },
        base_url="https://scrape.usesieve.com",
    )
    assert run["status"] == "done"
    assert run["files"][0]["download_url"] == "https://scrape.usesieve.com/api/scrapes/s/files/out.csv"
    assert run["result"] == [{"text": "hi", "author": "a"}]
    assert sieve.result_is_clean(run) is True


def test_normalize_refused_is_terminal_with_code():
    run = sieve.normalize_run({"status": "refused", "session_id": "s", "refusal": {"code": "quota", "message": "no credits"}})
    assert run["status"] == "refused"
    assert run["terminal"] is True
    assert run["code"] == "quota"
    assert run["quota_exhausted"] is True


def test_normalize_unknown_status_is_an_error():
    for bad in ("queued", "processing", "cancelled", None, ""):
        try:
            sieve.normalize_run({"status": bad})
        except SieveError as exc:
            assert exc.kind == "protocol", bad
        else:
            raise AssertionError(f"expected protocol error for status {bad!r}")


def test_failed_or_partial_conformance_is_never_clean():
    for status in ("partial", "fail", "not_checkable", "no_artifact", "unknown"):
        run = {"status": "done", "schema_conformance": {"status": status}}
        assert sieve.result_is_clean(run) is False, status
    assert sieve.result_is_clean({"status": "running", "schema_conformance": {"status": "pass"}}) is False
    assert sieve.conformance_state({"status": "done"}) == "unknown"


# ---------------------------------------------------------------------------
# Follow-up turn check
# ---------------------------------------------------------------------------

def test_followup_409_means_a_turn_is_in_flight():
    recorder = Recorder(FakeResponse(409, {"error": "turn in flight"}))
    with _temp_state() as state, _configured(), _patched(recorder):
        sieve_store.save_session(
            {"session_id": "s1", "request": {"instruction": "orig"}, "turns": 3}, state_dir=state
        )
        out = sieve.send_followup("s1", instruction="more", state_dir=state)
    assert out["status"] == "in_flight"
    assert out["previous_turns"] == 3
    assert len(recorder.calls) == 1


def test_followup_records_baseline_before_polling():
    recorder = Recorder(FakeResponse(202, {"status": "running"}))
    with _temp_state() as state, _configured(), _patched(recorder):
        sieve_store.save_session(
            {
                "session_id": "s1",
                "turns": 2,
                "request": {
                    "instruction": "orig",
                    "target_urls": ["https://quotes.toscrape.com"],
                    "compliance_mode": "regular",
                },
            },
            state_dir=state,
        )
        out = sieve.send_followup("s1", instruction="more", state_dir=state)
        stored = sieve_store.load_session("s1", state_dir=state)
    assert out["status"] == "accepted"
    assert out["previous_turns"] == 2
    # baseline persisted, and the stored request fields are inherited
    assert stored["previous_turns"] == 2
    assert recorder.calls[0]["json"] == {
        "instruction": "more",
        "target_urls": ["https://quotes.toscrape.com"],
        "compliance_mode": "regular",
    }


def test_wait_for_run_polls_until_terminal_with_backoff():
    seq = [
        {"status": "running", "turns": 0},
        {"status": "running", "turns": 0},
        {"status": "done", "turns": 1, "files": []},
    ]
    calls, sleeps = [], []

    def fetch(session_id):
        calls.append(session_id)
        return seq.pop(0)

    run = sieve.wait_for_run(
        "s1", fetch=fetch, sleep=sleeps.append, monotonic=lambda: 0.0,
        initial_delay=5.0, max_delay=30.0,
    )
    assert run["status"] == "done"
    assert len(calls) == 3
    assert sleeps == [5.0, 10.0]


def test_wait_for_turn_ignores_the_previous_answer():
    seq = [
        {"status": "running", "turns": 3},
        {"status": "done", "turns": 3},  # "done" but still the previous turn
        {"status": "done", "turns": 4},  # the new turn
    ]
    calls = []

    def fetch(session_id):
        calls.append(session_id)
        return seq.pop(0)

    run = sieve.wait_for_turn("s1", 3, fetch=fetch, sleep=lambda _d: None, monotonic=lambda: 0.0)
    assert run["turns"] == 4
    assert len(calls) == 3


def test_wait_for_run_returns_refused_immediately():
    calls = []

    def fetch(session_id):
        calls.append(session_id)
        return {"status": "refused", "terminal": True, "code": "quota"}

    run = sieve.wait_for_run("s1", until_turns=0, fetch=fetch, sleep=lambda _d: None, monotonic=lambda: 0.0)
    assert run["status"] == "refused"
    assert len(calls) == 1


def test_wait_for_run_respects_the_deadline():
    ticks = iter([0.0, 9999.0])
    try:
        sieve.wait_for_run(
            "s1", fetch=lambda _s: {"status": "running", "turns": 0},
            sleep=lambda _d: None, max_seconds=10.0, monotonic=lambda: next(ticks),
        )
    except SieveError as exc:
        assert exc.kind == "timeout"
    else:
        raise AssertionError("expected a timeout")


# ---------------------------------------------------------------------------
# Files, URL handling, store safety
# ---------------------------------------------------------------------------

def test_absolute_url_prefixes_relative_and_keeps_absolute():
    assert sieve.absolute_url("https://other/x", "https://base") == "https://other/x"
    assert sieve.absolute_url("/api/scrapes/s/files/f.csv", "https://base/") == (
        "https://base/api/scrapes/s/files/f.csv"
    )


def test_fetch_file_sends_bearer_to_the_prefixed_url():
    recorder = Recorder(FakeResponse(200, None, content=b"text,author\n1,a\n", headers={"Content-Type": "text/csv"}))
    with _configured("dc_sk_secret"), _patched(recorder):
        content, content_type = sieve.fetch_file(
            {"url": "/api/scrapes/s1/files/out.csv"}, base_url="https://scrape.usesieve.com"
        )
    assert content == b"text,author\n1,a\n"
    assert content_type == "text/csv"
    assert recorder.calls[0]["url"] == "https://scrape.usesieve.com/api/scrapes/s1/files/out.csv"
    assert recorder.calls[0]["headers"]["Authorization"] == "Bearer dc_sk_secret"


def test_store_rejects_unsafe_session_ids():
    with _temp_state() as state:
        for bad in ("../evil", "a/b", "", "x" * 200, None):
            try:
                sieve_store.save_session({"session_id": bad}, state_dir=state)
            except ValueError:
                pass
            else:
                raise AssertionError(f"expected ValueError for {bad!r}")
    try:
        sieve.poll_run("../evil")
    except SieveError as exc:
        assert exc.kind == "bad_request"
    else:
        raise AssertionError("expected bad_request for a traversal id")


def test_store_roundtrip_and_listing():
    with _temp_state() as state:
        sieve_store.save_session({"session_id": "a1", "status": "queued"}, state_dir=state)
        sieve_store.update_session("a1", state_dir=state, status="done", turns=2)
        stored = sieve_store.load_session("a1", state_dir=state)
        assert stored["status"] == "done" and stored["turns"] == 2
        assert [r["session_id"] for r in sieve_store.list_sessions(state_dir=state)] == ["a1"]
        assert sieve_store.load_session("../nope", state_dir=state) is None


# ---------------------------------------------------------------------------
# stdlib-only fallback runner (no pytest dependency)
# ---------------------------------------------------------------------------

def _run_all():
    names = [n for n in sorted(globals()) if n.startswith("test_") and callable(globals()[n])]
    failed = []
    for name in names:
        try:
            globals()[name]()
        except Exception:  # noqa: BLE001
            failed.append(name)
            print(f"FAIL {name}")
            traceback.print_exc()
        else:
            print(f"PASS {name}")
    print(f"\n{len(names) - len(failed)}/{len(names)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
