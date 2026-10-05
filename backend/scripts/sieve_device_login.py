"""Device login for the Sieve scrape API - run once, with the user present.

Usage (from backend/):

    python scripts/sieve_device_login.py

The script asks Sieve for a device code, prints the verification link and the
short user code, then polls until the user approves it in their browser. The
returned key is written straight into the secret store (``backend/.env`` as
``SIEVE_API_KEY``) and is never printed, logged or echoed.

Anti-phishing posture (this is the whole point of the device flow):

* The link is never opened for the user - they open it themselves.
* The approval page shows where the code was requested from next to the
  approver's own location, and labels the tool name as self-reported.
* Anyone can start a device code, so the user must confirm the code matches
  and approve ONLY a code they started themselves.
* Approval always needs an explicit click; codes expire in 10 minutes and
  work exactly once.

Options:
    --base-url URL     Override the Sieve base URL.
    --client-name NAME Tool name shown on the approval page (self-reported).
    --env-file PATH    Where to write the key (default: backend/.env).
    --force            Overwrite an existing SIEVE_API_KEY in the env file.
"""
import argparse
import os
import sys
import time

import requests

DEFAULT_BASE_URL = "https://scrape.usesieve.com"
DEFAULT_CLIENT_NAME = "DeepGuard forensic backend"
ENV_KEY = "SIEVE_API_KEY"


def _post(url, payload, timeout=30):
    """POST JSON and return (status, parsed_body) - 4xx/5xx included."""
    resp = requests.post(url, json=payload, timeout=timeout,
                         headers={"Accept": "application/json"})
    try:
        parsed = resp.json() or {}
    except ValueError:
        parsed = {"error": (resp.text or "").strip()}
    return resp.status_code, parsed


def _request_device_code(base_url, client_name):
    status, payload = _post(f"{base_url}/api/auth/device/code", {"client_name": client_name})
    if status != 200:
        raise SystemExit(f"Sieve refused the device-code request (HTTP {status}): {payload.get('error', payload)}")
    for field in ("device_code", "user_code", "verification_uri"):
        if not payload.get(field):
            raise SystemExit(f"Sieve device-code response is missing '{field}'.")
    return payload


def _poll_for_key(base_url, device_code, interval, expires_in):
    """Poll until the user approves, the code dies, or they decline."""
    deadline = time.monotonic() + max(30, int(expires_in or 600))
    wait = max(1, int(interval or 5))
    while time.monotonic() < deadline:
        status, payload = _post(f"{base_url}/api/auth/device/token", {"device_code": device_code})
        if status == 200:
            key = payload.get("api_key")
            if not key:
                raise SystemExit("Sieve returned 200 without an api_key.")
            return key
        if status != 400:
            raise SystemExit(f"Device-token poll failed (HTTP {status}): {payload.get('error', payload)}")
        error = str(payload.get("error", ""))
        if error == "authorization_pending":
            time.sleep(wait)
            continue
        if error == "slow_down":
            wait += 5
            time.sleep(wait)
            continue
        if error == "access_denied":
            raise SystemExit("The approval was declined in the browser. Nothing was stored; re-run when ready.")
        if error == "expired_token":
            return None
        raise SystemExit(f"Unexpected device-token error: {error or payload}")
    return None


def _upsert_env(path, key, value):
    """Write KEY=value into the env file without touching other entries."""
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    out, replaced = [], False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    os.replace(tmp, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Approve a Sieve device login and store SIEVE_API_KEY.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--client-name", default=DEFAULT_CLIENT_NAME)
    parser.add_argument("--env-file", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    parser.add_argument("--force", action="store_true", help="Overwrite an existing key in the env file.")
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")

    if os.environ.get(ENV_KEY) and not args.force:
        print(f"{ENV_KEY} is already set in the environment; nothing to do.")
        return 0
    if os.path.exists(args.env_file):
        with open(args.env_file, "r", encoding="utf-8") as fh:
            if any(line.strip().startswith(f"{ENV_KEY}=") for line in fh) and not args.force:
                print(f"{ENV_KEY} already exists in {args.env_file}; re-run with --force to replace it.")
                return 0

    while True:
        code = _request_device_code(base_url, args.client_name)
        print("")
        print("Open this link in your browser and approve the request:")
        print(f"  {code.get('verification_uri_complete') or code['verification_uri']}")
        print(f"  user code: {code['user_code']}")
        print("")
        print("Checklist before you click Approve:")
        print("  - Open the link yourself; nobody should send you one to approve.")
        print("  - Confirm the code above matches the one shown on the page.")
        print("  - Approve ONLY a login you started yourself.")
        print("  - The tool name on the page is self-reported, not verified.")
        print("  - The code expires in 10 minutes and works once.")
        print("")
        print("Waiting for approval (Ctrl+C to abort)...")
        sys.stdout.flush()

        key = _poll_for_key(base_url, code["device_code"], code.get("interval", 5), code.get("expires_in", 600))
        if key is None:
            print("The code expired before approval. Requesting a new one...")
            continue
        break

    _upsert_env(args.env_file, ENV_KEY, key)
    print(f"Approved. {ENV_KEY} was written to {args.env_file} (value not shown).")
    print("Restart the backend so the new setting is loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
