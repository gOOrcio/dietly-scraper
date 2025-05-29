FROM python:3.12-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY . .

# Install dependencies
RUN uv sync

# Install Playwright and browsers
RUN uv run playwright install chromium
RUN uv run playwright install-deps

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
USER app

# Run the scraper
CMD ["uv", "run", "python", "main.py"] 