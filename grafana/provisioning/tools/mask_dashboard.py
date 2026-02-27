#!/usr/bin/env python3
"""Write the user's exact dashboard JSON with API keys masked."""
import json, os, sys

def load_dotenv(path):
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
TD_KEY = dotenv.get("TWELVE_DATA_API_KEY", "")
FRED_KEY = dotenv.get("FRED_API_KEY", "")

infile = sys.argv[1]
outfile = sys.argv[2] if len(sys.argv) > 2 else infile

with open(infile) as f:
    raw = f.read()

if TD_KEY:
    raw = raw.replace(TD_KEY, "${TWELVE_DATA_API_KEY}")
if FRED_KEY:
    raw = raw.replace(FRED_KEY, "${FRED_API_KEY}")

# Parse to fix id/version for provisioning
dash = json.loads(raw)
dash["id"] = None
dash["version"] = 1

raw = json.dumps(dash, indent=2) + "\n"

with open(outfile, "w") as f:
    f.write(raw)

td_count = raw.count("${TWELVE_DATA_API_KEY}")
fred_count = raw.count("${FRED_API_KEY}")
print(f"Saved {outfile} ({len(raw)} bytes). Masked {td_count} TD keys, {fred_count} FRED keys.")
print(f"schemaVersion: {dash.get('schemaVersion')}, preload: {dash.get('preload')}")
