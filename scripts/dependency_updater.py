#!/usr/bin/env python3
"""
Dependency Updater for Dietly Scraper

This script checks for outdated dependencies and can automatically update them.
Includes safety checks and backup creation.
"""
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class DependencyUpdater:
    """Handles dependency updates for the project."""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.pyproject_file = self.project_root / "pyproject.toml"
        self.uv_lock_file = self.project_root / "uv.lock"
        self.backup_dir = self.project_root / "backups" / "dependencies"
        
    def check_uv_available(self) -> bool:
        """Check if uv package manager is available."""
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                logging.info(f"uv version: {result.stdout.strip()}")
                return True
            return False
        except FileNotFoundError:
            logging.error("uv package manager not found - please install it first")
            return False
    
    def create_backup(self) -> bool:
        """Create backup of current dependency files."""
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup pyproject.toml
            if self.pyproject_file.exists():
                backup_pyproject = self.backup_dir / f"pyproject_backup_{timestamp}.toml"
                backup_pyproject.write_text(self.pyproject_file.read_text())
                logging.info(f"Backed up pyproject.toml to {backup_pyproject}")
            
            # Backup uv.lock
            if self.uv_lock_file.exists():
                backup_lock = self.backup_dir / f"uv_lock_backup_{timestamp}.lock"
                backup_lock.write_text(self.uv_lock_file.read_text())
                logging.info(f"Backed up uv.lock to {backup_lock}")
            
            return True
        except Exception as e:
            logging.error(f"Failed to create backup: {e}")
            return False
    
    def get_outdated_packages(self) -> List[Dict]:
        """Get list of outdated packages."""
        try:
            # Use uv to check for outdated packages
            result = subprocess.run(
                ["uv", "pip", "list", "--outdated", "--format", "json"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0 and result.stdout.strip():
                outdated = json.loads(result.stdout)
                logging.info(f"Found {len(outdated)} outdated packages")
                return outdated
            else:
                logging.info("No outdated packages found")
                return []
                
        except json.JSONDecodeError:
            logging.warning("Could not parse outdated packages output")
            return []
        except Exception as e:
            logging.error(f"Error checking outdated packages: {e}")
            return []
    
    def check_critical_packages(self, packages: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Separate critical packages from regular ones."""
        critical_packages = {
            'httpx', 'playwright', 'pydantic', 'pydantic-core', 
            'asyncio', 'aiohttp', 'urllib3'
        }
        
        critical = []
        regular = []
        
        for pkg in packages:
            if pkg['name'].lower() in critical_packages:
                critical.append(pkg)
            else:
                regular.append(pkg)
        
        return critical, regular
    
    def update_dependencies(self, packages: List[str] = None, dry_run: bool = False) -> bool:
        """Update specified packages or all dependencies."""
        try:
            if dry_run:
                logging.info("🔍 DRY RUN - No actual updates will be performed")
            
            if packages:
                # Update specific packages
                cmd = ["uv", "pip", "install", "--upgrade"] + packages
                action = f"update packages: {', '.join(packages)}"
            else:
                # Update all dependencies
                cmd = ["uv", "sync", "--upgrade"]
                action = "update all dependencies"
            
            if dry_run:
                logging.info(f"Would run: {' '.join(cmd)}")
                return True
            
            logging.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info(f"✅ Successfully updated dependencies")
                if result.stdout:
                    logging.debug(f"Output: {result.stdout}")
                return True
            else:
                logging.error(f"❌ Failed to {action}")
                if result.stderr:
                    logging.error(f"Error: {result.stderr}")
                return False
                
        except Exception as e:
            logging.error(f"Error during update: {e}")
            return False
    
    def verify_health_after_update(self) -> bool:
        """Run health check after dependency update."""
        try:
            health_script = self.project_root / "scripts" / "health_check.py"
            if not health_script.exists():
                logging.warning("Health check script not found - skipping verification")
                return True
            
            logging.info("🏥 Running health check after update...")
            result = subprocess.run(
                [sys.executable, str(health_script), "--quiet"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logging.info("✅ Health check passed after update")
                return True
            else:
                logging.error("❌ Health check failed after update")
                logging.error(f"Health check output: {result.stdout}")
                return False
                
        except Exception as e:
            logging.error(f"Error running health check: {e}")
            return False
    
    def restore_backup(self, timestamp: str = None) -> bool:
        """Restore from backup."""
        try:
            if not timestamp:
                # Find most recent backup
                backups = list(self.backup_dir.glob("pyproject_backup_*.toml"))
                if not backups:
                    logging.error("No backups found")
                    return False
                
                latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
                timestamp = latest_backup.stem.split('_backup_')[1].replace('.toml', '')
            
            pyproject_backup = self.backup_dir / f"pyproject_backup_{timestamp}.toml"
            lock_backup = self.backup_dir / f"uv_lock_backup_{timestamp}.lock"
            
            if pyproject_backup.exists():
                self.pyproject_file.write_text(pyproject_backup.read_text())
                logging.info(f"Restored pyproject.toml from {pyproject_backup}")
            
            if lock_backup.exists():
                self.uv_lock_file.write_text(lock_backup.read_text())
                logging.info(f"Restored uv.lock from {lock_backup}")
            
            # Re-sync dependencies
            subprocess.run(["uv", "sync"], cwd=self.project_root)
            logging.info("Re-synced dependencies from restored files")
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to restore backup: {e}")
            return False
    
    def generate_update_report(self, outdated: List[Dict], updated: List[str] = None) -> Dict:
        """Generate a report of the update process."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_outdated": len(outdated),
            "outdated_packages": outdated,
            "updated_packages": updated or [],
            "update_successful": bool(updated),
            "recommendations": []
        }
        
        # Add recommendations
        critical, regular = self.check_critical_packages(outdated)
        
        if critical:
            report["recommendations"].append({
                "type": "critical_updates",
                "message": f"Consider updating critical packages: {[p['name'] for p in critical]}",
                "packages": critical
            })
        
        if len(outdated) > 10:
            report["recommendations"].append({
                "type": "batch_update",
                "message": "Many packages are outdated - consider a full dependency update",
                "count": len(outdated)
            })
        
        return report


def main():
    """Main entry point for dependency updater."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Dietly Scraper Dependency Updater")
    parser.add_argument("--check-only", action="store_true", help="Only check for updates, don't install")
    parser.add_argument("--update-all", action="store_true", help="Update all dependencies")
    parser.add_argument("--update-critical", action="store_true", help="Update only critical packages")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without doing it")
    parser.add_argument("--restore", help="Restore from backup (specify timestamp or 'latest')")
    parser.add_argument("--report", help="Save update report to JSON file")
    parser.add_argument("--force", action="store_true", help="Skip health checks and confirmations")
    
    args = parser.parse_args()
    
    updater = DependencyUpdater()
    
    # Check if uv is available
    if not updater.check_uv_available():
        sys.exit(1)
    
    # Handle restore operation
    if args.restore:
        timestamp = None if args.restore == "latest" else args.restore
        success = updater.restore_backup(timestamp)
        sys.exit(0 if success else 1)
    
    # Get outdated packages
    outdated = updater.get_outdated_packages()
    
    if not outdated:
        logging.info("🎉 All dependencies are up to date!")
        sys.exit(0)
    
    # Show outdated packages
    critical, regular = updater.check_critical_packages(outdated)
    
    logging.info("📦 OUTDATED PACKAGES:")
    if critical:
        logging.warning(f"🔴 Critical packages ({len(critical)}):")
        for pkg in critical:
            logging.warning(f"  {pkg['name']}: {pkg['version']} → {pkg['latest_version']}")
    
    if regular:
        logging.info(f"🟡 Regular packages ({len(regular)}):")
        for pkg in regular:
            logging.info(f"  {pkg['name']}: {pkg['version']} → {pkg['latest_version']}")
    
    # Exit if only checking
    if args.check_only:
        sys.exit(1 if critical else 0)  # Exit 1 if critical updates needed
    
    # Determine what to update
    packages_to_update = []
    if args.update_critical:
        packages_to_update = [pkg['name'] for pkg in critical]
        action = "critical packages"
    elif args.update_all:
        packages_to_update = None  # Update all
        action = "all dependencies"
    else:
        # Interactive mode
        if critical:
            response = input(f"\n⚠️ Update {len(critical)} critical packages? [y/N]: ")
            if response.lower() in ['y', 'yes']:
                packages_to_update = [pkg['name'] for pkg in critical]
                action = "critical packages"
        
        if not packages_to_update:
            response = input(f"\n📦 Update all {len(outdated)} outdated packages? [y/N]: ")
            if response.lower() in ['y', 'yes']:
                packages_to_update = None
                action = "all dependencies"
    
    if packages_to_update is None or packages_to_update:
        # Create backup before updating
        if not args.dry_run and not updater.create_backup():
            logging.error("Failed to create backup - aborting update")
            sys.exit(1)
        
        # Perform update
        success = updater.update_dependencies(packages_to_update, dry_run=args.dry_run)
        
        if success and not args.dry_run:
            # Verify health after update
            if not args.force:
                health_ok = updater.verify_health_after_update()
                if not health_ok:
                    logging.error("Health check failed - consider restoring backup")
                    response = input("Restore from backup? [y/N]: ")
                    if response.lower() in ['y', 'yes']:
                        updater.restore_backup()
                    sys.exit(1)
            
            logging.info(f"✅ Successfully updated {action}")
        elif not success:
            logging.error(f"❌ Failed to update {action}")
            sys.exit(1)
    
    # Generate report
    if args.report:
        updated_packages = packages_to_update if packages_to_update else [pkg['name'] for pkg in outdated]
        report = updater.generate_update_report(outdated, updated_packages)
        
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        logging.info(f"Update report saved to {args.report}")


if __name__ == "__main__":
    main() 