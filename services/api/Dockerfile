FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN pip install --no-cache-dir \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.28.0" \
    "sqlalchemy>=2.0.0" \
    "pydantic>=2.5.0" \
    "httpx>=0.27.0" \
    "openpyxl>=3.1.0"

# Copy shared code and service code
COPY shared /app/shared
COPY services/api /app/services/api

# Create data directory for SQLite database storage and ensure /app/data exists
RUN mkdir -p /data /app/data

ENV PYTHONPATH=/app
ENV DATABASE_URL=sqlite:////data/api_central.db

EXPOSE 8000

CMD ["uvicorn", "services.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
