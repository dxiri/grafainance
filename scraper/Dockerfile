FROM python:3.11-slim

LABEL maintainer="Grafainance"
LABEL description="Fear & Greed Index Scraper for Grafainance"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scraper scripts
COPY fear_greed_scraper.py .
COPY aeco_scraper.py .
COPY lng_price_scraper.py .

# Run as non-root user
RUN useradd -m -r scraper && chown -R scraper:scraper /app
USER scraper

# Default command - can be overridden by cron or orchestrator
CMD ["python", "fear_greed_scraper.py"]
