#!/usr/bin/env python3
"""
Configuration Migrator for Dietly Scraper

This script handles configuration migrations when the structure changes.
Includes version tracking, automatic backups, and validation.
"""
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml
from pydantic import ValidationError

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config_model import SitesConfiguration, UsersConfiguration

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class ConfigMigration:
    """Represents a single configuration migration."""
    
    def __init__(self, version: str, description: str, migrate_func):
        self.version = version
        self.description = description
        self.migrate_func = migrate_func


class ConfigMigrator:
    """Handles configuration migrations and versioning."""
    
    CURRENT_VERSION = "1.2.0"
    
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path("config")
        self.backup_dir = self.config_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Define available migrations
        self.migrations = [
            ConfigMigration("1.0.0", "Initial configuration", self._migrate_to_1_0_0),
            ConfigMigration("1.1.0", "Add API URL separation", self._migrate_to_1_1_0),
            ConfigMigration("1.2.0", "Add headless browser option", self._migrate_to_1_2_0),
        ]
    
    def get_current_version(self) -> str:
        """Get the current configuration version."""
        version_file = self.config_dir / ".version"
        
        if not version_file.exists():
            return "0.0.0"  # Pre-versioning
        
        try:
            return version_file.read_text().strip()
        except Exception:
            return "0.0.0"
    
    def set_version(self, version: str) -> None:
        """Set the configuration version."""
        version_file = self.config_dir / ".version"
        version_file.write_text(version)
        logging.info(f"Updated configuration version to {version}")
    
    def create_backup(self, reason: str = "migration") -> str:
        """Create a backup of current configuration."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{reason}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(exist_ok=True)
        
        # Backup all config files
        for config_file in self.config_dir.glob("*.yaml"):
            if config_file.name != "backups":
                shutil.copy2(config_file, backup_path / config_file.name)
        
        # Backup version file if exists
        version_file = self.config_dir / ".version"
        if version_file.exists():
            shutil.copy2(version_file, backup_path / ".version")
        
        logging.info(f"Created backup: {backup_path}")
        return backup_name
    
    def restore_backup(self, backup_name: str) -> bool:
        """Restore configuration from backup."""
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            logging.error(f"Backup not found: {backup_name}")
            return False
        
        try:
            # Restore all files from backup
            for backup_file in backup_path.glob("*"):
                if backup_file.is_file():
                    target_file = self.config_dir / backup_file.name
                    shutil.copy2(backup_file, target_file)
            
            logging.info(f"Restored configuration from backup: {backup_name}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to restore backup: {e}")
            return False
    
    def list_backups(self) -> List[str]:
        """List available backups."""
        backups = []
        for backup_dir in self.backup_dir.glob("backup_*"):
            if backup_dir.is_dir():
                backups.append(backup_dir.name)
        return sorted(backups, reverse=True)
    
    def _migrate_to_1_0_0(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Migration to version 1.0.0 - initial structure."""
        # This is the baseline - no changes needed
        return config
    
    def _migrate_to_1_1_0(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Migration to version 1.1.0 - separate API URLs."""
        # Check if this is a sites.yaml file
        if "dietly" in config and "fitatu" in config:
            # Add separate API URLs if they don't exist
            if "api_url" not in config.get("dietly", {}):
                config["dietly"]["api_url"] = config["dietly"]["base_url"] + "/api"
            
            if "api_url" not in config.get("fitatu", {}):
                config["fitatu"]["api_url"] = "https://pl-pl.fitatu.com/api"
            
            logging.info("Added separate API URLs to sites configuration")
        
        return config
    
    def _migrate_to_1_2_0(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Migration to version 1.2.0 - add headless browser option."""
        # Check if this is a users.yaml file
        if "users" in config:
            for user in config["users"]:
                # Add headless option to fitatu_credentials if not present
                if "fitatu_credentials" in user:
                    if "headless" not in user["fitatu_credentials"]:
                        user["fitatu_credentials"]["headless"] = True
                        logging.info(f"Added headless option for user: {user.get('name', 'unknown')}")
        
        return config
    
    def migrate_file(self, file_path: Path, target_version: str) -> bool:
        """Migrate a single configuration file."""
        if not file_path.exists():
            logging.warning(f"File not found: {file_path}")
            return True  # Nothing to migrate
        
        try:
            # Load current configuration
            with open(file_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config:
                logging.warning(f"Empty or invalid file: {file_path}")
                return True
            
            current_version = self.get_current_version()
            
            # Apply migrations
            for migration in self.migrations:
                if (self._version_compare(current_version, migration.version) < 0 and
                    self._version_compare(migration.version, target_version) <= 0):
                    
                    logging.info(f"Applying migration {migration.version}: {migration.description}")
                    config = migration.migrate_func(config)
            
            # Write updated configuration
            with open(file_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            logging.info(f"Successfully migrated: {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to migrate {file_path}: {e}")
            return False
    
    def _version_compare(self, version1: str, version2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1."""
        def version_tuple(v):
            return tuple(map(int, v.split('.')))
        
        v1_tuple = version_tuple(version1)
        v2_tuple = version_tuple(version2)
        
        if v1_tuple < v2_tuple:
            return -1
        elif v1_tuple > v2_tuple:
            return 1
        else:
            return 0
    
    def validate_configuration(self) -> bool:
        """Validate configuration after migration."""
        try:
            sites_file = self.config_dir / "sites.yaml"
            users_file = self.config_dir / "users.yaml"
            
            # Validate sites configuration
            if sites_file.exists():
                sites_config = SitesConfiguration.load_from_file(str(sites_file))
                logging.info("✅ Sites configuration is valid")
            
            # Validate users configuration
            if users_file.exists():
                users_config = UsersConfiguration.load_from_file(str(users_file))
                logging.info(f"✅ Users configuration is valid ({len(users_config.users)} users)")
            
            return True
            
        except ValidationError as e:
            logging.error(f"❌ Configuration validation failed: {e}")
            return False
        except Exception as e:
            logging.error(f"❌ Unexpected validation error: {e}")
            return False
    
    def migrate_all(self, target_version: str = None, dry_run: bool = False) -> bool:
        """Migrate all configuration files."""
        target_version = target_version or self.CURRENT_VERSION
        current_version = self.get_current_version()
        
        if self._version_compare(current_version, target_version) >= 0:
            logging.info(f"Configuration is already at version {current_version} (target: {target_version})")
            return True
        
        logging.info(f"Migrating configuration from {current_version} to {target_version}")
        
        if dry_run:
            logging.info("🔍 DRY RUN - No changes will be made")
            
            # Simulate migration for each file
            for config_file in self.config_dir.glob("*.yaml"):
                logging.info(f"Would migrate: {config_file}")
            
            return True
        
        # Create backup before migration
        backup_name = self.create_backup("migration")
        
        try:
            # Migrate configuration files
            config_files = list(self.config_dir.glob("*.yaml"))
            if not config_files:
                logging.warning("No configuration files found to migrate")
                return True
            
            all_successful = True
            for config_file in config_files:
                if not self.migrate_file(config_file, target_version):
                    all_successful = False
            
            if all_successful:
                # Update version
                self.set_version(target_version)
                
                # Validate configuration
                if self.validate_configuration():
                    logging.info("🎉 Migration completed successfully")
                    return True
                else:
                    logging.error("Migration completed but validation failed")
                    return False
            else:
                logging.error("Some files failed to migrate")
                return False
                
        except Exception as e:
            logging.error(f"Migration failed: {e}")
            logging.info(f"Restoring backup: {backup_name}")
            self.restore_backup(backup_name)
            return False
    
    def generate_migration_report(self) -> Dict:
        """Generate a report of migration status."""
        current_version = self.get_current_version()
        
        # Find applicable migrations
        applicable_migrations = []
        for migration in self.migrations:
            if self._version_compare(current_version, migration.version) < 0:
                applicable_migrations.append({
                    "version": migration.version,
                    "description": migration.description
                })
        
        # Check configuration files
        config_files = []
        for config_file in self.config_dir.glob("*.yaml"):
            config_files.append({
                "name": config_file.name,
                "exists": config_file.exists(),
                "size": config_file.stat().st_size if config_file.exists() else 0,
                "modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat() if config_file.exists() else None
            })
        
        return {
            "current_version": current_version,
            "latest_version": self.CURRENT_VERSION,
            "needs_migration": len(applicable_migrations) > 0,
            "applicable_migrations": applicable_migrations,
            "config_files": config_files,
            "backups": self.list_backups()[:5],  # Show last 5 backups
            "timestamp": datetime.now().isoformat()
        }


def main():
    """Main entry point for configuration migrator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Dietly Scraper Configuration Migrator")
    parser.add_argument("--migrate", action="store_true", help="Perform migration")
    parser.add_argument("--target-version", help="Target version for migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated")
    parser.add_argument("--validate", action="store_true", help="Validate current configuration")
    parser.add_argument("--backup", help="Create a backup with custom name")
    parser.add_argument("--restore", help="Restore from backup")
    parser.add_argument("--list-backups", action="store_true", help="List available backups")
    parser.add_argument("--report", help="Save migration report to JSON file")
    parser.add_argument("--config-dir", default="config", help="Configuration directory")
    
    args = parser.parse_args()
    
    migrator = ConfigMigrator(Path(args.config_dir))
    
    # Handle restore operation
    if args.restore:
        success = migrator.restore_backup(args.restore)
        sys.exit(0 if success else 1)
    
    # Handle backup creation
    if args.backup:
        migrator.create_backup(args.backup)
        sys.exit(0)
    
    # List backups
    if args.list_backups:
        backups = migrator.list_backups()
        if backups:
            print("Available backups:")
            for backup in backups:
                print(f"  - {backup}")
        else:
            print("No backups found")
        sys.exit(0)
    
    # Validate configuration
    if args.validate:
        success = migrator.validate_configuration()
        sys.exit(0 if success else 1)
    
    # Generate report
    report = migrator.generate_migration_report()
    
    # Display current status
    print("📋 CONFIGURATION STATUS")
    print("=" * 40)
    print(f"Current Version: {report['current_version']}")
    print(f"Latest Version: {report['latest_version']}")
    print(f"Needs Migration: {'Yes' if report['needs_migration'] else 'No'}")
    
    if report['applicable_migrations']:
        print(f"\nAvailable Migrations ({len(report['applicable_migrations'])}):")
        for migration in report['applicable_migrations']:
            print(f"  → {migration['version']}: {migration['description']}")
    
    print(f"\nConfiguration Files ({len(report['config_files'])}):")
    for file_info in report['config_files']:
        status = "✅" if file_info['exists'] else "❌"
        print(f"  {status} {file_info['name']}")
    
    # Save report if requested
    if args.report:
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        logging.info(f"Report saved to {args.report}")
    
    # Perform migration
    if args.migrate:
        success = migrator.migrate_all(args.target_version, args.dry_run)
        sys.exit(0 if success else 1)
    elif report['needs_migration']:
        print(f"\n⚠️ Migration available. Run with --migrate to update to version {report['latest_version']}")
        sys.exit(1)
    else:
        print("\n🎉 Configuration is up to date!")
        sys.exit(0)


if __name__ == "__main__":
    main() 