# **Product Requirements Document: Financial Market Intelligence Dashboards**

## **1\. Executive Summary**

The goal of this project is to build a centralized, real-time financial monitoring suite in Grafana. These dashboards will provide a holistic view of global market health, currency strength, and crypto asset performance for retail traders and market analysts. By consolidating data from **Twelve Data**, **FRED (Federal Reserve Economic Data)**, and custom sentiment indicators, we will replace disparate browser tabs with a single pane of glass.

## **2\. User Personas**

* **The Macro Analyst:** Monitors global bond yields and volatility to predict broad market moves. Needs to see the yield curve spread (2Y vs 10Y) and VIX at a glance.  
* **The Crypto/Forex Trader:** Tracks specific currency pairs (USD/JPY, GBP/USD) and major crypto assets (BTC, ETH) for arbitrage or swing trading opportunities. Needs low-latency candlestick charts.  
* **The Global Investor:** balanced exposure to US (S\&P 500), Japan (Nikkei), and Emerging Markets (China/World). Needs performance comparisons normalized to a common baseline.

## **2.1 Success Metrics**

| Metric | Target | Measurement Method |
| :---- | :---- | :---- |
| Dashboard Load Time | < 3 seconds | Grafana performance monitoring |
| Data Freshness SLA | 99% within expected refresh interval | Alerting on stale data |
| API Uptime | 99.5% availability | External monitoring (UptimeRobot) |
| User Adoption | 3 active daily users within 30 days | Grafana usage analytics |
| Alert Response Time | < 15 minutes for critical alerts | Alert acknowledgment tracking |

## **3\. Functional Requirements & Dashboards**

### **Dashboard 1: Market Overview & Sentiment ("The Cockpit")**

* **Goal:** Instant read on "Risk On" vs. "Risk Off".  
* **Panels:**  
  * **Fear & Greed Index:** Gauge chart (0-100).  
    * *Source:* Custom Python Scraper (see Technical Architecture).  
  * **CBOE Volatility Index (VIX):** Time series line chart.  
    * *Source:* FRED (Series: VIXCLS) or Twelve Data (VIX).  
  * **Major Indexes Summary:** Sparklines with % change for SP500, Nikkei 225, MSCI World (ETF Proxy), MSCI China (ETF Proxy).  
    * *Source:* Twelve Data.

### **Dashboard 2: Forex & Crypto Monitor**

* **Goal:** Asset price tracking with technical view.  
* **Panels:**  
  * **Currency Grid:** 2x3 grid of Candlestick charts (15m or 1h interval).  
    * Pairs: EUR/USD, GBP/USD, USD/JPY, USD/CAD, USD/CRC.  
  * **Crypto Trio:** Multi-series line chart or separate candlesticks for BTC/USD, ETH/USD, XMR/USD.  
  * **Costa Rica Focus:** Specific single stat panel for USD/CRC exchange rate.

### **Dashboard 3: Macro & Yield Curves**

* **Goal:** Interest rate and bond market analysis.  
* **Panels:**  
  * **US Treasury Yield Curve:** Multi-series time chart showing 2Y (DGS2), 10Y (DGS10), and 30Y (DGS30) yields.  
    * *Visualization:* Time Series (historical spread).
  * **Japan Government Bonds Yield Curve:** Multi-series time chart showing 2Y, 10Y, and 30Y yields for JGBs.
  * **German Government Bonds Yield Curve:** Multi-series time chart showing 2Y, 10Y, and 30Y yields for German Bunds.  
  * **Global 10Y Benchmark:** Line chart comparing US 10Y, German Bund 10Y, and Japan JGB 10Y.  
    * *Source:* FRED (Data Series: IRLTLT01DEQ156N for Germany, IRLTLT01JPM156N for Japan — note: monthly frequency).

## **3.1 Acceptance Criteria**

| Dashboard | Criterion | Test Method |
| :---- | :---- | :---- |
| Market Overview | VIX panel updates within 5 minutes of FRED publish | Compare panel timestamp vs FRED API |
| Market Overview | Fear & Greed gauge displays value 0-100 with color coding | Visual inspection |
| Forex & Crypto | Candlestick charts render OHLC data correctly | Compare sample candle vs source data |
| Forex & Crypto | USD/CRC single stat updates within refresh interval | Timestamp validation |
| Macro & Yields | All 3 yield curves display synchronized time ranges | Time range selector test |
| Macro & Yields | Spread calculation (10Y - 2Y) matches manual calculation | Spot check 5 random dates |
| All Dashboards | "Stale Data" indicator appears if update > 2× expected interval | Disconnect API and verify |
| All Dashboards | Graceful degradation on API timeout (no blank panels) | Simulate timeout |
| **US Bond Yields** | **FRED** | JSON API | Best source for official Treasury constant maturity rates. |
| **Global Yields** | **FRED** | JSON API | Aggregates OECD data for Germany/Japan 10Y bonds. |
| **VIX** | **FRED** | JSON API | Series VIXCLS is reliable and free. |
| **Fear & Greed** | **Custom Script** | InfluxDB/Push | No public API. Requires Python scraping script. |

### **4.1 Rate Limit Budget**

Twelve Data free tier limits:
- **8 API credits per minute**
- **8 WebSocket credits**
- **800 API credits per day**

| Dashboard | API Calls | Refresh Rate | Daily Requests |
| :---- | :---- | :---- | :---- |
| **Market Overview** | 8 panels | 1 hour | 8 × 24 = 192 |
| **Forex & Crypto** | 8 panels | 1 hour | 8 × 24 = 192 |
| | | **Total** | **384 requests/day** |

✅ **Within free tier limits** — 52% buffer (416 requests) available for manual refreshes or adding symbols.

**Important**: Each dashboard makes exactly 8 API calls per refresh, matching the 8 credits/minute limit. Avoid manually refreshing both dashboards simultaneously.

### **4.2 Fallback Data Sources**

| Primary Source | Fallback | Trigger |
| :---- | :---- | :---- |
| Twelve Data | Yahoo Finance (yfinance) | 3 consecutive failures |
| FRED | Cached last-known-good value | API timeout > 30s |
| Fear & Greed Scraper | Static "N/A" with timestamp | Scraper error |

### **4.3 Data Retention Policy**

| Data Type | Retention | Storage |
| :---- | :---- | :---- |
| Fear & Greed (InfluxDB) | 1 year | ~50 MB |
| Cached API responses | 24 hours | Grafana Infinity cache |
| Historical yields | Sourced on-demand | No local storage |

## **5\. Technical Architecture**

### **5.1 Grafana Configuration**

* **Datasource Plugin:** **Infinity Datasource** (Essential for connecting to Twelve Data/FRED API endpoints).  
* **Database (Optional):** **InfluxDB** is recommended if you want to store the Fear & Greed index history, as the scraper runs periodically.

### **5.2 Implementation Guide: Twelve Data (Infinity Plugin)**

* **URL:** https://api.twelvedata.com/time\_series  
* **Method:** GET  
* **Params:**  
  * symbol: EUR/USD (or BTC/USD, SPX, etc.)  
  * interval: 1h (or 1day for longer trends)  
  * apikey: *\[Your\_API\_Key\]*  
  * format: JSON  
* **Infinity Parsing:**  
  * Rows: values  
  * Columns: datetime (Time), close (Number), open, high, low.

### **5.3 Implementation Guide: FRED (Infinity Plugin)**

* **URL:** https://api.stlouisfed.org/fred/series/observations  
* **Params:**  
  * series\_id: DGS10 (US 10Y), VIXCLS (VIX), IRLTLT01DEQ156N (Germany 10Y)  
  * api\_key: *\[Your\_FRED\_Key\]*  
  * file\_type: json  
* **Infinity Parsing:**  
  * Rows: observations  
  * Columns: date (Time), value (Number).

### **5.4 Fear & Greed Scraper (Python)**

Since no direct API exists, use this script to fetch data and push it to Grafana (via InfluxDB or a simple JSON endpoint).

```python
import requests
import json
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# CNN Fear & Greed endpoint
URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# InfluxDB configuration (use environment variables in production)
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "your-token-here"  # Use os.environ.get("INFLUX_TOKEN")
INFLUX_ORG = "grafainance"
INFLUX_BUCKET = "market_sentiment"

def get_fear_greed():
    try:
        response = requests.get(URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current_score = data['fear_and_greed']['score']
        rating = data['fear_and_greed']['rating']
        timestamp = data['fear_and_greed']['timestamp']
        
        return {
            "score": current_score,
            "rating": rating,
            "timestamp": timestamp
        }
    except requests.RequestException as e:
        print(f"Error fetching Fear & Greed: {e}")
        return None

def push_to_influx(data):
    with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        point = Point("fear_greed") \
            .field("score", float(data["score"])) \
            .tag("rating", data["rating"])
        write_api.write(bucket=INFLUX_BUCKET, record=point)
        print(f"Pushed score {data['score']} ({data['rating']}) to InfluxDB")

if __name__ == "__main__":
    result = get_fear_greed()
    if result:
        print(json.dumps(result, indent=2))
        push_to_influx(result)
```

**Scheduling:** Run via cron every 4 hours: `0 */4 * * * /usr/bin/python3 /opt/grafainance/fear_greed_scraper.py`

## **6\. Non-Functional Requirements**

* **Latency:**  
  * Forex/Crypto: 15-60 minute refresh rate (tiered by priority, see Section 4.1).  
  * Macro/Yields: Daily refresh (data only updates EOD).  
* **Reliability:**
  * Dashboards must handle API rate limits gracefully (using Infinity's "Cache" feature).
  * Display "Stale Data" indicator if last update exceeds 2× expected refresh interval.
  * Fallback to cached/alternative sources on primary API failure (see Section 4.2).
* **Cost:** $0/month using Free Tiers for Twelve Data and FRED.
* **Mobile Responsiveness:** Dashboards must render correctly on tablet (768px+) viewports.
* **Accessibility:** Color scheme must distinguish Risk-On (green) vs Risk-Off (red) states; avoid sole reliance on color.

## **6.1 Security Requirements**

| Requirement | Implementation |
| :---- | :---- |
| API Key Storage | Environment variables or Grafana provisioned secrets (never in dashboards) |
| Dashboard Access | Grafana RBAC: Viewer role for traders, Editor for admins |
| Scraper Credentials | Stored in `/etc/grafainance/.env` with `chmod 600` |
| Network | InfluxDB accessible only from localhost or internal network |
| Audit | Enable Grafana audit logging for dashboard changes |

## **7\. Roadmap**

| Phase | Scope | Duration | Deliverables |
| :---- | :---- | :---- | :---- |
| **Phase 1 (MVP)** | Core infrastructure | 2 weeks | Twelve Data & FRED connections, 3 dashboards, VIX as "Fear" proxy |
| **Phase 2 (Sentiment)** | Enhanced sentiment | 1 week | Python scraper for Fear & Greed, InfluxDB integration, News Sentiment panel |
| **Phase 3 (Alerting)** | Proactive monitoring | 1 week | Grafana Alerts (USD/JPY > 150, VIX > 30, yield curve inversion) |
| **Phase 4 (Hardening)** | Production readiness | 1 week | Fallback sources, stale data indicators, mobile optimization, security audit |

## **8\. Risks & Mitigations**

| Risk | Likelihood | Impact | Mitigation |
| :---- | :---- | :---- | :---- |
| Twelve Data API deprecation or pricing change | Medium | High | Implement yfinance fallback; monitor API changelog |
| CNN Fear & Greed endpoint changes | High | Medium | Scraper monitoring with alerts; manual backup data entry |
| FRED rate limits during market volatility | Low | Medium | Aggressive caching; reduce refresh frequency during high-load periods |
| Grafana Infinity plugin incompatibility | Low | High | Grafana >= 10.4.8 required for Infinity plugin v3.x; test upgrades in staging |
| InfluxDB data corruption | Low | Medium | Weekly backups; 30-day retention allows rebuild from sources |

## **9\. Dependencies**

| Component | Version | Purpose |
| :---- | :---- | :---- |
| Grafana | 10.x+ | Dashboard platform |
| Infinity Datasource Plugin | 2.x | REST API connectivity |
| InfluxDB | 2.x | Fear & Greed time-series storage |
| Python | 3.9+ | Scraper runtime |
| influxdb-client (Python) | 1.36+ | InfluxDB writes |
| requests (Python) | 2.28+ | HTTP client for scraping |
| Cron / systemd timer | — | Scraper scheduling |