#!/usr/bin/env python3
"""
Grafainance LNG Price Scraper (JKM + TTF)

Fetches daily JKM (Asia) and TTF (Europe) natural gas benchmark prices
from lngpriceindex.com and pushes them to InfluxDB.

The source site is a static SPA that embeds daily benchmark data in its
main JavaScript bundle.  We:
  1. Download the homepage HTML.
  2. Locate the hashed main JS bundle URL.
  3. Download the bundle and parse the embedded 7-day chart data.
  4. Write one InfluxDB point per benchmark per day.

Prices are stored in USD/MMBtu (JKM is native; TTF is the site's own
USD/MMBtu equivalent of the €/MWh front-month).

Measurements written
--------------------
  jkm_price   field: price  (USD/MMBtu)
  ttf_price   field: price  (USD/MMBtu)

Designed to run every 4 hours alongside the other scrapers.

Usage:
    python lng_price_scraper.py

Environment Variables:
    INFLUX_URL      - InfluxDB URL (default: http://localhost:8086)
    INFLUX_TOKEN    - InfluxDB authentication token
    INFLUX_ORG      - InfluxDB organization (default: grafainance)
    INFLUX_BUCKET   - InfluxDB bucket (default: market_sentiment)
"""

import os
import re
import sys
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("lng_price_scraper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5  # seconds

SITE_URL = "https://lngpriceindex.com/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Regex to find the hashed main bundle in the HTML
# e.g. src="/assets/index-CQA6stea.js"
BUNDLE_RE = re.compile(r'src="(/assets/index-[A-Za-z0-9_-]+\.js)"')

# Regex to extract the 7-day chart data object from the JS bundle.
# The variable contains {"7D":[...],"30D":[...],...}
# We look for the pattern: ={"7D":[ ... ]}; and extract the full object.
CHART_DATA_RE = re.compile(
    r'=(\{"7D":\[.*?\],"30D":\[.*?\],"90D":\[.*?\],"1Y":\[.*?\]\})'
)

# Month abbreviation → number
MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# InfluxDB configuration
INFLUX_URL = os.environ.get("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "grafainance")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "market_sentiment")


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _get(url: str, **kwargs) -> Optional[requests.Response]:
    """GET with retries and exponential backoff."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.Timeout:
            logger.warning("Timeout for %s (attempt %d/%d)", url, attempt, MAX_RETRIES)
        except requests.RequestException as exc:
            logger.warning("HTTP error for %s (attempt %d/%d): %s", url, attempt, MAX_RETRIES, exc)
        if attempt < MAX_RETRIES:
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.info("Retrying in %ds...", delay)
            time.sleep(delay)
    logger.error("Failed to fetch %s after %d attempts", url, MAX_RETRIES)
    return None


def fetch_bundle_url() -> Optional[str]:
    """Fetch the homepage and return the absolute URL of the main JS bundle."""
    resp = _get(SITE_URL)
    if resp is None:
        return None
    match = BUNDLE_RE.search(resp.text)
    if not match:
        logger.error("Could not find main JS bundle URL in homepage HTML")
        return None
    bundle_path = match.group(1)
    bundle_url = f"https://lngpriceindex.com{bundle_path}"
    logger.info("Found JS bundle: %s", bundle_url)
    return bundle_url


def fetch_chart_data(bundle_url: str) -> Optional[List[dict]]:
    """
    Download the JS bundle and extract the 7-day chart data array.

    Returns a list of dicts like:
        [{"date": "Mar 20", "JKM": 22.35, "TTF": 18.85, "HH": 3.11}, ...]
    """
    resp = _get(bundle_url)
    if resp is None:
        return None

    js_text = resp.text
    match = CHART_DATA_RE.search(js_text)
    if not match:
        logger.error("Could not locate chart data object in JS bundle")
        return None

    raw = match.group(1)
    # JS object keys are unquoted identifiers – add quotes to make valid JSON
    json_str = re.sub(r"(?<=[{,])(\w+):", r'"\1":', raw)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse chart data JSON: %s", exc)
        return None

    entries = data.get("7D", [])
    logger.info("Parsed 7D chart data: %d entries", len(entries))
    return entries


# ---------------------------------------------------------------------------
# Date resolution
# ---------------------------------------------------------------------------

def resolve_dates(entries: List[dict]) -> List[Tuple[datetime, dict]]:
    """
    Convert short date labels ("Mar 20") into full UTC datetime objects.

    Uses today's date as the anchor: the most recent entry is assumed to be
    today or very recent.  We walk backwards and handle month/year boundaries.

    Returns list of (datetime_utc, entry) tuples.
    """
    today = datetime.now(timezone.utc).date()
    result: List[Tuple[datetime, dict]] = []

    for entry in reversed(entries):
        label = entry.get("date", "")
        parts = label.split()
        if len(parts) != 2:
            logger.warning("Skipping entry with unexpected date format: %s", label)
            continue
        month_abbr, day_str = parts
        month = MONTH_MAP.get(month_abbr)
        if month is None:
            logger.warning("Unknown month abbreviation: %s", month_abbr)
            continue
        day = int(day_str)

        # Determine year: if the month-day is in the future relative to
        # today, it must belong to the previous year.
        year = today.year
        try:
            candidate = datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Invalid date: %s %d %d", month_abbr, day, year)
            continue
        if candidate.date() > today:
            year -= 1
            candidate = datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)

        result.append((candidate, entry))

    # Return in chronological order
    result.reverse()
    return result


# ---------------------------------------------------------------------------
# InfluxDB points
# ---------------------------------------------------------------------------

def build_points(dated_entries: List[Tuple[datetime, dict]]) -> List[Point]:
    """
    Build InfluxDB Point objects for JKM and TTF from the dated chart entries.

    Timestamps are pinned to 12:00 UTC (same dedup strategy as AECO scraper).
    """
    points: List[Point] = []

    for ts, entry in dated_entries:
        jkm = entry.get("JKM")
        ttf = entry.get("TTF")

        if jkm is not None:
            points.append(
                Point("jkm_price")
                .time(ts)
                .field("price", float(jkm))
            )

        if ttf is not None:
            points.append(
                Point("ttf_price")
                .time(ts)
                .field("price", float(ttf))
            )

    return points


def push_to_influx(points: List[Point]) -> bool:
    """Write points to InfluxDB."""
    if not INFLUX_TOKEN:
        logger.error("INFLUX_TOKEN environment variable not set")
        return False

    if not points:
        logger.info("No points to write")
        return True

    try:
        with InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG,
        ) as client:
            health = client.health()
            if health.status != "pass":
                logger.error("InfluxDB health check failed: %s", health.message)
                return False

            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, record=points)
            logger.info("Successfully pushed %d LNG price points to InfluxDB", len(points))
            return True

    except Exception as exc:
        logger.error("Error pushing to InfluxDB: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("Starting LNG price scraper (JKM + TTF)")

    # 1. Discover the JS bundle URL
    bundle_url = fetch_bundle_url()
    if bundle_url is None:
        logger.error("Could not discover JS bundle URL")
        sys.exit(1)

    # 2. Download and parse the 7-day chart data
    entries = fetch_chart_data(bundle_url)
    if not entries:
        logger.error("No chart data extracted from bundle")
        sys.exit(1)

    # 3. Resolve short date labels to full timestamps
    dated = resolve_dates(entries)
    if not dated:
        logger.error("Could not resolve any dates from chart data")
        sys.exit(1)

    logger.info("Resolved %d dated entries:", len(dated))
    for ts, e in dated:
        logger.info("  %s  JKM=%.2f  TTF=%.2f", ts.strftime("%Y-%m-%d"), e["JKM"], e["TTF"])

    # 4. Build InfluxDB points
    points = build_points(dated)
    logger.info("Built %d InfluxDB points (JKM + TTF)", len(points))

    # 5. Push to InfluxDB
    if not push_to_influx(points):
        logger.error("Failed to push data to InfluxDB")
        sys.exit(1)

    logger.info("LNG price scraper completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
