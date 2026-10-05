"""Run one live Sieve scrape from the CLI.

Usage (from backend/):

    python scripts/sieve_scrape.py \
        --instruction "Extract the text and author of each quote" \
        --url https://quotes.toscrape.com

This spends credits. It uses the same service module the API endpoints use
(app.services.sieve), so it exercises the real retry / status / persistence
logic. The session id is printed and also persisted under
settings.SIEVE_STATE_DIR, so an aborted run can be resumed by polling instead
of being started (and charged) again.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import sieve  # noqa: E402
from app.services.sieve import SieveError  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Start one Sieve scrape and poll it to completion.")
    parser.add_argument("--instruction", required=True, help="Plain-language instruction for the run.")
    parser.add_argument("--url", action="append", default=[], help="Public http(s) target page (repeatable).")
    parser.add_argument("--fields", default="", help="Comma-separated expected columns.")
    parser.add_argument("--output-schema", default="", help="Path to a JSON Schema (2020-12) file.")
    parser.add_argument("--table-shape", default="", choices=["", "long", "wide"])
    parser.add_argument("--compliance-mode", default="", choices=["", "conservative", "regular", "yolo"])
    parser.add_argument("--followup", default="", help="Extra instruction to send as a follow-up turn.")
    parser.add_argument("--download-dir", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads", "sieve"))
    parser.add_argument("--max-seconds", type=float, default=1800.0)
    return parser.parse_args(argv)


def _status_cb(started):
    def cb(run):
        elapsed = int(time.monotonic() - started)
        print(f"  [{elapsed:>4}s] status={run.get('status')} turns={run.get('turns')}")
    return cb


def main(argv=None):
    args = _parse_args(argv)

    if not sieve.is_configured():
        print("SIEVE_API_KEY is not set. Run: python scripts/sieve_device_login.py")
        return 2

    output_schema = None
    if args.output_schema:
        with open(args.output_schema, "r", encoding="utf-8") as fh:
            output_schema = json.load(fh)

    fields = [f.strip() for f in args.fields.split(",") if f.strip()] or None

    print("Starting Sieve run (this spends credits)...")
    try:
        record = sieve.start_scrape(
            args.instruction,
            target_urls=args.url or None,
            fields=fields,
            output_schema=output_schema,
            table_shape=args.table_shape or None,
            compliance_mode=args.compliance_mode or None,
        )
    except SieveError as exc:
        print(f"Start failed [{exc.kind}]: {exc}")
        return 1

    session_id = record["session_id"]
    print(f"Accepted. session_id={session_id} status={record.get('status')}")

    started = time.monotonic()
    try:
        run = sieve.wait_for_run(session_id, max_seconds=args.max_seconds, on_status=_status_cb(started))
    except SieveError as exc:
        print(f"Polling failed [{exc.kind}]: {exc}")
        print(f"Resume by polling session {session_id}; do NOT start a new run.")
        return 1

    if run["status"] == "refused":
        print(f"Run refused (terminal). code={run.get('code')} refusal={json.dumps(run.get('refusal'))}")
        return 2

    print("Done.")
    print(f"  summary: {run.get('summary')}")
    print(f"  schema_conformance: {json.dumps(run.get('schema_conformance'))}")
    print(f"  clean: {sieve.result_is_clean(run)}")
    if run.get("result") is not None:
        print(f"  result: {json.dumps(run.get('result'))[:2000]}")

    files = run.get("files") or []
    if files:
        os.makedirs(args.download_dir, exist_ok=True)
        for entry in files:
            dest = os.path.join(args.download_dir, os.path.basename(entry.get("name") or "file"))
            try:
                sieve.download_file(entry, dest)
                print(f"  downloaded {entry.get('name')} ({entry.get('size')} bytes) -> {dest}")
            except SieveError as exc:
                print(f"  download failed for {entry.get('name')} [{exc.kind}]: {exc}")
    else:
        print("  no files delivered")

    if args.followup:
        print("Sending follow-up turn...")
        try:
            follow = sieve.send_followup(session_id, instruction=args.followup)
        except SieveError as exc:
            print(f"Follow-up failed [{exc.kind}]: {exc}")
            return 1
        if follow["status"] == "in_flight":
            print("A turn is already in flight (409); re-run shortly to resend.")
            return 1
        print(f"Turn accepted (baseline turns={follow['previous_turns']}); polling for the new answer...")
        try:
            run = sieve.wait_for_turn(
                session_id, follow["previous_turns"], max_seconds=args.max_seconds,
                on_status=_status_cb(started),
            )
        except SieveError as exc:
            print(f"Follow-up polling failed [{exc.kind}]: {exc}")
            return 1
        print(f"  follow-up status: {run.get('status')}")
        print(f"  summary: {run.get('summary')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
