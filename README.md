[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![httpx](https://img.shields.io/badge/httpx-latest-green.svg)](https://www.python-httpx.org/)
[![Pydantic](https://img.shields.io/badge/pydantic-v2-orange.svg)](https://pydantic.dev/)

# Dietly Menu Synchronizer

A production-ready Python application that automatically syncs meal data from [Dietly.pl](https://dietly.pl) to [Fitatu.com](https://fitatu.com) by calling both services' web APIs directly with httpx. Features clean architecture, comprehensive error handling, and multiple deployment options.

## 🚀 Features

- **Automated Daily Sync**: Runs via Gitea Actions (homelab runner), Docker, or cron jobs
- **Clean Architecture**: Modular design following SOLID principles
- **Smart Error Handling**: Robust handling of missing meals, API errors, and timeouts
- **Multi-Layer Retry Logic**: Exponential backoff retry at HTTP and user-sync levels
- **Multi-User Support**: Configure multiple Dietly/Fitatu account pairs
- **Viking-Style Logic**: Search-first, create-only-if-not-found approach
- **Comprehensive Logging**: Detailed execution logs with proper exit codes
- **Mobile Notifications**: Multiple notification options for sync status
- **Configuration-Driven**: YAML-based configuration with validation

## 📋 Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Dietly.pl account with active meal plan
- Fitatu.com account with API access

## 🛠 Installation

### Local Development

```bash
# Clone the repository
git clone ssh://git@gitea-ssh.mati-lab.online:30009/gooral/dietly-scraper.git
cd dietly-scraper

# Install dependencies with uv
uv sync
```

## 🔧 Configuration

### 1. Create Configuration Files

Copy the example files and configure them with your credentials:

```bash
cp config/users.yaml.example config/users.yaml
# optional — only to override the built-in site URLs:
cp config/sites.yaml.example config/sites.yaml
```

### 2. Configure Sites (optional, config/sites.yaml)

These are the built-in defaults; create the file only to override them.

```yaml
dietly:
  base_url: "https://dietly.pl"
  login_url: "https://dietly.pl/api/auth/login"
  api_url: "https://dietly.pl/api"

fitatu:
  base_url: "https://fitatu.com"
  api_url: "https://pl-pl.fitatu.com/api"
```

### 3. Configure Users (config/users.yaml)

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

> ⚠️ **Security Note**: Keep `config/users.yaml` private and never commit credentials to version control.

## 🚀 Quick Start

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

### 🥇 Gitea Actions on the homelab runner (production)

`.gitea/workflows/daily-sync.yml` runs daily at 02:00 UTC (and on manual dispatch)
on the self-hosted Gitea runner, so requests leave from the home IP.

**Repository secrets** (Gitea → repo → Settings → Actions → Secrets):
- `USERS_YAML`: full content of `config/users.yaml` (multi-line is fine)
- `NTFY_TOKEN` *(optional)*: write-only ntfy token; failures are posted to `homelab-alerts`
- `KUMA_PUSH_URL` *(optional)*: Uptime Kuma push URL; every successful run sends a heartbeat

Site URLs are built-in defaults, so `config/sites.yaml` is only needed to override them.

**Notifications:**
- Exit code 1 (some users failed) or 2 (all failed) fails the job → ntfy alert with the failed users
- No successful run within the Kuma push interval (e.g. the runner was down) → Kuma alert
- "No active plan" / "no menu" counts as success (normal on weekends)

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

### Constants (src/utils/constants.py)

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_REQUEST_TIMEOUT` | 30 | HTTP request timeout (seconds) |
| `DEFAULT_SCRAPING_TIMEOUT` | 15 | Page scraping timeout (seconds) |
| `SEARCH_PAGE_LIMIT` | 1 | API search results limit |
| `MEAL_MAPPING` | Dict | Dietly → Fitatu meal name mapping |

### Environment Variables

```bash
# Override default configurations
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
- **Gitea Actions**: Workflow run logs in the repo's Actions tab

### Health Checks

```bash
# Test configuration loading
uv run python -c "from src.models.config_model import SitesConfiguration, UsersConfiguration; print('✅ Config valid')"

# Test API connectivity
uv run python -c "
import asyncio
from src.clients.fitatu_client import FitatuClient
from src.models.config_model import SitesConfiguration, UsersConfiguration

async def test():
    sites = SitesConfiguration.load_from_file('config/sites.yaml')
    users = UsersConfiguration.load_from_file('config/users.yaml')
    client = FitatuClient(sites.fitatu, users.users[0].fitatu_credentials, 'Test')
    result = await client.login()
    print('✅ Fitatu connection successful' if result else '❌ Fitatu login failed')

asyncio.run(test())
"
```

## 🔄 Retry & Resilience Strategy

The application implements a comprehensive multi-layer retry strategy to handle transient failures:

### HTTP-Level Retries (BaseAPIClient)
- **Exponential backoff** with jitter (1s, 2s, 4s delays)
- **Retryable status codes**: 500, 502, 503, 504
- **Network error handling**: Connection timeouts, DNS failures
- **Non-retryable errors**: 4xx client errors (don't retry)

### User-Level Retries (Main Sync Logic)
- **Intelligent failure detection**: Distinguishes transient vs permanent failures
- **Per-user retry**: Each user's sync is retried independently
- **Transient error patterns**: "503", "timeout", "connection", "network"

### No Workflow-Level Retry
The workflow deliberately does not re-run the whole sync: that would re-sync users
that already succeeded. Transient errors are retried by the two layers above.

### Example Retry Flow

```bash
# HTTP level: 503 Service Unavailable
2025-06-11 02:30:54 - WARNING: Request POST https://dietly.pl/api/auth/login failed (attempt 1/3): HTTP 503 error. Retrying in 1.2s...
2025-06-11 02:30:56 - WARNING: Request POST https://dietly.pl/api/auth/login failed (attempt 2/3): HTTP 503 error. Retrying in 2.4s...
2025-06-11 02:30:59 - INFO: POST https://dietly.pl/api/auth/login - Status: 200

# User level: If still failing
2025-06-11 02:31:00 - WARNING: User Kamil sync failed with transient error (attempt 1/3): Dietly API failed: Login failed
2025-06-11 02:31:00 - INFO: Will retry user Kamil sync in next attempt...

```

### Tests

```bash
uv run --extra dev pytest
```

## 🛠️ Development

### Project Structure

```
dietly-scraper/
├── 📁 .gitea/workflows/           # Gitea Actions (CI + daily sync)
├── 📁 config/                     # Configuration files
│   ├── sites.yaml                 # API endpoints configuration
│   └── users.yaml                 # User credentials
├── 📁 src/                        # Source code
│   ├── 📁 clients/                # API clients
│   │   ├── base_client.py         # HTTP client base class
│   │   ├── dietly_client.py       # Dietly web scraping
│   │   └── fitatu_client.py       # Fitatu API client
│   ├── 📁 models/                 # Data models
│   │   ├── add_product_model.py   # Nutrition product models
│   │   ├── config_model.py        # Configuration models
│   │   ├── dietly_order_models.py # Dietly order models
│   │   └── menu_response_model.py # Menu response models
│   └── 📁 utils/                  # Utility functions
│       ├── constants.py           # Application constants
│       └── utils.py               # Helper functions
├── 📄 main.py                     # Application entry point
├── 📄 docker-compose.yml          # Docker configuration
├── 📄 Dockerfile                  # Docker image definition
├── 📄 pyproject.toml              # Dependencies
└── 📄 README.md                   # This file
```

### Core Architecture

The application follows clean architecture principles:

- **`main.py`**: Entry point and orchestration
- **`src/clients/`**: External service integrations
  - `DietlyClient`: Dietly login (with XSRF token) and menu retrieval
  - `FitatuClient`: Manages Fitatu API operations with Viking-style logic
  - `BaseAPIClient`: Shared httpx client with retry/backoff on 5xx
- **`src/models/`**: Data structures and validation using Pydantic
- **`src/utils/`**: Shared utilities and constants

### Key Features

- **Viking-Style Sync**: Search first, create only if not found
- **Smart Deduplication**: Avoids creating duplicate products
- **Robust Error Handling**: Multi-layer error catching with graceful degradation
- **Configuration-Driven**: YAML-based configuration with type validation

### Adding New Features

1. **Extend models** in `src/models/` for new data structures
2. **Add constants** in `src/utils/constants.py` for configuration
3. **Create utilities** in `src/utils/utils.py` for reusable functions
4. **Update clients** in `src/clients/` for new API endpoints
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
- Verify credentials in `config/users.yaml`
- Check if 2FA is enabled (not supported)
- Ensure API secret is valid for Fitatu

#### Rate Limiting

```
ERROR: HTTP 429 error: Too Many Requests
```

**Solutions:**
- Increase `DEFAULT_REQUEST_TIMEOUT` in `src/utils/constants.py`
- Add delays between requests
- Check API rate limits with service providers

#### Network Timeouts

```
ERROR: Request failed for GET https://...
```

**Solutions:**
- Check internet connectivity
- Verify site URLs in `config/sites.yaml`
- Increase timeout values in `src/utils/constants.py`
- **Note**: HTTP timeouts are often treated as "no menu available" (acceptable)

#### Error Handling & Resilience

The application includes comprehensive error handling:

- **All users processed**: Even if one user fails, others continue processing
- **Graceful timeouts**: HTTP timeouts treated as "no menu found"
- **Detailed logging**: Each error includes user context and specific failure reason
- **Fallback handling**: Multiple layers of error catching prevent script crashes

**Error Recovery Examples:**
```bash
# User 1 fails with timeout (treated as no menu)
2025-05-29 10:21:50,057 - ERROR - Unexpected error processing User1: TimeoutError
2025-05-29 10:21:50,058 - INFO - HTTP/timeout error for User1 - likely no menu available

# User 2 continues processing normally
2025-05-29 10:21:50,059 - INFO - Processing user: User2
2025-05-29 10:22:15,123 - INFO - Successfully retrieved menu data for User2
```

### Debug Mode

```bash
# Run with detailed logging
LOG_LEVEL=DEBUG uv run python main.py

# Test specific component
uv run python -c "
import asyncio
from src.clients.dietly_client import DietlyClient
from src.models.config_model import SitesConfiguration, UsersConfiguration

async def test():
    sites = SitesConfiguration.load_from_file('config/sites.yaml')
    users = UsersConfiguration.load_from_file('config/users.yaml')
    client = DietlyClient(sites.dietly, users.users[0].dietly_credentials)
    # ... test code

asyncio.run(test())
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

This project is licensed under the MIT License

## ⚠️ Disclaimer

This tool is for personal use only. Please respect the terms of service of both Dietly and Fitatu. The authors are not responsible for any violations or issues arising from the use of this software.

---

**Made with ❤️ for automated nutrition tracking**
