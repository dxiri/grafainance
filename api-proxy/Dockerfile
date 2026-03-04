FROM python:3.11-slim

LABEL description="API key injection proxy for Grafainance"

WORKDIR /app
COPY proxy.py .

# Run as non-root (nobody user is built-in)
USER nobody

EXPOSE 8080
CMD ["python", "proxy.py"]
