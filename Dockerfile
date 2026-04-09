FROM python:3.12-slim

# Install Node.js for frontend build and Playwright system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
COPY contractmonitor/ contractmonitor/
RUN pip install --no-cache-dir . && playwright install chromium

# Build frontend
COPY frontend/ frontend/
RUN cd frontend && npm install && npm run build

# Copy env example
COPY .env.example .env.example

EXPOSE 8080

CMD ["contract-monitor", "--serve", "--port", "8080"]
