# 🍽️ Dietly Scraper

**Automated meal synchronization from Dietly to Fitatu for seamless nutrition tracking.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Playwright](https://img.shields.io/badge/playwright-latest-green.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📖 Overview

Dietly Scraper automates the process of syncing daily meal plans from Dietly.pl to Fitatu.com, eliminating manual data entry while maintaining accurate nutrition tracking. The application:

- 🔍 **Scrapes** meal data from Dietly using authenticated API calls
- 🔄 **Syncs** nutritional information to Fitatu with intelligent deduplication
- 📅 **Schedules** automatic daily runs via GitHub Actions or Docker
- 🛡️ **Handles** errors gracefully with comprehensive logging

## 🏗️ Architecture

```mermaid
graph TD
    A[Scheduler] --> B[Main App]
    B --> C[Dietly Scraper]
    B --> D[Fitatu Client]
    C --> E[Dietly API]
    D --> F[Fitatu API]
    B --> G[Config Manager]
    G --> H[users.yaml]
    G --> I[sites.yaml]
```

### Core Components

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| **DietlyScraper** | Web scraping & API interception | Playwright automation, request filtering |
| **FitatuClient** | Fitatu API integration | Product search, meal plan management |
| **BaseAPIClient** | HTTP request abstraction | Error handling, logging, timeouts |
| **Config Models** | Configuration management | YAML loading, validation, type safety |

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **uv** package manager (recommended) or pip
- Valid **Dietly.pl** and **Fitatu.com** accounts

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/dietly-scraper.git
cd dietly-scraper

# Install dependencies with uv
uv sync

# Install Playwright browsers
uv run playwright install chromium
# Or: playwright install chromium
```

### Configuration

1. **Create configuration files:**

```bash
cp sites.yaml.example sites.yaml
cp users.yaml.example users.yaml
```

2. **Configure sites.yaml:**

```yaml
dietly:
  base_url: "https://dietly.pl"
  api_url: "https://dietly.pl/api"
  login_url: "https://dietly.pl/api/auth/login"

fitatu:
  base_url: "https://www.fitatu.com"
  api_url: "https://pl-pl.fitatu.com/api"
  login_url: "https://pl-pl.fitatu.com/api/login"
```

3. **Configure users.yaml:**

```yaml
users:
  - name: "Your Name"
    dietly_credentials:
      email: "your-dietly-email@example.com"
      password: "your-dietly-password"
    fitatu_credentials:
      email: "your-fitatu-email@example.com"
      password: "your-fitatu-password"
      api_secret: "your-fitatu-api-secret"
```

> ⚠️ **Security Note**: Keep `users.yaml` private and never commit credentials to version control.

### Running

```bash
# Run once
uv run python main.py

# Run with specific log level
PYTHONPATH=. uv run python main.py

# Check logs
tail -f logs/scraper_*.log
```

## ⏰ Scheduling Options

### 🥇 GitHub Actions (Recommended)

**Setup:**

1. Push code to GitHub
2. Add repository secrets:
   - `USERS_YAML`: Content of your users.yaml
   - `SITES_YAML`: Content of your sites.yaml
3. Workflow runs daily at 2:00 AM UTC automatically

**Benefits:**
- ✅ Zero infrastructure management
- ✅ Free for public repositories
- ✅ Built-in secrets management
- ✅ Execution history and logs

## 📱 Mobile Notifications
```
🍽️ Dietly Sync Report

⚠️ Status: Partial Success - Some users failed
📅 Date: 2025-01-20 08:00 UTC
🔗 Logs: View Details
Exit Code: 1
```

### 🥈 **GitHub Mobile App**

**Setup:**
1. Install **GitHub Mobile App**
2. Repository **Settings** → **Notifications** → Enable **Actions**
3. Phone notifications settings → Enable **GitHub**

### 🔧 **Notification Triggers**

The workflow sends notifications based on exit codes:

| Exit Code | Trigger | Message |
|-----------|---------|---------|
| **0** | Success | No notification (unless `ALWAYS_NOTIFY=true`) |
| **1** | Partial failure | ⚠️ Some users failed to sync |
| **2** | Complete failure | ❌ All users failed to sync |

**Smart notifications:**
- 🍽️ **No menu found** = No notification (normal on weekends)
- ⚠️ **Some users failed** = Warning notification  
- ❌ **All users failed** = Critical notification

### 🥈 Docker (Cross-platform)

```bash
# Build and start scheduler
docker-compose up -d scheduler

# View logs
docker-compose logs -f scheduler

# Manual run
docker-compose run --rm dietly-scraper

# Stop scheduler
docker-compose down
```

### 🥉 Cron Job (Linux/macOS)

```bash
# Add to crontab (daily at 8 AM)
crontab -e

# Add line:
0 8 * * * /full/path/to/your/project/run_scraper.sh
```

## 🔧 Configuration Reference

### Constants (constants.py)

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_REQUEST_TIMEOUT` | 30 | HTTP request timeout (seconds) |
| `DEFAULT_SCRAPING_TIMEOUT` | 15 | Page scraping timeout (seconds) |
| `SEARCH_PAGE_LIMIT` | 1 | API search results limit |
| `MEAL_MAPPING` | Dict | Dietly → Fitatu meal name mapping |

### Environment Variables

```bash
# Override default configurations
export DIETLY_HEADLESS=false          # Show browser during scraping
export FITATU_BRAND="Custom Brand"    # Override default brand name
export LOG_LEVEL=DEBUG                # Increase logging verbosity
```

## 📊 Exit Codes & Status Handling

The application uses specific exit codes to indicate different sync outcomes:

| Exit Code | Status | Description | Cron/CI Behavior |
|-----------|--------|-------------|------------------|
| **0** | ✅ Success | All users processed successfully | Job marked as passed |
| **1** | ⚠️ Partial | Some users synced, others failed | Job marked as warning |
| **2** | ❌ Failed | No users synced successfully | Job marked as failed |

### Sync Scenarios

The application distinguishes between different scenarios:

**🍽️ No Menu Available**
- When no menu is found for today (common on weekends/holidays)
- Treated as **acceptable** and doesn't count as failure
- Logs: `ℹ️ No menu data found for [user] - sync skipped (acceptable)`

**✅ Successful Sync**
- Menu found and successfully synced to Fitatu
- Logs: `✅ [user]: Menu synced successfully`

**❌ Sync Failed**
- Menu found but Fitatu sync failed (auth, API errors, etc.)
- Treated as **failure** requiring attention
- Logs: `❌ [user]: Fitatu sync failed`

### Example Log Output

```
2025-05-29 09:55:15,850 - INFO - Starting Dietly sync for 2025-05-29
2025-05-29 09:55:15,851 - INFO - Processing user: User1
2025-05-29 09:55:25,157 - INFO - No menu data found for User1 on 2025-05-29 - sync skipped (acceptable)
2025-05-29 09:55:25,157 - INFO - Processing user: User2  
2025-05-29 09:55:35,260 - ERROR - Failed to login to Fitatu for User2
2025-05-29 09:55:35,260 - INFO - === SYNC SUMMARY ===
2025-05-29 09:55:35,260 - INFO - Total users: 2
2025-05-29 09:55:35,260 - INFO - Successful syncs: 0
2025-05-29 09:55:35,260 - INFO - No menu available: 1
2025-05-29 09:55:35,260 - INFO - Failed syncs: 1
2025-05-29 09:55:35,260 - INFO - ℹ️ User1: No menu available for today
2025-05-29 09:55:35,260 - INFO - ❌ User2: Fitatu sync failed
2025-05-29 09:55:35,260 - WARNING - ⚠️ Partial success - some users failed to sync
2025-05-29 09:55:35,260 - INFO - Sync completed with exit code: 1
```

## 📊 Monitoring & Logging

### Log Levels

- **INFO**: Normal operation, meal processing status
- **WARNING**: Non-critical issues, skipped meals
- **ERROR**: Failed operations, authentication problems
- **DEBUG**: Detailed HTTP requests, response parsing

### Log Locations

- **Local**: `logs/scraper_YYYYMMDD_HHMMSS.log`
- **Docker**: Container logs via `docker-compose logs`
- **GitHub Actions**: Workflow run logs in Actions tab

### Health Checks

```bash
# Test configuration loading
uv run python -c "from config_model import SitesConfig, UsersConfig; print('✅ Config valid')"

# Test API connectivity
uv run python -c "
import asyncio
from fitatu_client import FitatuClient
from config_model import SitesConfig, UsersConfig

async def test():
    sites = SitesConfig.load('sites.yaml')
    users = UsersConfig.load('users.yaml')
    client = FitatuClient(sites.fitatu, users.users[0].fitatu_credentials, 'Test')
    result = await client.login()
    print('✅ Fitatu connection successful' if result else '❌ Fitatu login failed')

asyncio.run(test())
"
```

## 🛠️ Development

### Project Structure

```
dietly-scraper/
├── 📁 .github/workflows/    # GitHub Actions
├── 📄 main.py              # Application entry point
├── 📄 dietly_scraper.py    # Dietly web scraping
├── 📄 fitatu_client.py     # Fitatu API client
├── 📄 base_client.py       # HTTP client base class
├── 📄 config_model.py      # Configuration models
├── 📄 constants.py         # Application constants
├── 📄 utils.py             # Utility functions
├── 📄 *_model.py           # Data models
├── 📄 sites.yaml           # API endpoints
├── 📄 users.yaml           # User credentials
├── 📄 pyproject.toml       # Dependencies
└── 📄 README.md            # This file
```

### Adding New Features

1. **Extend models** in `*_model.py` for new data structures
2. **Add constants** in `constants.py` for configuration
3. **Create utilities** in `utils.py` for reusable functions
4. **Update clients** for new API endpoints
5. **Modify main.py** for new processing logic

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type checking
uv run mypy .

# Run tests (when available)
uv run pytest
```

## 🐛 Troubleshooting

### Common Issues

#### Authentication Failures

```
ERROR: Login failed with status 401
```

**Solutions:**
- Verify credentials in `users.yaml`
- Check if 2FA is enabled (not supported)
- Ensure API secret is valid for Fitatu

#### Playwright Browser Issues

```
ERROR: Browser executable not found
```

**Solutions:**
```bash
# Reinstall browsers
uv run playwright install chromium
uv run playwright install-deps

# For Docker
docker-compose build --no-cache
```

#### Rate Limiting

```
ERROR: HTTP 429 error: Too Many Requests
```

**Solutions:**
- Increase `DEFAULT_REQUEST_TIMEOUT` in constants.py
- Add delays between requests
- Check API rate limits with service providers

#### Network Timeouts

```
ERROR: Request failed for GET https://...
playwright._impl._errors.TimeoutError: Page.goto: Timeout 45000ms exceeded
```

**Solutions:**
- Check internet connectivity
- Verify site URLs in `sites.yaml`
- Increase timeout values in constants.py
- **Note**: Navigation timeouts are often treated as "no menu available" (acceptable)

#### Error Handling & Resilience

The application includes comprehensive error handling:

- **All users processed**: Even if one user fails, others continue processing
- **Graceful timeouts**: Playwright navigation timeouts treated as "no menu found"
- **Detailed logging**: Each error includes user context and specific failure reason
- **Fallback handling**: Multiple layers of error catching prevent script crashes

**Error Recovery Examples:**
```bash
# User 1 fails with timeout (treated as no menu)
2025-05-29 10:21:50,057 - ERROR - Unexpected error processing User1: TimeoutError
2025-05-29 10:21:50,058 - INFO - Navigation/timeout error for User1 - likely no menu available

# User 2 continues processing normally
2025-05-29 10:21:50,059 - INFO - Processing user: User2
2025-05-29 10:22:15,123 - INFO - Successfully retrieved menu data for User2
```

### Debug Mode

```bash
# Run with detailed logging
LOG_LEVEL=DEBUG uv run python main.py

# Run with visible browser
DIETLY_HEADLESS=false uv run python main.py

# Test specific component
uv run python -c "
import asyncio
from dietly_scraper import DietlyScraper
# ... test code
"
```

### Getting Help

1. **Check logs** for specific error messages
2. **Verify configuration** files are properly formatted
3. **Test connectivity** to both services manually
4. **Review recent changes** to API endpoints or credentials
5. **Open an issue** with logs and configuration (remove credentials!)

## 📈 Future Roadmap

See [improvements.md](improvements.md) for planned enhancements:

- 🔄 **Retry logic** with exponential backoff
- 📊 **Monitoring** with metrics and alerting  
- 🧪 **Testing** with comprehensive test suite
- 🔐 **Security** improvements and secrets rotation
- 🚀 **Performance** optimizations and caching

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** changes (`git commit -m 'Add amazing feature'`)
4. **Push** to branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup

```bash
# Install development dependencies
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install

# Run full test suite
uv run pytest --cov=.
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for personal use only. Please respect the terms of service of both Dietly and Fitatu. The authors are not responsible for any violations or issues arising from the use of this software.

---

**Made with ❤️ for automated nutrition tracking**
