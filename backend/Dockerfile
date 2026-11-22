FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (for torch / sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persist the vector store in a Docker volume via /app/data
VOLUME ["/app/data"]

EXPOSE 8000

# Use $PORT if set by the platform (Render, Railway, Fly.io), else default to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
