# Maintenance Scripts

This directory contains maintenance tools for the Dietly Scraper project. These scripts help ensure the system stays healthy, up-to-date, and properly configured.

## 🛠️ Available Scripts

### `maintenance.py` - Master Control Script
The unified interface to all maintenance tools.

```bash
# Run all critical maintenance tasks
python scripts/maintenance.py --critical-only

# Run comprehensive maintenance (all tasks)
python scripts/maintenance.py --all

# Run specific tasks
python scripts/maintenance.py --tasks health dependencies

# Quick health check only
python scripts/maintenance.py --health-only

# Generate maintenance report
python scripts/maintenance.py --all --report maintenance_report.txt
```

### `health_check.py` - System Health Verification
Comprehensive health checks for configuration, connectivity, and functionality.

```bash
# Run full health check
python scripts/health_check.py

# Save results to JSON
python scripts/health_check.py --output health_results.json

# Quiet mode (less verbose)
python scripts/health_check.py --quiet
```

**What it checks:**
- ✅ Python version and dependencies
- ✅ Configuration file validation
- ✅ Dietly API connectivity (all users)
- ✅ Fitatu API connectivity (all users)  
- ✅ End-to-end flow testing

### `dependency_updater.py` - Dependency Management
Automated dependency updates with safety checks and rollback capability.

```bash
# Check for outdated packages
python scripts/dependency_updater.py --check-only

# Update critical packages only
python scripts/dependency_updater.py --update-critical

# Update all dependencies
python scripts/dependency_updater.py --update-all

# Dry run (show what would be updated)
python scripts/dependency_updater.py --update-all --dry-run

# Restore from backup
python scripts/dependency_updater.py --restore latest
```

**Features:**
- 🔄 Automatic backup creation before updates
- 🏥 Health check verification after updates
- 🚨 Critical vs regular package classification
- 📊 Update reports and recommendations

### `api_monitor.py` - External API Monitoring
Monitors external APIs for breaking changes by comparing response structures.

```bash
# Monitor APIs and compare with baselines
python scripts/api_monitor.py

# Save current responses as new baselines
python scripts/api_monitor.py --save-baselines

# Generate monitoring report
python scripts/api_monitor.py --report api_status.txt --output api_data.json
```

**Monitoring targets:**
- 🌐 Dietly login endpoint
- 🌐 Dietly profile/orders endpoint
- 🌐 Fitatu API base endpoint

**Detection capabilities:**
- 📊 Response structure changes
- 🔢 HTTP status code changes
- 🏗️ Missing/new fields in API responses
- ⚡ Endpoint availability

### `config_migrator.py` - Configuration Migration
Handles configuration updates when the structure changes, with version tracking.

```bash
# Check migration status
python scripts/config_migrator.py

# Perform migration
python scripts/config_migrator.py --migrate

# Validate current configuration
python scripts/config_migrator.py --validate

# Create manual backup
python scripts/config_migrator.py --backup manual_backup

# List available backups
python scripts/config_migrator.py --list-backups

# Restore from backup
python scripts/config_migrator.py --restore backup_migration_20250120_143022
```

**Migration features:**
- 📝 Version tracking with `.version` file
- 💾 Automatic backup before migration
- ✅ Post-migration validation
- 🔄 Rollback capability

## 🚀 Quick Start

### Daily Health Check
```bash
# Quick system health verification
python scripts/maintenance.py --health-only
```

### Weekly Maintenance
```bash
# Comprehensive maintenance with report
python scripts/maintenance.py --all --report weekly_maintenance.txt
```

### Before Production Deployment
```bash
# Full system check
python scripts/maintenance.py --all
python scripts/health_check.py --output pre_deploy_health.json
```

### Dependency Updates
```bash
# Safe critical updates only
python scripts/dependency_updater.py --update-critical

# Monthly full update (with backup)
python scripts/dependency_updater.py --update-all
```

## 📊 Exit Codes

All scripts use consistent exit codes:

| Code | Status | Description |
|------|--------|-------------|
| **0** | ✅ Success | All checks passed / No issues found |
| **1** | ⚠️ Warning | Some non-critical issues detected |
| **2** | ❌ Critical | Critical issues requiring immediate attention |

## 🔧 Integration Examples

### GitHub Actions
```yaml
- name: Health Check
  run: python scripts/maintenance.py --health-only
  
- name: Dependency Check
  run: python scripts/dependency_updater.py --check-only
```

### Cron Jobs
```bash
# Daily health check at 6 AM
0 6 * * * cd /path/to/dietly-scraper && python scripts/maintenance.py --health-only

# Weekly maintenance on Sundays at 2 AM
0 2 * * 0 cd /path/to/dietly-scraper && python scripts/maintenance.py --all --report /var/log/dietly_maintenance.log
```

### Docker Integration
```dockerfile
# Add maintenance scripts to container
COPY scripts/ /app/scripts/

# Health check endpoint
HEALTHCHECK --interval=5m --timeout=30s \
  CMD python scripts/health_check.py --quiet || exit 1
```

## 📁 File Structure

```
scripts/
├── maintenance.py          # Master control script
├── health_check.py         # System health verification
├── dependency_updater.py   # Dependency management
├── api_monitor.py          # External API monitoring
├── config_migrator.py      # Configuration migration
├── api_baselines/          # API response baselines (auto-created)
└── README.md              # This documentation
```

## 🔒 Security Notes

- **Credentials**: Scripts use existing config files but never log sensitive data
- **Backups**: All backup files are stored locally in `config/backups/` and `backups/dependencies/`
- **API Testing**: Monitoring uses test credentials that intentionally fail but test endpoint availability

## 🐛 Troubleshooting

### Common Issues

**"Script not found" errors:**
```bash
# Ensure you're in the project root
cd /path/to/dietly-scraper
python scripts/maintenance.py
```

**Permission errors:**
```bash
# Make scripts executable
chmod +x scripts/*.py
```

**Module import errors:**
```bash
# Ensure dependencies are installed
uv sync
```

**Configuration validation failures:**
```bash
# Check and fix configuration
python scripts/config_migrator.py --validate
```

### Debug Mode
Add `--debug` or check individual script outputs:
```bash
python scripts/health_check.py --output debug_health.json
cat debug_health.json | jq '.checks[] | select(.success == false)'
```

## 📈 Monitoring Integration

### Log Aggregation
Scripts generate structured logs that can be integrated with:
- **ELK Stack**: For log aggregation and visualization
- **Grafana**: For metrics and alerting
- **Prometheus**: For metrics collection

### Alerting
Exit codes can trigger alerts in:
- **Nagios/Icinga**: System monitoring
- **PagerDuty**: Incident management
- **Slack/Discord**: Team notifications

---

**💡 Pro Tip**: Run `python scripts/maintenance.py --help` for comprehensive usage information! 