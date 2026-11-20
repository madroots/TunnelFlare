"""Stand-in for cloudflared in tests: logs a quick-tunnel URL, then idles until killed."""
import os
import sys

if os.environ.get("FAKE_CLOUDFLARED_MODE") == "fail":
    # Exit as fast as possible so the app's 1 s startup check sees the failure.
    sys.stderr.write("ERR failed to dial to edge: forbidden by its access permissions\n")
    sys.exit(1)

import argparse  # noqa: E402
import time  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("command")
parser.add_argument("--no-autoupdate", action="store_true")
parser.add_argument("--url", required=True)
parser.add_argument("--logfile")
parser.add_argument("--protocol")
parser.add_argument("--edge-ip-version")
args = parser.parse_args()

log = open(args.logfile, "a", encoding="utf-8") if args.logfile else sys.stdout
print(f"INF Requesting new quick Tunnel on trycloudflare.com... origin={args.url}", file=log, flush=True)
# cloudflared names the API host in error messages; it is not a tunnel URL.
print('ERR failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel": EOF', file=log, flush=True)
time.sleep(float(os.environ.get("FAKE_CLOUDFLARED_URL_DELAY", "0")))
print("INF |  https://fake-tunnel-test.trycloudflare.com  |", file=log, flush=True)
while True:
    time.sleep(1)
