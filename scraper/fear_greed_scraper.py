#!/usr/bin/env python3
"""
Grafainance Fear & Greed Index Scraper

Fetches the CNN Fear & Greed Index and pushes it to InfluxDB.
Designed to run as a cron job every 4 hours.

Usage:
    python fear_greed_scraper.py

Environment Variables:
    INFLUX_URL      - InfluxDB URL (default: http://localhost:8086)
    INFLUX_TOKEN    - InfluxDB authentication token
    INFLUX_ORG      - InfluxDB organization (default: grafainance)
    INFLUX_BUCKET   - InfluxDB bucket (default: market_sentiment)
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('fear_greed_scraper')

# Maximum retries with exponential backoff
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5  # seconds

# CNN Fear & Greed endpoint
FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.cnn.com/markets/fear-and-greed"
}

# InfluxDB configuration from environment
INFLUX_URL = os.environ.get("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "grafainance")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "market_sentiment")


def get_fear_greed() -> Optional[Dict[str, Any]]:
    """
    Fetch the current Fear & Greed index from CNN with retry logic.
    
    Returns:
        Dictionary with score, rating, and timestamp, or None on error.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                FEAR_GREED_URL, 
                headers=HEADERS, 
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract current values
            fear_greed_data = data.get('fear_and_greed', {})
            
            result = {
                "score": float(fear_greed_data.get('score', 0)),
                "rating": fear_greed_data.get('rating', 'Unknown'),
                "timestamp": fear_greed_data.get('timestamp', datetime.utcnow().isoformat()),
                "previous_close": float(fear_greed_data.get('previous_close', 0)),
                "previous_1_week": float(fear_greed_data.get('previous_1_week', 0)),
                "previous_1_month": float(fear_greed_data.get('previous_1_month', 0)),
                "previous_1_year": float(fear_greed_data.get('previous_1_year', 0)),
            }
            
            logger.info(f"Fetched Fear & Greed: {result['score']} ({result['rating']})")
            return result
            
        except requests.Timeout:
            logger.warning(f"Request timed out (attempt {attempt}/{MAX_RETRIES})")
        except requests.RequestException as e:
            logger.warning(f"HTTP error (attempt {attempt}/{MAX_RETRIES}): {e}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing Fear & Greed response: {e}")
            return None  # Don't retry parse errors
        
        if attempt < MAX_RETRIES:
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.info(f"Retrying in {delay}s...")
            time.sleep(delay)
    
    logger.error(f"Failed after {MAX_RETRIES} attempts")
    return None


def push_to_influx(data: Dict[str, Any]) -> bool:
    """
    Push Fear & Greed data to InfluxDB.
    
    Args:
        data: Dictionary containing score, rating, and historical values.
        
    Returns:
        True on success, False on failure.
    """
    if not INFLUX_TOKEN:
        logger.error("INFLUX_TOKEN environment variable not set")
        return False
    
    try:
        with InfluxDBClient(
            url=INFLUX_URL, 
            token=INFLUX_TOKEN, 
            org=INFLUX_ORG
        ) as client:
            # Verify connection
            health = client.health()
            if health.status != "pass":
                logger.error(f"InfluxDB health check failed: {health.message}")
                return False
            
            write_api = client.write_api(write_options=SYNCHRONOUS)
            
            # Parse the CNN timestamp and truncate to the hour so that
            # repeated fetches of the same data produce the same point
            # (InfluxDB deduplicates on measurement + tag set + timestamp).
            try:
                ts = datetime.fromisoformat(
                    data["timestamp"].replace("Z", "+00:00")
                ).replace(minute=0, second=0, microsecond=0)
            except (ValueError, AttributeError):
                ts = datetime.now(timezone.utc).replace(
                    minute=0, second=0, microsecond=0
                )

            # Create data point with all fields
            # NOTE: 'rating' is a field (not a tag) so the same timestamp
            # always maps to one point regardless of rating text changes.
            point = Point("fear_greed") \
                .time(ts) \
                .field("score", data["score"]) \
                .field("rating", data["rating"]) \
                .field("previous_close", data["previous_close"]) \
                .field("previous_1_week", data["previous_1_week"]) \
                .field("previous_1_month", data["previous_1_month"]) \
                .field("previous_1_year", data["previous_1_year"])
            
            write_api.write(bucket=INFLUX_BUCKET, record=point)
            logger.info(f"Successfully pushed to InfluxDB: score={data['score']}")
            return True
            
    except Exception as e:
        logger.error(f"Error pushing to InfluxDB: {e}")
        return False


def main():
    """Main entry point."""
    logger.info("Starting Fear & Greed scraper")
    
    # Fetch data
    data = get_fear_greed()
    if not data:
        logger.error("Failed to fetch Fear & Greed data")
        sys.exit(1)
    
    # Log the data (useful for debugging)
    logger.info(f"Current data: {json.dumps(data, indent=2)}")
    
    # Push to InfluxDB
    if not push_to_influx(data):
        logger.error("Failed to push data to InfluxDB")
        sys.exit(1)
    
    logger.info("Scraper completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
