#!/usr/bin/env python3
"""
Maintenance Master Script for Dietly Scraper

This script provides a unified interface to all maintenance tools:
- Health checks
- Dependency updates  
- API monitoring
- Configuration migrations
"""
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class MaintenanceRunner:
    """Runs comprehensive maintenance tasks."""
    
    def __init__(self, scripts_dir: Path = None):
        self.scripts_dir = scripts_dir or Path("scripts")
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
        
        # Define available maintenance tasks
        self.tasks = {
            "health": {
                "script": "health_check.py",
                "description": "Run comprehensive health checks",
                "critical": True
            },
            "dependencies": {
                "script": "dependency_updater.py", 
                "description": "Check and update dependencies",
                "critical": False
            },
            "api_monitor": {
                "script": "api_monitor.py",
                "description": "Monitor external APIs for changes",
                "critical": False
            },
            "config_migration": {
                "script": "config_migrator.py",
                "description": "Handle configuration migrations",
                "critical": True
            }
        }
    
    async def run_task(self, task_name: str, args: List[str] = None) -> Dict:
        """Run a single maintenance task."""
        if task_name not in self.tasks:
            raise ValueError(f"Unknown task: {task_name}")
        
        task = self.tasks[task_name]
        script_path = self.scripts_dir / task["script"]
        
        if not script_path.exists():
            return {
                "task": task_name,
                "success": False,
                "error": f"Script not found: {script_path}",
                "output": "",
                "exit_code": 1
            }
        
        # Prepare command
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
        
        logging.info(f"🔧 Running {task_name}: {task['description']}")
        
        try:
            # Run the script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            success = result.returncode == 0
            status_icon = "✅" if success else "❌"
            
            logging.info(f"{status_icon} {task_name} completed with exit code {result.returncode}")
            
            return {
                "task": task_name,
                "success": success,
                "exit_code": result.returncode,
                "output": result.stdout,
                "error": result.stderr,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"❌ Failed to run {task_name}: {e}")
            return {
                "task": task_name,
                "success": False,
                "error": str(e),
                "output": "",
                "exit_code": 1,
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_all_tasks(self, include_optional: bool = False) -> Dict:
        """Run all maintenance tasks."""
        logging.info("🛠️ Starting comprehensive maintenance run...")
        
        results = []
        critical_failures = 0
        
        for task_name, task_info in self.tasks.items():
            # Skip optional tasks if not requested
            if not include_optional and not task_info["critical"]:
                logging.info(f"⏭️ Skipping optional task: {task_name}")
                continue
            
            result = await self.run_task(task_name)
            results.append(result)
            
            if not result["success"] and task_info["critical"]:
                critical_failures += 1
        
        # Generate summary
        total_tasks = len(results)
        successful_tasks = len([r for r in results if r["success"]])
        failed_tasks = total_tasks - successful_tasks
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": total_tasks,
            "successful": successful_tasks,
            "failed": failed_tasks,
            "critical_failures": critical_failures,
            "overall_status": "healthy" if critical_failures == 0 else "critical_issues",
            "results": results
        }
        
        logging.info("=" * 50)
        logging.info("🛠️ MAINTENANCE SUMMARY")
        logging.info("=" * 50)
        logging.info(f"Overall Status: {summary['overall_status'].upper()}")
        logging.info(f"Tasks Completed: {successful_tasks}/{total_tasks}")
        
        if critical_failures > 0:
            logging.error(f"🚨 {critical_failures} critical failures detected!")
        
        return summary
    
    def generate_report(self, summary: Dict) -> str:
        """Generate a detailed maintenance report."""
        report = []
        report.append("🛠️ DIETLY SCRAPER MAINTENANCE REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {summary['timestamp']}")
        report.append(f"Overall Status: {summary['overall_status'].upper()}")
        report.append("")
        
        # Summary stats
        report.append("📊 SUMMARY")
        report.append("-" * 20)
        report.append(f"Total Tasks: {summary['total_tasks']}")
        report.append(f"Successful: {summary['successful']}")
        report.append(f"Failed: {summary['failed']}")
        report.append(f"Critical Failures: {summary['critical_failures']}")
        report.append("")
        
        # Individual task results
        report.append("📋 TASK DETAILS")
        report.append("-" * 20)
        
        for result in summary['results']:
            task_info = self.tasks.get(result['task'], {})
            is_critical = task_info.get('critical', False)
            
            status_icon = "✅" if result['success'] else "❌"
            critical_icon = "🔴" if is_critical else "🟡"
            
            report.append(f"{status_icon} {result['task'].upper()} {critical_icon}")
            report.append(f"   Description: {task_info.get('description', 'Unknown')}")
            report.append(f"   Status: {'SUCCESS' if result['success'] else 'FAILED'}")
            report.append(f"   Exit Code: {result['exit_code']}")
            
            if result['error']:
                report.append(f"   Error: {result['error'][:100]}...")
            
            # Show key output snippets
            if result['output']:
                lines = result['output'].split('\n')
                important_lines = [line for line in lines if any(
                    keyword in line.lower() for keyword in 
                    ['error', 'warning', 'failed', 'success', 'completed', '✅', '❌', '⚠️']
                )][:3]
                
                if important_lines:
                    report.append("   Key Output:")
                    for line in important_lines:
                        report.append(f"     {line.strip()}")
            
            report.append("")
        
        # Recommendations
        report.append("💡 RECOMMENDATIONS")
        report.append("-" * 20)
        
        if summary['critical_failures'] > 0:
            report.append("🚨 CRITICAL: Fix critical failures before running production sync")
        
        if summary['failed'] > 0:
            report.append("⚠️ Review failed tasks and address issues")
        
        if summary['overall_status'] == 'healthy':
            report.append("✅ System is healthy - ready for operation")
        
        report.append("")
        report.append("🔗 For detailed logs, check individual task outputs above")
        
        return "\n".join(report)
    
    async def run_specific_checks(self, categories: List[str]) -> Dict:
        """Run specific categories of maintenance tasks."""
        category_mapping = {
            "health": ["health"],
            "dependencies": ["dependencies"],
            "api": ["api_monitor"],
            "config": ["config_migration"],
            "all": list(self.tasks.keys())
        }
        
        tasks_to_run = []
        for category in categories:
            if category in category_mapping:
                tasks_to_run.extend(category_mapping[category])
            elif category in self.tasks:
                tasks_to_run.append(category)
            else:
                logging.warning(f"Unknown category/task: {category}")
        
        # Remove duplicates while preserving order
        tasks_to_run = list(dict.fromkeys(tasks_to_run))
        
        logging.info(f"🎯 Running specific maintenance tasks: {', '.join(tasks_to_run)}")
        
        results = []
        for task_name in tasks_to_run:
            result = await self.run_task(task_name)
            results.append(result)
        
        # Generate summary
        total_tasks = len(results)
        successful_tasks = len([r for r in results if r["success"]])
        failed_tasks = total_tasks - successful_tasks
        critical_failures = len([r for r in results if not r["success"] and self.tasks[r["task"]]["critical"]])
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": total_tasks,
            "successful": successful_tasks,
            "failed": failed_tasks,
            "critical_failures": critical_failures,
            "overall_status": "healthy" if critical_failures == 0 else "critical_issues",
            "results": results
        }


async def main():
    """Main entry point for maintenance script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Dietly Scraper Maintenance Manager")
    
    # Task selection
    parser.add_argument("--all", action="store_true", help="Run all maintenance tasks")
    parser.add_argument("--critical-only", action="store_true", help="Run only critical tasks")
    parser.add_argument("--include-optional", action="store_true", help="Include optional tasks")
    parser.add_argument("--tasks", nargs="+", help="Run specific tasks or categories")
    
    # Task-specific options
    parser.add_argument("--health-only", action="store_true", help="Run health check only")
    parser.add_argument("--deps-check", action="store_true", help="Check dependencies only")
    parser.add_argument("--api-monitor", action="store_true", help="Monitor APIs only")
    parser.add_argument("--config-check", action="store_true", help="Check configuration only")
    
    # Output options
    parser.add_argument("--report", help="Save detailed report to file")
    parser.add_argument("--json-output", help="Save results as JSON")
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")
    
    # Specific task arguments (passed through)
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode where applicable")
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    runner = MaintenanceRunner()
    
    # Determine what to run
    if args.health_only:
        summary = await runner.run_specific_checks(["health"])
    elif args.deps_check:
        task_args = ["--check-only"] if args.dry_run else []
        result = await runner.run_task("dependencies", task_args)
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": 1,
            "successful": 1 if result["success"] else 0,
            "failed": 0 if result["success"] else 1,
            "critical_failures": 0,
            "overall_status": "healthy" if result["success"] else "issues",
            "results": [result]
        }
    elif args.api_monitor:
        summary = await runner.run_specific_checks(["api_monitor"])
    elif args.config_check:
        summary = await runner.run_specific_checks(["config"])
    elif args.tasks:
        summary = await runner.run_specific_checks(args.tasks)
    elif args.all or args.critical_only:
        summary = await runner.run_all_tasks(include_optional=args.include_optional or args.all)
    else:
        # Default: run critical tasks only
        summary = await runner.run_all_tasks(include_optional=False)
    
    # Generate and display report
    if not args.quiet:
        report = runner.generate_report(summary)
        print(report)
    
    # Save outputs
    if args.report:
        report = runner.generate_report(summary)
        with open(args.report, 'w') as f:
            f.write(report)
        logging.info(f"Report saved to {args.report}")
    
    if args.json_output:
        with open(args.json_output, 'w') as f:
            json.dump(summary, f, indent=2)
        logging.info(f"JSON output saved to {args.json_output}")
    
    # Exit with appropriate code
    if summary['critical_failures'] > 0:
        sys.exit(2)  # Critical issues
    elif summary['failed'] > 0:
        sys.exit(1)  # Some failures
    else:
        sys.exit(0)  # All good


if __name__ == "__main__":
    asyncio.run(main()) 