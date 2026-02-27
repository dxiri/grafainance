#!/bin/bash
# Grafana initialization script
# Replaces API key placeholders in dashboard JSON files with actual values

set -e

DASHBOARD_DIR="/etc/grafana/provisioning/dashboards"

echo "Initializing Grafana dashboards with API keys..."

# Replace Twelve Data API key placeholder
if [ -n "$TWELVE_DATA_API_KEY" ]; then
    echo "Setting Twelve Data API key... (${#TWELVE_DATA_API_KEY} chars)"
    find "$DASHBOARD_DIR" -name "*.json" -exec sed -i 's/\${TWELVE_DATA_API_KEY}/'"$TWELVE_DATA_API_KEY"'/g' {} \;
else
    echo "WARNING: TWELVE_DATA_API_KEY is not set!"
fi

# Replace FRED API key placeholder
if [ -n "$FRED_API_KEY" ]; then
    echo "Setting FRED API key... (${#FRED_API_KEY} chars)"
    find "$DASHBOARD_DIR" -name "*.json" -exec sed -i 's/\${FRED_API_KEY}/'"$FRED_API_KEY"'/g' {} \;
else
    echo "WARNING: FRED_API_KEY is not set!"
fi

echo "Dashboard initialization complete."

# Execute the original Grafana entrypoint
exec /run.sh "$@"
