#!/usr/bin/env python3
"""Export a live Grafana dashboard back to its provisioning JSON file.

Since API keys are now handled by the api-proxy sidecar (not embedded in
dashboard URLs), this script only needs to reset id/version for clean provisioning.
"""
import sys, json, os, requests

GRAFANA_URL = "http://localhost:3000"

# Read .env file directly since shell `source` doesn't export to Python
def load_dotenv(path=".env"):
    env = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("'\"")
    return env

dotenv = load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

USER = dotenv.get("GF_SECURITY_ADMIN_USER", "admin")
PASSWD = dotenv.get("GF_SECURITY_ADMIN_PASSWORD", "admin")

uid = sys.argv[1] if len(sys.argv) > 1 else "market-overview"
outpath = sys.argv[2] if len(sys.argv) > 2 else f"grafana/provisioning/dashboards/{uid}.json"

resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{uid}", auth=(USER, PASSWD), timeout=10)
resp.raise_for_status()
dash = resp.json()["dashboard"]

# Strip runtime fields
dash["id"] = None
dash["version"] = 1

raw = json.dumps(dash, indent=2)

# Safety check: ensure no real API keys leaked into the exported JSON
TWELVE_KEY = dotenv.get("TWELVE_DATA_API_KEY", "")
FRED_KEY = dotenv.get("FRED_API_KEY", "")
if TWELVE_KEY and TWELVE_KEY in raw:
    print(f"ERROR: Twelve Data API key found in dashboard JSON! Aborting.", file=sys.stderr)
    sys.exit(1)
if FRED_KEY and FRED_KEY in raw:
    print(f"ERROR: FRED API key found in dashboard JSON! Aborting.", file=sys.stderr)
    sys.exit(1)

with open(outpath, "w") as f:
    f.write(raw + "\n")

print(f"Saved {outpath} ({len(raw)} bytes). No API keys present in output.")
