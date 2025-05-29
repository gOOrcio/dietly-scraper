#!/usr/bin/env python3
"""
Health Check Script for Dietly Scraper

This script performs comprehensive health checks to validate the system is working correctly.
Useful for troubleshooting and maintenance.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from pydantic import ValidationError

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clients.dietly_client import DietlyClient, DietlyClientAPIError, DietlyNoActivePlanError
from src.clients.fitatu_client import FitatuClient
from src.models.config_model import SitesConfiguration, UsersConfiguration
from src.utils.constants import LOG_FORMAT
from src.utils.utils import get_current_date_iso

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class HealthCheckResult:
    """Represents the result of a health check operation."""
    
    def __init__(self, name: str, success: bool, message: str, details: Optional[Dict] = None):
        self.name = name
        self.success = success
        self.message = message
        self.details = details or {}


class HealthChecker:
    """Comprehensive health checker for Dietly Scraper."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.results: List[HealthCheckResult] = []
        
    def add_result(self, result: HealthCheckResult):
        """Add a health check result."""
        self.results.append(result)
        icon = "✅" if result.success else "❌"
        logging.info(f"{icon} {result.name}: {result.message}")
        
    def check_config_files(self) -> None:
        """Check if configuration files exist and are valid."""
        sites_file = self.config_dir / "sites.yaml"
        users_file = self.config_dir / "users.yaml"
        
        # Check sites.yaml
        if not sites_file.exists():
            self.add_result(HealthCheckResult(
                "Config Files", False, "sites.yaml not found",
                {"missing_file": str(sites_file)}
            ))
            return
            
        # Check users.yaml
        if not users_file.exists():
            self.add_result(HealthCheckResult(
                "Config Files", False, "users.yaml not found",
                {"missing_file": str(users_file)}
            ))
            return
            
        # Validate YAML syntax
        try:
            with open(sites_file, 'r') as f:
                yaml.safe_load(f)
            with open(users_file, 'r') as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.add_result(HealthCheckResult(
                "Config Files", False, f"Invalid YAML syntax: {e}"
            ))
            return
            
        self.add_result(HealthCheckResult(
            "Config Files", True, "Configuration files exist and have valid syntax"
        ))
    
    def check_config_validation(self) -> Tuple[Optional[SitesConfiguration], Optional[UsersConfiguration]]:
        """Validate configuration models."""
        sites_config = None
        users_config = None
        
        try:
            sites_config = SitesConfiguration.load_from_file(str(self.config_dir / "sites.yaml"))
            self.add_result(HealthCheckResult(
                "Sites Config", True, "Sites configuration is valid"
            ))
        except (FileNotFoundError, ValidationError) as e:
            self.add_result(HealthCheckResult(
                "Sites Config", False, f"Sites configuration validation failed: {e}"
            ))
            
        try:
            users_config = UsersConfiguration.load_from_file(str(self.config_dir / "users.yaml"))
            user_count = len(users_config.users)
            self.add_result(HealthCheckResult(
                "Users Config", True, f"Users configuration is valid ({user_count} users)",
                {"user_count": user_count}
            ))
        except (FileNotFoundError, ValidationError) as e:
            self.add_result(HealthCheckResult(
                "Users Config", False, f"Users configuration validation failed: {e}"
            ))
            
        return sites_config, users_config
    
    async def check_dietly_connectivity(self, sites: SitesConfiguration, users: UsersConfiguration) -> None:
        """Test Dietly API connectivity for all users."""
        if not sites or not users:
            self.add_result(HealthCheckResult(
                "Dietly Connectivity", False, "Cannot test - invalid configuration"
            ))
            return
            
        total_users = len(users.users)
        successful_logins = 0
        
        for user in users.users:
            try:
                async with DietlyClient(sites.dietly, user.dietly_credentials) as client:
                    await client.login()
                    successful_logins += 1
                    self.add_result(HealthCheckResult(
                        f"Dietly Login ({user.name})", True, "Login successful"
                    ))
            except DietlyClientAPIError as e:
                self.add_result(HealthCheckResult(
                    f"Dietly Login ({user.name})", False, f"Login failed: {e}"
                ))
            except Exception as e:
                self.add_result(HealthCheckResult(
                    f"Dietly Login ({user.name})", False, f"Unexpected error: {e}"
                ))
                
        # Overall connectivity result
        if successful_logins == total_users:
            self.add_result(HealthCheckResult(
                "Dietly Connectivity", True, f"All {total_users} users can connect to Dietly"
            ))
        elif successful_logins > 0:
            self.add_result(HealthCheckResult(
                "Dietly Connectivity", False, f"Only {successful_logins}/{total_users} users can connect"
            ))
        else:
            self.add_result(HealthCheckResult(
                "Dietly Connectivity", False, "No users can connect to Dietly"
            ))
    
    async def check_fitatu_connectivity(self, sites: SitesConfiguration, users: UsersConfiguration) -> None:
        """Test Fitatu API connectivity for all users."""
        if not sites or not users:
            self.add_result(HealthCheckResult(
                "Fitatu Connectivity", False, "Cannot test - invalid configuration"
            ))
            return
            
        total_users = len(users.users)
        successful_logins = 0
        
        for user in users.users:
            try:
                client = FitatuClient(
                    sites_config=sites.fitatu,
                    credentials=user.fitatu_credentials,
                    brand="HealthCheck"
                )
                result = await client.login()
                if result:
                    successful_logins += 1
                    self.add_result(HealthCheckResult(
                        f"Fitatu Login ({user.name})", True, "Login successful"
                    ))
                else:
                    self.add_result(HealthCheckResult(
                        f"Fitatu Login ({user.name})", False, "Login returned no data"
                    ))
            except Exception as e:
                self.add_result(HealthCheckResult(
                    f"Fitatu Login ({user.name})", False, f"Login failed: {e}"
                ))
                
        # Overall connectivity result
        if successful_logins == total_users:
            self.add_result(HealthCheckResult(
                "Fitatu Connectivity", True, f"All {total_users} users can connect to Fitatu"
            ))
        elif successful_logins > 0:
            self.add_result(HealthCheckResult(
                "Fitatu Connectivity", False, f"Only {successful_logins}/{total_users} users can connect"
            ))
        else:
            self.add_result(HealthCheckResult(
                "Fitatu Connectivity", False, "No users can connect to Fitatu"
            ))
    
    async def check_end_to_end_flow(self, sites: SitesConfiguration, users: UsersConfiguration) -> None:
        """Test the complete end-to-end flow for the first user."""
        if not sites or not users or not users.users:
            self.add_result(HealthCheckResult(
                "End-to-End Flow", False, "Cannot test - no valid users"
            ))
            return
            
        user = users.users[0]  # Test with first user
        
        try:
            async with DietlyClient(sites.dietly, user.dietly_credentials) as dietly_client:
                # Test Dietly flow
                try:
                    result = await dietly_client.login_and_get_todays_menu()
                    if result:
                        menu_data, company_name = result
                        self.add_result(HealthCheckResult(
                            "End-to-End Flow", True, 
                            f"Successfully retrieved menu from {company_name} for {user.name}",
                            {"company": company_name, "has_menu": True}
                        ))
                    else:
                        self.add_result(HealthCheckResult(
                            "End-to-End Flow", True, 
                            f"No menu available for {user.name} today (acceptable)",
                            {"has_menu": False}
                        ))
                except DietlyNoActivePlanError:
                    self.add_result(HealthCheckResult(
                        "End-to-End Flow", True, 
                        f"No active meal plan for {user.name} (acceptable)",
                        {"has_plan": False}
                    ))
                except DietlyClientAPIError as e:
                    self.add_result(HealthCheckResult(
                        "End-to-End Flow", False, f"Dietly API error: {e}"
                    ))
        except Exception as e:
            self.add_result(HealthCheckResult(
                "End-to-End Flow", False, f"Unexpected error: {e}"
            ))
    
    def check_environment(self) -> None:
        """Check system environment and dependencies."""
        import sys
        import platform
        
        # Python version check
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if sys.version_info >= (3, 12):
            self.add_result(HealthCheckResult(
                "Python Version", True, f"Python {python_version} (supported)"
            ))
        else:
            self.add_result(HealthCheckResult(
                "Python Version", False, f"Python {python_version} (requires 3.12+)"
            ))
        
        # Platform info
        self.add_result(HealthCheckResult(
            "Platform", True, f"{platform.system()} {platform.release()}"
        ))
        
        # Check required modules
        required_modules = ['httpx', 'playwright', 'pydantic', 'yaml']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            self.add_result(HealthCheckResult(
                "Dependencies", False, f"Missing modules: {', '.join(missing_modules)}"
            ))
        else:
            self.add_result(HealthCheckResult(
                "Dependencies", True, "All required modules are available"
            ))
    
    async def run_all_checks(self) -> Dict:
        """Run all health checks and return summary."""
        logging.info("🏥 Starting comprehensive health check...")
        
        # Basic checks
        self.check_environment()
        self.check_config_files()
        sites_config, users_config = self.check_config_validation()
        
        # Connectivity checks (only if config is valid)
        if sites_config and users_config:
            await self.check_dietly_connectivity(sites_config, users_config)
            await self.check_fitatu_connectivity(sites_config, users_config)
            await self.check_end_to_end_flow(sites_config, users_config)
        
        # Generate summary
        total_checks = len(self.results)
        successful_checks = len([r for r in self.results if r.success])
        failed_checks = total_checks - successful_checks
        
        summary = {
            "timestamp": get_current_date_iso(),
            "total_checks": total_checks,
            "successful": successful_checks,
            "failed": failed_checks,
            "success_rate": round((successful_checks / total_checks) * 100, 1) if total_checks > 0 else 0,
            "overall_status": "HEALTHY" if failed_checks == 0 else "ISSUES_DETECTED",
            "checks": [
                {
                    "name": r.name,
                    "success": r.success,
                    "message": r.message,
                    "details": r.details
                }
                for r in self.results
            ]
        }
        
        logging.info("=" * 50)
        logging.info("🏥 HEALTH CHECK SUMMARY")
        logging.info("=" * 50)
        logging.info(f"Overall Status: {summary['overall_status']}")
        logging.info(f"Success Rate: {summary['success_rate']}% ({successful_checks}/{total_checks})")
        
        if failed_checks > 0:
            logging.warning(f"⚠️ {failed_checks} issues detected - see details above")
            return summary
        else:
            logging.info("🎉 All checks passed - system is healthy!")
            return summary


async def main():
    """Main entry point for health check."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Dietly Scraper Health Check")
    parser.add_argument("--config-dir", default="config", help="Configuration directory path")
    parser.add_argument("--output", help="Save results to JSON file")
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    checker = HealthChecker(args.config_dir)
    summary = await checker.run_all_checks()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2)
        logging.info(f"Results saved to {args.output}")
    
    # Exit with appropriate code
    sys.exit(0 if summary["overall_status"] == "HEALTHY" else 1)


if __name__ == "__main__":
    asyncio.run(main()) 