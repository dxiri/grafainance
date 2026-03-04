#!/bin/bash
# Grafana initialization script
# API keys are now injected by the api-proxy service, not embedded in dashboards.

set -e

echo "Grafana initializing... (API keys handled by api-proxy sidecar)"

# Execute the original Grafana entrypoint
exec /run.sh "$@"
