FROM python:3.11-slim

# System dependencies for Playwright and Lighthouse
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Lighthouse
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g lighthouse

# Install uv
RUN pip install uv

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY . .

# Install Playwright browsers
RUN uv run playwright install chromium --with-deps

# Create data directories
RUN mkdir -p data/logs data/chroma data/exports data/screenshots

EXPOSE 8000 8501

# Default: start both API and dashboard
CMD ["sh", "-c", "uv run uvicorn sharpqa_agent.orchestrator.api:app --host 0.0.0.0 --port 8000 & uv run streamlit run src/sharpqa_agent/dashboard/app.py --server.port 8501 --server.address 0.0.0.0"]
