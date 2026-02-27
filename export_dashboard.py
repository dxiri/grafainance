#!/usr/bin/env python3
"""Export a live Grafana dashboard back to its provisioning JSON file, re-masking API keys."""
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
TWELVE_KEY = dotenv.get("TWELVE_DATA_API_KEY", "")
FRED_KEY = dotenv.get("FRED_API_KEY", "")

uid = sys.argv[1] if len(sys.argv) > 1 else "market-overview"
outpath = sys.argv[2] if len(sys.argv) > 2 else f"grafana/provisioning/dashboards/{uid}.json"

resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{uid}", auth=(USER, PASSWD), timeout=10)
resp.raise_for_status()
dash = resp.json()["dashboard"]

# Strip runtime fields
dash["id"] = None
dash["version"] = 1

raw = json.dumps(dash, indent=2)

# Re-mask API keys
if TWELVE_KEY:
    raw = raw.replace(TWELVE_KEY, "${TWELVE_DATA_API_KEY}")
if FRED_KEY:
    raw = raw.replace(FRED_KEY, "${FRED_API_KEY}")

with open(outpath, "w") as f:
    f.write(raw + "\n")

td_count = raw.count("${TWELVE_DATA_API_KEY}")
fred_count = raw.count("${FRED_API_KEY}")
print(f"Saved {outpath} ({len(raw)} bytes). Masked {td_count} TD keys, {fred_count} FRED keys.")
