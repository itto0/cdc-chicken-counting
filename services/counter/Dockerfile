FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only counter service files (completely self-contained)
COPY . /app

# Create data directory for local outbox SQLite database
RUN mkdir -p /data /app/data

ENV PYTHONPATH=/app
ENV LINE_ID=line-1
ENV VIDEO_SOURCE_TYPE=synthetic
ENV API_SYNC_URL=http://localhost:8000/api/v1/sync/batch
ENV DB_PATH=/data/counter_outbox.db
ENV SYNC_INTERVAL_SEC=5.0

CMD ["python", "main.py"]
