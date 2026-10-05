"""Sieve scrape API client - server-side only.

Secrets
    ``SIEVE_API_KEY`` comes from ``app.config`` (pydantic-settings, read from
    ``backend/.env``). The key grants full account access, so it only ever
    travels as an ``Authorization: Bearer`` header on a server-side call. It is
    never logged, returned in a response, or included in an error message.

HTTP
    Outbound calls reuse ``requests`` - the same client
    ``app.services.news_detector`` already uses for the Google Fact Check call.
    No second HTTP library is introduced. All traffic funnels through
    :func:`_transport`, which is the single boundary tests replace.

Jobs
    DeepGuard has no job queue, so this module exposes explicit start / poll /
    follow-up calls instead of adding one. Runs take minutes, so the caller
    polls (starting at ~5s, backing off to ~30s); ``app.main`` exposes those
    calls as endpoints and ``scripts/sieve_scrape.py`` drives them from a CLI.

    A started session is persisted through :mod:`app.services.sieve_store`
    *before* anything else can happen, so a crash resumes polling from the
    stored ``session_id`` rather than starting a second, billable run.

Retry policy
    ``POST /api/scrapes`` has no idempotency key, so a timeout or connection
    error is never retried (the first call may have succeeded). A 429 or 5xx
    response *is* retried because no run was created in that case. GETs retry
    network errors, 429 and 5xx with exponential backoff.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from app.config import settings
from app.services import sieve_store

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://scrape.usesieve.com"
DEFAULT_TIMEOUT = 30.0
POLL_TIMEOUT = 30.0
DOWNLOAD_TIMEOUT = 120.0
MAX_ATTEMPTS = 3
MAX_BACKOFF = 30.0
MAX_OUTPUT_SCHEMA_BYTES = 32 * 1024

STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_REFUSED = "refused"

COMPLIANCE_MODES = ("conservative", "regular", "yolo")
TABLE_SHAPES = ("long", "wide")

# Conformance states reported by a run that had an output_schema.
CONFORMANCE_PASS = "pass"
CONFORMANCE_PARTIAL = "partial"
CONFORMANCE_FAIL = "fail"
CONFORMANCE_NOT_CHECKABLE = "not_checkable"
CONFORMANCE_NO_ARTIFACT = "no_artifact"

_HTTP_STATUS_BY_KIND = {
    "not_configured": 503,
    "bad_request": 400,
    "unauthorized": 401,
    "payment_required": 402,
    "not_found": 404,
    "conflict": 409,
    "rate_limited": 429,
    "server": 502,
    "network": 502,
    "timeout": 504,
    "protocol": 502,
}

_STATUS_KINDS = {
    400: "bad_request",
    401: "unauthorized",
    402: "payment_required",
    404: "not_found",
    409: "conflict",
    429: "rate_limited",
}


class SieveError(Exception):
    """Typed failure from the Sieve integration.

    ``http_status`` maps the failure onto an HTTP status for the API layer so
    a caller never has to guess.
    """

    def __init__(self, kind: str, message: str, *, status: Optional[int] = None,
                 retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.retry_after = retry_after

    @property
    def http_status(self) -> int:
        return _HTTP_STATUS_BY_KIND.get(self.kind, 502)

    def as_detail(self) -> Dict[str, Any]:
        return {"kind": self.kind, "message": str(self), "upstream_status": self.status}


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def is_configured() -> bool:
    """True when a Sieve key is present. Nothing else in the app changes."""
    return bool((settings.SIEVE_API_KEY or "").strip())


def _api_key(api_key: Optional[str] = None) -> str:
    return (api_key if api_key is not None else settings.SIEVE_API_KEY) or ""


def _base_url(base_url: Optional[str] = None) -> str:
    return (base_url or settings.SIEVE_BASE_URL or DEFAULT_BASE_URL).rstrip("/")


def absolute_url(url: str, base_url: Optional[str] = None) -> str:
    """Turn a relative ``files[].url`` into an absolute URL."""
    if url.startswith(("http://", "https://")):
        return url
    return f"{_base_url(base_url)}/{url.lstrip('/')}"


def _unsafe_session_id(session_id: Any) -> bool:
    return not sieve_store.is_safe_session_id(session_id)


# ---------------------------------------------------------------------------
# HTTP boundary + retry policy
# ---------------------------------------------------------------------------

def _transport(method: str, url: str, *, headers: Dict[str, str],
               json_body: Optional[Dict[str, Any]] = None,
               files: Optional[Dict[str, Any]] = None,
               data: Optional[Dict[str, Any]] = None,
               timeout: float = DEFAULT_TIMEOUT):
    """The one place this module touches the network. Tests replace this."""
    return requests.request(
        method, url, headers=headers, json=json_body, files=files, data=data, timeout=timeout
    )


def _retry_after(resp) -> Optional[float]:
    raw = (getattr(resp, "headers", None) or {}).get("Retry-After")
    if raw is None:
        return None
    try:
        return max(0.0, float(str(raw).strip()))
    except (TypeError, ValueError):
        return None


def _loggable_url(url: str) -> str:
    """Strip query strings so nothing sensitive ends up in a log line."""
    return url.split("?", 1)[0]


def _send(method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None,
          files: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None,
          base_url: Optional[str] = None, api_key: Optional[str] = None,
          timeout: float = DEFAULT_TIMEOUT, retry_network: bool = False,
          max_attempts: int = MAX_ATTEMPTS):
    """Perform one logical request with the module's retry policy applied."""
    key = _api_key(api_key)
    if not key:
        raise SieveError("not_configured", "SIEVE_API_KEY is not set")
    url = path if path.startswith(("http://", "https://")) else f"{_base_url(base_url)}{path}"
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    delay = 1.0
    resp = None
    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            resp = _transport(method, url, headers=headers, json_body=json_body,
                              files=files, data=data, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - transport failures are all mapped
            kind = "timeout" if "timeout" in type(exc).__name__.lower() else "network"
            # A POST may already have created a run: never retry it blindly.
            if not retry_network or attempt >= max_attempts:
                raise SieveError(
                    kind, f"{method} {_loggable_url(url)} failed ({kind})", retry_after=None
                ) from exc
            logger.warning("sieve %s %s: %s; retrying in %.1fs", method, _loggable_url(url), kind, delay)
            time.sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF)
            continue

        code = getattr(resp, "status_code", 0)
        if code == 429 or code >= 500:
            if attempt >= max_attempts:
                return resp
            wait = _retry_after(resp)
            wait = delay if wait is None else wait
            logger.warning("sieve %s %s: HTTP %s; retrying in %.1fs", method, _loggable_url(url), code, wait)
            time.sleep(wait)
            delay = min(delay * 2, MAX_BACKOFF)
            continue
        return resp
    return resp


def _json(resp) -> Dict[str, Any]:
    try:
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise SieveError("protocol", "sieve returned a non-JSON response") from exc
    if not isinstance(payload, dict):
        raise SieveError("protocol", "sieve returned an unexpected JSON payload")
    return payload


def _error_detail(resp) -> str:
    """Best-effort, truncated, newline-free upstream message (never logs)."""
    detail = ""
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            for field in ("error", "detail", "message"):
                value = payload.get(field)
                if isinstance(value, str) and value.strip():
                    detail = value.strip()
                    break
                if isinstance(value, dict) and isinstance(value.get("message"), str):
                    detail = value["message"].strip()
                    break
    except Exception:  # noqa: BLE001
        detail = ""
    if not detail:
        try:
            detail = (resp.text or "").strip()
        except Exception:  # noqa: BLE001
            detail = ""
    detail = " ".join(detail.split())
    return detail[:300]


def _raise_for_status(resp, context: str) -> None:
    code = getattr(resp, "status_code", 0)
    kind = _STATUS_KINDS.get(code)
    if kind is None:
        kind = "server" if code >= 500 else "protocol"
    detail = _error_detail(resp)
    suffix = f" - {detail}" if detail else ""
    raise SieveError(
        kind, f"{context}: HTTP {code}{suffix}", status=code, retry_after=_retry_after(resp)
    )


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------

def _bad(message: str) -> None:
    raise SieveError("bad_request", message)


def build_scrape_body(instruction: Optional[str], *, target_urls: Optional[List[str]] = None,
                      fields: Optional[List[str]] = None, schema: Optional[Dict[str, Any]] = None,
                      output_schema: Optional[Dict[str, Any]] = None,
                      table_shape: Optional[str] = None,
                      compliance_mode: Optional[str] = None) -> Dict[str, Any]:
    """Validate and build the JSON body shared by start and follow-up calls."""
    if not isinstance(instruction, str) or not instruction.strip():
        _bad("instruction is required (plain language, non-empty)")
    body: Dict[str, Any] = {"instruction": instruction.strip()}

    if target_urls is not None:
        if not isinstance(target_urls, (list, tuple)) or not target_urls:
            _bad("target_urls must be a non-empty list of public http(s) URLs")
        for url in target_urls:
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                _bad("target_urls entries must start with http:// or https://")
        body["target_urls"] = list(target_urls)

    if fields is not None:
        if not isinstance(fields, (list, tuple)) or not all(isinstance(f, str) for f in fields):
            _bad("fields must be a list of column names")
        body["fields"] = list(fields)

    if schema is not None:
        if not isinstance(schema, dict):
            _bad("schema must be a JSON object")
        body["schema"] = schema

    if output_schema is not None:
        if not isinstance(output_schema, dict):
            _bad("output_schema must be a JSON Schema object")
        if len(json.dumps(output_schema).encode("utf-8")) > MAX_OUTPUT_SCHEMA_BYTES:
            _bad(f"output_schema exceeds {MAX_OUTPUT_SCHEMA_BYTES} bytes")
        body["output_schema"] = output_schema

    mode = compliance_mode or settings.SIEVE_COMPLIANCE_MODE or "regular"
    if mode not in COMPLIANCE_MODES:
        _bad(f"compliance_mode must be one of {COMPLIANCE_MODES}")
    body["compliance_mode"] = mode

    if table_shape is not None:
        if table_shape not in TABLE_SHAPES:
            _bad(f"table_shape must be one of {TABLE_SHAPES}")
        body["table_shape"] = table_shape

    return body


# ---------------------------------------------------------------------------
# Response handling
# ---------------------------------------------------------------------------

def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _normalize_file(entry: Dict[str, Any], base_url: Optional[str]) -> Dict[str, Any]:
    url = entry.get("url", "")
    normalized = {
        "name": entry.get("name", ""),
        "size": entry.get("size"),
        "ext": entry.get("ext", ""),
        "url": url,
    }
    if isinstance(url, str) and url:
        normalized["download_url"] = absolute_url(url, base_url)
    return normalized


def normalize_run(payload: Dict[str, Any], *, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Map a raw run payload onto the three states the caller must handle."""
    if not isinstance(payload, dict):
        raise SieveError("protocol", "sieve run payload is not an object")

    status = payload.get("status")
    session_id = payload.get("session_id")
    turns = _as_int(payload.get("turns"))

    if status == STATUS_RUNNING:
        # Schema-repair turns also read as "running" - keep polling.
        return {"status": STATUS_RUNNING, "session_id": session_id, "turns": turns, "raw": payload}

    if status == STATUS_DONE:
        files = [
            _normalize_file(entry, base_url)
            for entry in (payload.get("files") or [])
            if isinstance(entry, dict)
        ]
        return {
            "status": STATUS_DONE,
            "session_id": session_id,
            "turns": turns,
            "summary": payload.get("summary"),
            "files": files,
            "schema_conformance": payload.get("schema_conformance") or {},
            "result": payload.get("result"),
            "raw": payload,
        }

    if status == STATUS_REFUSED:
        refusal = payload.get("refusal")
        refusal = refusal if isinstance(refusal, dict) else {}
        code = refusal.get("code")
        return {
            "status": STATUS_REFUSED,
            "terminal": True,
            "session_id": session_id,
            "turns": turns,
            "refusal": refusal,
            "code": code,
            "quota_exhausted": code == "quota",
            "raw": payload,
        }

    raise SieveError("protocol", f"unknown sieve run status: {status!r}")


def conformance_state(run_or_payload: Dict[str, Any]) -> str:
    """Return the schema-conformance status of a run (``unknown`` if absent)."""
    source = run_or_payload.get("schema_conformance") if isinstance(run_or_payload, dict) else None
    if not isinstance(source, dict):
        return "unknown"
    status = source.get("status")
    return status if isinstance(status, str) and status else "unknown"


def result_is_clean(run: Dict[str, Any]) -> bool:
    """True only for a ``done`` run whose declared schema fully validated.

    ``partial`` means declared columns are missing, ``fail`` means the payload
    is still non-conforming, and ``not_checkable``/``no_artifact`` mean nothing
    was checkable - none of those may be presented as clean data.
    """
    if run.get("status") != STATUS_DONE:
        return False
    return conformance_state(run) == CONFORMANCE_PASS


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

def start_scrape(instruction: str, *, target_urls: Optional[List[str]] = None,
                 fields: Optional[List[str]] = None, schema: Optional[Dict[str, Any]] = None,
                 output_schema: Optional[Dict[str, Any]] = None,
                 table_shape: Optional[str] = None, compliance_mode: Optional[str] = None,
                 document: Optional[bytes] = None,
                 document_name: str = "document",
                 state_dir: Optional[str] = None,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None) -> Dict[str, Any]:
    """Start a run and durably persist its ``session_id`` before returning."""
    body = build_scrape_body(
        instruction, target_urls=target_urls, fields=fields, schema=schema,
        output_schema=output_schema, table_shape=table_shape, compliance_mode=compliance_mode,
    )

    files = data = None
    if document is not None:
        files = {"file": (document_name, document)}
        data = {k: v if isinstance(v, str) else json.dumps(v) for k, v in body.items()}

    resp = _send(
        "POST", "/api/scrapes", json_body=None if files else body, files=files, data=data,
        base_url=base_url, api_key=api_key, retry_network=False, max_attempts=MAX_ATTEMPTS,
    )
    if resp.status_code != 202:
        _raise_for_status(resp, "start scrape")

    payload = _json(resp)
    session_id = payload.get("session_id")
    if not session_id:
        raise SieveError("protocol", "start scrape: 202 response without a session_id")

    record = {
        "session_id": session_id,
        "status": payload.get("status", "queued"),
        "poll": payload.get("poll") or f"/api/scrapes/{session_id}",
        "instruction": body["instruction"],
        "request": body,
        "turns": 0,
        "previous_turns": 0,
        "files": [],
        "created_at": None,
    }
    # Persist before anything else: a crash must resume, not re-run (and re-charge).
    return sieve_store.save_session(record, state_dir=state_dir)


def poll_run(session_id: str, *, base_url: Optional[str] = None,
             api_key: Optional[str] = None) -> Dict[str, Any]:
    """Fetch the current state of a run (GET retries are safe)."""
    if _unsafe_session_id(session_id):
        _bad("invalid session_id")
    resp = _send(
        "GET", f"/api/scrapes/{session_id}", base_url=base_url, api_key=api_key,
        retry_network=True, max_attempts=MAX_ATTEMPTS + 1, timeout=POLL_TIMEOUT,
    )
    if resp.status_code != 200:
        _raise_for_status(resp, "poll scrape")
    return normalize_run(_json(resp), base_url=base_url)


def send_followup(session_id: str, *, instruction: Optional[str] = None,
                  target_urls: Optional[List[str]] = None, fields: Optional[List[str]] = None,
                  schema: Optional[Dict[str, Any]] = None,
                  output_schema: Optional[Dict[str, Any]] = None,
                  table_shape: Optional[str] = None,
                  compliance_mode: Optional[str] = None,
                  previous_turns: Optional[int] = None,
                  state_dir: Optional[str] = None, base_url: Optional[str] = None,
                  api_key: Optional[str] = None) -> Dict[str, Any]:
    """Add a turn to an existing run.

    The turn baseline is recorded before the POST. The caller must then poll
    until ``status == "done"`` *and* ``turns`` has advanced past the returned
    ``previous_turns``, otherwise it would read the previous answer.
    """
    if _unsafe_session_id(session_id):
        _bad("invalid session_id")

    record = sieve_store.load_session(session_id, state_dir=state_dir) or {}
    prior = record.get("request") or {}

    body = build_scrape_body(
        instruction if instruction is not None else prior.get("instruction"),
        target_urls=target_urls if target_urls is not None else prior.get("target_urls"),
        fields=fields if fields is not None else prior.get("fields"),
        schema=schema if schema is not None else prior.get("schema"),
        output_schema=output_schema if output_schema is not None else prior.get("output_schema"),
        table_shape=table_shape if table_shape is not None else prior.get("table_shape"),
        compliance_mode=compliance_mode if compliance_mode is not None else prior.get("compliance_mode"),
    )

    if previous_turns is None:
        previous_turns = _as_int(record.get("turns")) or 0

    # Record the baseline first so the post-poll comparison survives a crash.
    sieve_store.update_session(
        session_id, state_dir=state_dir, previous_turns=previous_turns,
        turn_requested_at=_now(),
    )

    resp = _send(
        "POST", f"/api/scrapes/{session_id}/messages", json_body=body,
        base_url=base_url, api_key=api_key, retry_network=False, max_attempts=MAX_ATTEMPTS,
    )

    if resp.status_code == 409:
        # A turn is already in flight: wait, then resend.
        return {"status": "in_flight", "session_id": session_id, "previous_turns": previous_turns}

    if resp.status_code not in (200, 202):
        _raise_for_status(resp, "follow-up message")

    payload = _json(resp)
    sieve_store.update_session(
        session_id, state_dir=state_dir, turn_accepted_at=_now(),
        last_status=payload.get("status", "running"),
    )
    return {
        "status": "accepted",
        "session_id": session_id,
        "previous_turns": previous_turns,
        "payload": payload,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def wait_for_run(session_id: str, *, until_turns: Optional[int] = None,
                 fetch: Optional[Callable[[str], Dict[str, Any]]] = None,
                 sleep: Optional[Callable[[float], None]] = None,
                 max_seconds: float = 1800.0, initial_delay: float = 5.0,
                 max_delay: float = 30.0,
                 on_status: Optional[Callable[[Dict[str, Any]], None]] = None,
                 monotonic: Optional[Callable[[], float]] = None) -> Dict[str, Any]:
    """Poll until the run is terminal.

    Returns on ``done``/``refused``. When ``until_turns`` is given the run must
    also report more turns than that baseline, so a follow-up never returns the
    previous answer.
    """
    fetch = fetch or poll_run
    sleep = sleep or time.sleep
    monotonic = monotonic or time.monotonic

    delay = initial_delay
    started = monotonic()
    while True:
        run = fetch(session_id)
        if on_status is not None:
            on_status(run)

        status = run.get("status")
        if status == STATUS_REFUSED:
            return run
        if status == STATUS_DONE:
            turns = run.get("turns")
            if until_turns is None or (isinstance(turns, int) and turns > until_turns):
                return run

        if monotonic() - started >= max_seconds:
            raise SieveError(
                "timeout", f"scrape {session_id} did not finish within {max_seconds:.0f}s"
            )
        sleep(delay)
        delay = min(delay * 2, max_delay)


def wait_for_turn(session_id: str, previous_turns: int, **kwargs: Any) -> Dict[str, Any]:
    """Poll a follow-up until it is done *and* the turn counter advanced."""
    return wait_for_run(session_id, until_turns=previous_turns, **kwargs)


# ---------------------------------------------------------------------------
# Files + credits
# ---------------------------------------------------------------------------

def fetch_file(file_ref: Any, *, base_url: Optional[str] = None, api_key: Optional[str] = None,
               timeout: float = DOWNLOAD_TIMEOUT) -> Tuple[bytes, str]:
    """Download a delivered file (relative ``url`` + Bearer header)."""
    url = file_ref.get("url") if isinstance(file_ref, dict) else file_ref
    if not isinstance(url, str) or not url:
        _bad("file reference has no url")
    resp = _send(
        "GET", absolute_url(url, base_url), base_url=base_url, api_key=api_key,
        retry_network=True, max_attempts=MAX_ATTEMPTS + 1, timeout=timeout,
    )
    if resp.status_code != 200:
        _raise_for_status(resp, "download file")
    content_type = (getattr(resp, "headers", None) or {}).get("Content-Type") or "application/octet-stream"
    return resp.content, content_type


def download_file(file_ref: Any, dest_path: str, *, base_url: Optional[str] = None,
                  api_key: Optional[str] = None,
                  timeout: float = DOWNLOAD_TIMEOUT) -> str:
    """Download a delivered file to ``dest_path`` and return the path."""
    content, _ = fetch_file(file_ref, base_url=base_url, api_key=api_key, timeout=timeout)
    parent = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(parent, exist_ok=True)
    with open(dest_path, "wb") as fh:
        fh.write(content)
    return dest_path


def fetch_credits(*, base_url: Optional[str] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Plan / limit / used / remaining (useful when a 402 is reported)."""
    resp = _send("GET", "/api/me/credits", base_url=base_url, api_key=api_key,
                 retry_network=True, max_attempts=MAX_ATTEMPTS)
    if resp.status_code != 200:
        _raise_for_status(resp, "fetch credits")
    return _json(resp)
