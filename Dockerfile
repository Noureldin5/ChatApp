# Builds a lightweight image for the server entrypoint: python -m server.main
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install build deps required by bcrypt and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install only bcrypt (server doesn't need PyQt5)
COPY requirements.txt .
RUN pip install --no-cache-dir bcrypt>=4.0.1

# Copy application source
COPY . .

# Expose server port
EXPOSE 59394

# Default command: run the server module
CMD ["python", "-m", "server.main"]
