#!/usr/bin/env python3
"""
Lightweight API proxy that injects API keys server-side.

Grafana's Infinity plugin sends requests to this proxy (inside the Docker network).
The proxy appends the real API key before forwarding to the upstream API,
so keys never appear in Grafana's frontend, browser devtools, or dashboard JSON.

Routes:
  /twelvedata/*  →  https://api.twelvedata.com/*   + apikey=<TD_KEY>
  /fred/*        →  https://api.stlouisfed.org/*    + api_key=<FRED_KEY>
  /health        →  200 OK
"""

import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qs
from urllib.error import URLError, HTTPError

TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
FRED_KEY = os.environ.get("FRED_API_KEY", "")
PORT = int(os.environ.get("PROXY_PORT", "8080"))

ROUTES = {
    "/twelvedata/": {
        "upstream": "https://api.twelvedata.com/",
        "param_name": "apikey",
        "key": TWELVE_DATA_KEY,
    },
    "/fred/": {
        "upstream": "https://api.stlouisfed.org/",
        "param_name": "api_key",
        "key": FRED_KEY,
    },
}


class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Health check
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        # Find matching route
        for prefix, cfg in ROUTES.items():
            if self.path.startswith(prefix):
                return self._proxy(prefix, cfg)

        self.send_error(404, "Unknown route")

    def _proxy(self, prefix, cfg):
        # Build upstream URL
        remainder = self.path[len(prefix):]
        upstream_url = cfg["upstream"] + remainder

        # Parse and inject API key
        parts = urlsplit(upstream_url)
        qs = parse_qs(parts.query, keep_blank_values=True)

        # Remove any client-supplied API key (prevent abuse)
        qs.pop(cfg["param_name"], None)
        qs[cfg["param_name"]] = [cfg["key"]]

        new_query = urlencode(qs, doseq=True)
        upstream_url = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, ""))

        try:
            req = Request(upstream_url, headers={"User-Agent": "Grafainance-Proxy/1.0"})
            with urlopen(req, timeout=30) as resp:
                body = resp.read()
                self.send_response(resp.status)
                # Forward content headers
                for h in ("Content-Type", "Content-Encoding"):
                    val = resp.getheader(h)
                    if val:
                        self.send_header(h, val)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (URLError, TimeoutError) as e:
            self.send_error(502, f"Upstream error: {e}")

    def log_message(self, fmt, *args):
        # Redact API keys from access logs
        msg = fmt % args
        for cfg in ROUTES.values():
            if cfg["key"]:
                msg = msg.replace(cfg["key"], "***")
        sys.stderr.write(f"[proxy] {self.address_string()} {msg}\n")


if __name__ == "__main__":
    if not TWELVE_DATA_KEY:
        print("WARNING: TWELVE_DATA_API_KEY not set", file=sys.stderr)
    if not FRED_KEY:
        print("WARNING: FRED_API_KEY not set", file=sys.stderr)

    server = HTTPServer(("0.0.0.0", PORT), ProxyHandler)
    print(f"API proxy listening on :{PORT}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
