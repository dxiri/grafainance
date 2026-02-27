# Grafainance - Financial Market Intelligence Dashboards

A centralized, real-time financial monitoring suite built with Grafana, providing a holistic view of global market health, currency strength, and crypto asset performance.

![Grafana](https://img.shields.io/badge/Grafana-10.x-orange)
![InfluxDB](https://img.shields.io/badge/InfluxDB-2.x-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Market Overview Dashboard**: Fear & Greed Index, VIX, and major market indexes
- **Forex & Crypto Monitor**: Real-time candlestick charts for currency pairs and cryptocurrencies
- **Macro & Yield Curves**: US, German, and Japanese government bond yields with spread analysis
- **Zero-cost data sources**: Free tier APIs from Twelve Data and FRED
- **Automated sentiment tracking**: Fear & Greed Index scraper with InfluxDB storage
- **AECO natural gas prices**: Automated scraper from Gas Alberta's market data

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- API keys from:
  - [Twelve Data](https://twelvedata.com/pricing) (free tier: 800 requests/day)
  - [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) (free, unlimited)

### 1. Clone and Configure

```bash
cd Grafainance

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

### 2. Set Your API Keys

Edit `.env` and fill in:

```bash
TWELVE_DATA_API_KEY=your_twelve_data_key_here
FRED_API_KEY=your_fred_key_here
INFLUXDB_TOKEN=your_secure_token_here  # Generate a random string
GF_SECURITY_ADMIN_PASSWORD=your_grafana_password
INFLUXDB_ADMIN_PASSWORD=your_influxdb_password
```

### 3. Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f grafana
```

### 4. Access Dashboards

Open your browser and navigate to:

- **Grafana**: http://localhost:3000
  - Username: `admin` (or value of `GF_SECURITY_ADMIN_USER`)
  - Password: Your configured password

The dashboards will be automatically provisioned in the "Financial Markets" folder.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Grafana                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Market      │  │ Forex &     │  │ Macro & Yield           │  │
│  │ Overview    │  │ Crypto      │  │ Curves                  │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                      │                │
│  ┌──────┴────────────────┴──────────────────────┴─────────────┐ │
│  │                    Infinity Datasource                      │ │
│  └──────────────────────────┬───────────────────────────────┬─┘ │
│                             │                               │   │
│  ┌──────────────────────────┴───┐    ┌─────────────────────┴─┐ │
│  │         InfluxDB             │    │    External APIs      │ │
│  │    (Fear & Greed data)       │    │  (Twelve Data, FRED)  │ │
│  └──────────────────────────────┘    └───────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
           ▲
           │
┌──────────┴──────────┐
│  Fear & Greed       │
│  Scraper (Python)   │
│  (runs every 4hrs)  │
└─────────────────────┘
```

## Project Structure

```
Grafainance/
├── docker-compose.yml          # Container orchestration
├── .env.example                # Environment template
├── .env                        # Your configuration (git-ignored)
├── README.md                   # This file
├── Financial Grafana Dashboards PRD.md  # Product requirements
│
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── datasources.yml # Datasource configurations
│       └── dashboards/
│           ├── dashboards.yml  # Dashboard provisioning config
│           ├── market-overview.json
│           ├── forex-crypto.json
│           └── macro-yields.json
│
└── scraper/
    ├── Dockerfile              # Scraper container
    ├── requirements.txt        # Python dependencies
    ├── fear_greed_scraper.py   # CNN Fear & Greed scraper
    └── aeco_scraper.py         # AECO natural gas price scraper
```

## Dashboards

### 1. Market Overview & Sentiment

The "cockpit" view for instant Risk On/Risk Off assessment.

| Panel | Data Source | Refresh |
|-------|-------------|---------|
| Fear & Greed Gauge | InfluxDB | 4 hours |
| VIX Time Series | FRED | Daily |
| S&P 500 (SPY) | Twelve Data | 60 min |
| Japan (EWJ) | Twelve Data | 60 min |
| MSCI World (URTH) | Twelve Data | 60 min |
| MSCI China (MCHI) | Twelve Data | 60 min |
| Gold (XAU/USD) | Twelve Data | 60 min |
| Silver (SLV ETF) | Twelve Data | 60 min |
| Copper (CPER ETF) | Twelve Data | 60 min |
| Natural Gas — Henry Hub | FRED | 1 hour |
| Natural Gas — AECO | InfluxDB (Gas Alberta scraper) | 4 hours |
| Natural Gas — Japan LNG | FRED | 1 hour |

### 2. Forex & Crypto Monitor

Currency and cryptocurrency tracking with candlestick charts.

| Panel | Data Source | Refresh |
|-------|-------------|---------|
| EUR/USD, USD/JPY, BTC/USD | Twelve Data | 15 min |
| GBP/USD, USD/CAD, ETH/USD | Twelve Data | 30 min |
| USD/CRC, XMR/USD | Twelve Data | 60 min |

### 3. Macro & Yield Curves

Bond market analysis and recession indicators.

| Panel | Data Source | Refresh |
|-------|-------------|---------|
| US Treasury Curve (2Y, 10Y, 30Y) | FRED | Daily |
| Global 10Y Benchmark (US, DE, JP) | FRED | Daily |
| 10Y-2Y Spread (Recession Indicator) | FRED | Daily |

## API Rate Limits

The configuration is optimized for Twelve Data's free tier:
- **8 API credits per minute**
- **8 WebSocket credits**
- **800 API credits per day**

| Dashboard | API Calls | Refresh | Daily Requests |
|-----------|-----------|---------|----------------|
| Market Overview | 8 Twelve Data + 2 FRED panels | 1 hour | 192 (TD) |
| Forex & Crypto | 8 panels | 1 hour | 192 (TD) |
| Macro & Yields | 15 FRED panels | 1 hour | 0 (TD) |
| **Total Twelve Data** | | | **384** |

FRED API calls are unlimited and free. AECO data is scraped every 4 hours (2 requests/run to gasalberta.com).

Buffer: 416 Twelve Data requests (52%) for manual refreshes or additional symbols.

**Note**: Each dashboard makes exactly 8 API calls per refresh, matching the per-minute limit. Avoid manually refreshing both dashboards simultaneously.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TWELVE_DATA_API_KEY` | Twelve Data API key | (required) |
| `FRED_API_KEY` | FRED API key | (required) |
| `INFLUXDB_TOKEN` | InfluxDB authentication token | (required) |
| `INFLUXDB_ORG` | InfluxDB organization | `grafainance` |
| `INFLUXDB_BUCKET` | InfluxDB bucket name | `market_sentiment` |
| `INFLUXDB_ADMIN_USER` | InfluxDB admin username | `admin` |
| `INFLUXDB_ADMIN_PASSWORD` | InfluxDB admin password | (required) |
| `GF_SECURITY_ADMIN_USER` | Grafana admin username | `admin` |
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin password | (required) |

### Customizing Refresh Rates

Edit the dashboard JSON files in `grafana/provisioning/dashboards/` to adjust:

- Panel refresh intervals (in the `refresh` field)
- API query parameters (in the `url` field of each target)

## Operations

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f grafana
docker-compose logs -f scraper-cron
```

### Restarting Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart grafana
```

### Updating Dashboards

After modifying dashboard JSON files:

```bash
# Grafana will auto-reload provisioned dashboards
# Or force restart:
docker-compose restart grafana
```

### Running Scraper Manually

```bash
# Run one-off scraper execution
docker-compose run --rm scraper
```

### Stopping Services

```bash
# Stop all (preserves data)
docker-compose stop

# Stop and remove containers (preserves volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v
```

### Backup

```bash
# Backup InfluxDB data
docker-compose exec influxdb influx backup /tmp/backup
docker cp grafainance-influxdb:/tmp/backup ./backups/

# Backup Grafana data
docker cp grafainance-grafana:/var/lib/grafana ./backups/grafana/
```

## Troubleshooting

### Dashboards Not Loading

1. Check Grafana logs: `docker-compose logs grafana`
2. Verify API keys are set in `.env`
3. Test API endpoints manually:
   ```bash
   # Test Twelve Data
   curl "https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=1h&outputsize=1&apikey=YOUR_KEY"
   
   # Test FRED
   curl "https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key=YOUR_KEY&file_type=json&limit=1"
   ```

### Fear & Greed Not Updating

1. Check scraper logs: `docker-compose logs scraper-cron`
2. Verify InfluxDB is healthy: `docker-compose ps`
3. Run scraper manually: `docker-compose run --rm scraper`

### Rate Limit Errors

If you see 429 errors from Twelve Data:
1. Increase refresh intervals in dashboard JSON
2. Reduce `outputsize` parameters
3. Consider upgrading to a paid tier

### InfluxDB Connection Issues

1. Wait for InfluxDB to be healthy (check with `docker-compose ps`)
2. Verify token matches between `.env` and Grafana datasource
3. Test connection:
   ```bash
   docker-compose exec influxdb influx ping
   ```

## Security Considerations

- **API Keys**: Never commit `.env` to version control
- **Network**: InfluxDB is only accessible within the Docker network
- **Passwords**: Use strong, unique passwords for Grafana and InfluxDB
- **Access**: Consider adding a reverse proxy (nginx/traefik) with HTTPS for production

## Upgrading

### Grafana

```bash
# Update version in docker-compose.yml
# image: grafana/grafana:10.x.x

docker-compose pull grafana
docker-compose up -d grafana
```

### InfluxDB

```bash
# Backup first!
docker-compose exec influxdb influx backup /tmp/backup

# Update version in docker-compose.yml
docker-compose pull influxdb
docker-compose up -d influxdb
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `docker-compose up`
5. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- [Grafana](https://grafana.com/) - Dashboard platform
- [Twelve Data](https://twelvedata.com/) - Market data API
- [FRED](https://fred.stlouisfed.org/) - Federal Reserve Economic Data
- [Infinity Datasource](https://github.com/grafana/grafana-infinity-datasource) - REST API plugin
