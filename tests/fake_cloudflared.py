"""Stand-in for cloudflared in tests: logs a quick-tunnel URL and an edge connection,
then idles until killed.

FAKE_CLOUDFLARED_MODE: "ok" (default), "fail" (exit at once), "drop" (lose the
edge connection right after registering). FAKE_CLOUDFLARED_URL_DELAY: seconds to
wait before the URL appears.
"""
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
parser.add_argument("--http-host-header")
parser.add_argument("--no-tls-verify", action="store_true")
args = parser.parse_args()

log = open(args.logfile, "a", encoding="utf-8") if args.logfile else sys.stdout
print("INF Arguments:", " ".join(sys.argv[1:]), file=log, flush=True)
print(f"INF Requesting new quick Tunnel on trycloudflare.com... origin={args.url}", file=log, flush=True)
# cloudflared names the API host in error messages; it is not a tunnel URL.
print('ERR failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel": EOF', file=log, flush=True)
time.sleep(float(os.environ.get("FAKE_CLOUDFLARED_URL_DELAY", "0")))
print("INF |  https://fake-tunnel-test.trycloudflare.com  |", file=log, flush=True)
print("INF Registered tunnel connection connIndex=0 location=test01 protocol=http2", file=log, flush=True)
if os.environ.get("FAKE_CLOUDFLARED_MODE") == "drop":
    print('ERR Serve tunnel error error="connection reset by peer" connIndex=0', file=log, flush=True)
    print("INF Retrying connection in up to 1s connIndex=0", file=log, flush=True)
while True:
    time.sleep(1)
