#!/usr/bin/env python3
# /opt/hermes/supervisord/scripts/dependency_listener.py

import sys
import subprocess
import time
from supervisor.childutils import listener

# ── Dependency graph ──────────────────────────────────────────────────────────
#
# CRITICAL: upstream down → stop dependents
#           upstream up   → start dependents
#           enforced at runtime, not just boot
#
# SOFT:     upstream must be RUNNING before dependents start on boot
#           mid-session restarts of upstream are ignored
#
CRITICAL = {
    "gluetun": {
        "deps": ["pyload"],
	    "start_delay": 10,
        },
}

SOFT = {
    # "prowlarr": ["sonarr", "radarr"],  # uncomment when arr stack is added
}

# ─────────────────────────────────────────────────────────────────────────────

DOWN_EVENTS = {
    "PROCESS_STATE_STOPPED",
    "PROCESS_STATE_FATAL",
    "PROCESS_STATE_EXITED",
}

def supervisorctl(*args):
    subprocess.run(["supervisorctl", *args], check=False)

def parse_payload(payload):
    return dict(kv.split(":") for kv in payload.split())

def main():
    while True:
        headers, payload = listener.wait(sys.stdin, sys.stdout)
        eventname = headers.get("eventname", "")
        fields    = parse_payload(payload)
        process   = fields.get("processname", "")


        print(f"[debug] event={eventname} process={process} payload={payload}", file=sys.stderr)

        if eventname == "PROCESS_STATE_RUNNING":
            if process in CRITICAL:
                delay = CRITICAL[process].get("start_delay", 0)
                deps = CRITICAL[process]["deps"]
                if delay:
                    print(f"[dep:critical] {process} RUNNING — waiting {delay}s before starting {deps}", file=sys.stderr)
                    time.sleep(delay)
                for dep in deps:
                    supervisorctl("start", dep)

            if process in SOFT:
                print(f"[dep:soft] {process} RUNNING — starting {SOFT[process]}", file=sys.stderr)
                for dep in SOFT[process]:
                    supervisorctl("start", dep)

        elif eventname in DOWN_EVENTS:
            if process in CRITICAL:
                deps = CRITICAL[process]["deps"]
                print(f"[dep:critical] {process} {eventname} — stopping {CRITICAL[process]}", file=sys.stderr)
                for dep in CRITICAL[process]:
                    time.sleep(2)
                    supervisorctl("stop", dep)

        listener.ok(sys.stdout)

if __name__ == "__main__":
    main()
