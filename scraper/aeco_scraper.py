#!/usr/bin/env python3
"""
Grafainance AECO Natural Gas Price Scraper

Fetches AECO (Alberta) daily natural gas prices from the Gas Alberta
JSON API and pushes them to InfluxDB.

The source is: https://www.gasalberta.com/gas-market/market-prices
which exposes a JSON API at /actions/charts/default?id=<chart_type>.

Data format per month: [[day, monthly_index, daily_price], ...]
  - day:           Day of the month (1-31)
  - monthly_index: Monthly reference price (CAD/GJ), constant for the month
  - daily_price:   Daily spot price (CAD/GJ), null for future days

Designed to run as a cron job every 4 hours (same schedule as Fear & Greed).

Usage:
    python aeco_scraper.py

Environment Variables:
    INFLUX_URL      - InfluxDB URL (default: http://localhost:8086)
    INFLUX_TOKEN    - InfluxDB authentication token
    INFLUX_ORG      - InfluxDB organization (default: grafainance)
    INFLUX_BUCKET   - InfluxDB bucket (default: market_sentiment)
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from calendar import monthrange

import requests
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('aeco_scraper')

# Maximum retries with exponential backoff
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5  # seconds

# Gas Alberta API endpoints
BASE_URL = "https://www.gasalberta.com/actions/charts/default"
CURRENT_MONTH_ID = "aeco_ng_current"
PRIOR_MONTH_ID = "aeco_ng_prior"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# InfluxDB configuration from environment
INFLUX_URL = os.environ.get("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "grafainance")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "market_sentiment")


def fetch_month_data(chart_id: str) -> Optional[list]:
    """
    Fetch a month of AECO data from Gas Alberta's JSON API with retry logic.

    Args:
        chart_id: Either 'aeco_ng_current' or 'aeco_ng_prior'.

    Returns:
        List of [day, monthly_index, daily_price] arrays, or None on error.
    """
    url = f"{BASE_URL}?id={chart_id}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", [])
            logger.info(f"Fetched {chart_id}: {len(data)} rows")
            return data

        except requests.Timeout:
            logger.warning(f"Request timed out for {chart_id} (attempt {attempt}/{MAX_RETRIES})")
        except requests.RequestException as e:
            logger.warning(f"HTTP error for {chart_id} (attempt {attempt}/{MAX_RETRIES}): {e}")
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing {chart_id} response: {e}")
            return None  # Don't retry parse errors

        if attempt < MAX_RETRIES:
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.info(f"Retrying in {delay}s...")
            time.sleep(delay)

    logger.error(f"Failed to fetch {chart_id} after {MAX_RETRIES} attempts")
    return None


def determine_months() -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """
    Determine which year/month the 'current' and 'prior' data correspond to.

    Returns:
        ((current_year, current_month), (prior_year, prior_month))
    """
    now = datetime.now(timezone.utc)
    current_year, current_month = now.year, now.month

    # Prior month
    if current_month == 1:
        prior_year, prior_month = current_year - 1, 12
    else:
        prior_year, prior_month = current_year, current_month - 1

    return (current_year, current_month), (prior_year, prior_month)


def rows_to_points(
    rows: list,
    year: int,
    month: int,
) -> List[Point]:
    """
    Convert raw Gas Alberta rows to InfluxDB Point objects.

    Each row is [day_of_month, monthly_index, daily_price].
    Rows with null daily_price (future days) are skipped.

    Timestamps are pinned to 12:00 UTC on the given date so that
    repeated scrapes of the same day produce the same point
    (InfluxDB deduplicates on measurement + tag set + timestamp).

    Args:
        rows:  List of [day, monthly_index, daily_price].
        year:  Calendar year for this data set.
        month: Calendar month for this data set.

    Returns:
        List of InfluxDB Point objects.
    """
    points: List[Point] = []
    max_day = monthrange(year, month)[1]

    for row in rows:
        day = int(row[0])
        monthly_index = row[1]
        daily_price = row[2]

        if daily_price is None:
            continue  # Future day, no data yet

        if day < 1 or day > max_day:
            logger.warning(f"Skipping invalid day {day} for {year}-{month:02d}")
            continue

        ts = datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)

        point = (
            Point("aeco_price")
            .time(ts)
            .field("daily_price", float(daily_price))
            .field("monthly_index", float(monthly_index))
        )
        points.append(point)

    return points


def push_to_influx(points: List[Point]) -> bool:
    """
    Write AECO price points to InfluxDB.

    Args:
        points: List of InfluxDB Point objects.

    Returns:
        True on success, False on failure.
    """
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
                logger.error(f"InfluxDB health check failed: {health.message}")
                return False

            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, record=points)
            logger.info(f"Successfully pushed {len(points)} AECO points to InfluxDB")
            return True

    except Exception as e:
        logger.error(f"Error pushing to InfluxDB: {e}")
        return False


def main():
    """Main entry point."""
    logger.info("Starting AECO price scraper")

    (cur_year, cur_month), (prior_year, prior_month) = determine_months()
    logger.info(
        f"Current month: {cur_year}-{cur_month:02d}, "
        f"Prior month: {prior_year}-{prior_month:02d}"
    )

    all_points: List[Point] = []

    # Fetch current month
    current_data = fetch_month_data(CURRENT_MONTH_ID)
    if current_data is not None:
        pts = rows_to_points(current_data, cur_year, cur_month)
        logger.info(f"Current month: {len(pts)} data points")
        all_points.extend(pts)
    else:
        logger.warning("Could not fetch current month data")

    # Fetch prior month
    prior_data = fetch_month_data(PRIOR_MONTH_ID)
    if prior_data is not None:
        pts = rows_to_points(prior_data, prior_year, prior_month)
        logger.info(f"Prior month: {len(pts)} data points")
        all_points.extend(pts)
    else:
        logger.warning("Could not fetch prior month data")

    if not all_points:
        logger.error("No data points collected from either month")
        sys.exit(1)

    logger.info(f"Total points to write: {len(all_points)}")

    if not push_to_influx(all_points):
        logger.error("Failed to push data to InfluxDB")
        sys.exit(1)

    logger.info("AECO scraper completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
