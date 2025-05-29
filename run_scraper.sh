#!/bin/bash

# Dietly Scraper Runner Script
# Usage: Add to crontab with: 0 8 * * * /path/to/run_scraper.sh

# Set working directory
cd "$(dirname "$0")"

# Set up environment
export PATH="$HOME/.local/bin:$PATH"

# Log file with timestamp
LOG_FILE="logs/scraper_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

# Run the scraper and log output
echo "$(date): Starting Dietly scraper..." >> "$LOG_FILE"

# Activate virtual environment and run
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "No virtual environment found, using system Python" >> "$LOG_FILE"
fi

# Run with uv if available, otherwise use python directly
if command -v uv >/dev/null 2>&1; then
    uv run python main.py >> "$LOG_FILE" 2>&1
else
    python main.py >> "$LOG_FILE" 2>&1
fi

EXIT_CODE=$?

# Log appropriate message based on exit code
if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date): ✅ Scraper completed successfully - all users processed" >> "$LOG_FILE"
elif [ $EXIT_CODE -eq 1 ]; then
    echo "$(date): ⚠️ Scraper completed with warnings - partial success" >> "$LOG_FILE"
elif [ $EXIT_CODE -eq 2 ]; then
    echo "$(date): 💥 Scraper failed - no users synced successfully" >> "$LOG_FILE"
else
    echo "$(date): ❓ Scraper finished with unexpected exit code $EXIT_CODE" >> "$LOG_FILE"
fi

echo "$(date): Scraper finished with exit code $EXIT_CODE" >> "$LOG_FILE"

# Keep only last 7 days of logs
find logs -name "scraper_*.log" -mtime +7 -delete

exit $EXIT_CODE