"""Open saved sessions in the originating SHUKI panel, using a live job capability."""

import argparse
import json
import os
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions", nargs="+", help="One to three exact saved-session UUIDs")
    args = parser.parse_args()
    job = os.environ.get("SHUKI_UI_JOB")
    token = os.environ.get("SHUKI_UI_TOKEN")
    if not job or not token:
        print(json.dumps({"status": "unavailable", "message":
                          "This worker has no panel capability. After dashboard activation, send a new request."}))
        return 1
    # Credentials are never accepted from CLI flags, printed, or sent off the local server.
    base = os.environ.get("SHUKI_UI_URL", "http://127.0.0.1:8765")
    if not base.startswith("http://127.0.0.1:") or not base.rsplit(":", 1)[-1].isdigit():
        print(json.dumps({"status": "unavailable", "message": "Invalid local dashboard address"}))
        return 1

    def request(**values):
        body = json.dumps({"job": job, "token": token, **values}).encode("utf-8")
        req = urllib.request.Request(base + "/sessions/open", body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)

    try:
        result = request(sessions=args.sessions)
        deadline = time.monotonic() + 15
        while result["status"] in ("queued", "pending") and time.monotonic() < deadline:
            time.sleep(0.3)
            result = request(command="status")
        if result["status"] in ("queued", "pending"):
            result = {"status": "pending", "message":
                      "Queued; the originating panel has not acknowledged opening. Keep that page open."}
    except urllib.error.HTTPError as error:
        result = {"status": "failed", "message": f"Dashboard returned HTTP {error.code}"}
        try:
            result["message"] = json.load(error).get("error", result["message"])
        except (ValueError, OSError):
            pass
    except (OSError, ValueError, KeyError) as error:
        result = {"status": "failed", "message": str(error)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "opened" else 1


if __name__ == "__main__":
    raise SystemExit(main())
