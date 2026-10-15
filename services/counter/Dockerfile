FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN pip install --no-cache-dir \
    "opencv-python-headless>=4.8.0" \
    "numpy>=1.24.0" \
    "pydantic>=2.5.0" \
    "httpx>=0.27.0"

# Copy shared code and service code
COPY shared /app/shared
COPY services/counter /app/services/counter

# Create data directory for local outbox SQLite database
RUN mkdir -p /data /app/data

ENV PYTHONPATH=/app
ENV LINE_ID=lineA
ENV VIDEO_SOURCE_TYPE=synthetic
ENV API_SYNC_URL=http://api:8000/api/v1/sync/batch
ENV DB_PATH=/data/counter_outbox.db
ENV SYNC_INTERVAL_SEC=5.0

CMD ["python", "services/counter/main.py"]
