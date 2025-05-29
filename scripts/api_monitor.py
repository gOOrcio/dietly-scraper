#!/usr/bin/env python3
"""
API Monitor for Dietly Scraper

This script monitors external APIs for breaking changes by testing endpoints
and comparing response structures against known baselines.
"""
import asyncio
import json
import logging
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class APIEndpoint:
    """Represents an API endpoint to monitor."""
    
    def __init__(self, name: str, url: str, method: str = "GET", headers: Dict = None, data: Any = None):
        self.name = name
        self.url = url
        self.method = method
        self.headers = headers or {}
        self.data = data


class APIMonitor:
    """Monitors external APIs for breaking changes."""
    
    def __init__(self, baselines_dir: Path = None):
        self.baselines_dir = baselines_dir or Path("scripts/api_baselines")
        self.baselines_dir.mkdir(exist_ok=True)
        
        # Define endpoints to monitor
        self.endpoints = [
            APIEndpoint(
                name="dietly_login",
                url="https://dietly.pl/api/auth/login",
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data="username=test&password=test"  # This will fail but tests endpoint availability
            ),
            APIEndpoint(
                name="dietly_profile_orders",
                url="https://dietly.pl/api/profile/profile-order/active-ids",
                headers={
                    "Accept": "*/*",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty"
                }
            ),
            APIEndpoint(
                name="fitatu_api_base",
                url="https://pl-pl.fitatu.com/api/login",
                method="POST",
                headers={
                    "Accept": "application/json; version=v3",
                    "Content-Type": "application/json;charset=utf-8",
                    "API-Key": "FITATU-MOBILE-APP"
                },
                data=json.dumps({"_username": "test", "_password": "test"})
            )
        ]
    
    async def test_endpoint(self, endpoint: APIEndpoint) -> Dict:
        """Test a single endpoint and return results."""
        result = {
            "name": endpoint.name,
            "url": endpoint.url,
            "method": endpoint.method,
            "timestamp": datetime.now().isoformat(),
            "status": "unknown",
            "status_code": None,
            "response_headers": {},
            "response_structure": {},
            "error": None,
            "available": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if endpoint.method.upper() == "POST":
                    response = await client.post(
                        endpoint.url,
                        headers=endpoint.headers,
                        data=endpoint.data if isinstance(endpoint.data, str) else None,
                        json=endpoint.data if isinstance(endpoint.data, dict) else None
                    )
                else:
                    response = await client.get(endpoint.url, headers=endpoint.headers)
                
                result["status_code"] = response.status_code
                result["response_headers"] = dict(response.headers)
                result["available"] = True
                
                # Try to parse JSON response
                try:
                    json_data = response.json()
                    result["response_structure"] = self._analyze_structure(json_data)
                except:
                    # Not JSON or invalid JSON
                    result["response_structure"] = {
                        "type": "non_json",
                        "content_type": response.headers.get("content-type", "unknown"),
                        "size": len(response.content)
                    }
                
                # Determine status based on response
                if response.status_code < 500:
                    result["status"] = "accessible"
                else:
                    result["status"] = "server_error"
                    
                logging.info(f"✅ {endpoint.name}: HTTP {response.status_code} - {result['status']}")
                
        except httpx.TimeoutException:
            result["status"] = "timeout"
            result["error"] = "Request timeout"
            logging.warning(f"⏰ {endpoint.name}: Timeout")
            
        except httpx.ConnectError:
            result["status"] = "connection_error"
            result["error"] = "Connection failed"
            logging.error(f"❌ {endpoint.name}: Connection failed")
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logging.error(f"❌ {endpoint.name}: {e}")
        
        return result
    
    def _analyze_structure(self, data: Any, max_depth: int = 3, current_depth: int = 0) -> Dict:
        """Analyze the structure of API response data."""
        if current_depth >= max_depth:
            return {"type": "truncated", "original_type": type(data).__name__}
        
        if data is None:
            return {"type": "null"}
        elif isinstance(data, bool):
            return {"type": "boolean"}
        elif isinstance(data, int):
            return {"type": "integer"}
        elif isinstance(data, float):
            return {"type": "float"}
        elif isinstance(data, str):
            return {"type": "string", "length": len(data)}
        elif isinstance(data, list):
            structure = {"type": "array", "length": len(data)}
            if data:
                # Analyze first element as representative
                structure["item_structure"] = self._analyze_structure(data[0], max_depth, current_depth + 1)
            return structure
        elif isinstance(data, dict):
            structure = {
                "type": "object",
                "keys": sorted(data.keys()),
                "properties": {}
            }
            # Analyze a few key properties
            for key in sorted(data.keys())[:5]:  # Limit to first 5 keys
                structure["properties"][key] = self._analyze_structure(
                    data[key], max_depth, current_depth + 1
                )
            return structure
        else:
            return {"type": "unknown", "python_type": type(data).__name__}
    
    def _structure_hash(self, structure: Dict) -> str:
        """Generate a hash of the response structure for comparison."""
        # Create a normalized version for hashing
        normalized = json.dumps(structure, sort_keys=True)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def save_baseline(self, endpoint_name: str, result: Dict) -> None:
        """Save current result as baseline for future comparisons."""
        baseline_file = self.baselines_dir / f"{endpoint_name}_baseline.json"
        
        baseline = {
            "created": datetime.now().isoformat(),
            "endpoint": endpoint_name,
            "structure": result["response_structure"],
            "structure_hash": self._structure_hash(result["response_structure"]),
            "status_code": result["status_code"],
            "headers": result["response_headers"]
        }
        
        with open(baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)
        
        logging.info(f"💾 Saved baseline for {endpoint_name}")
    
    def load_baseline(self, endpoint_name: str) -> Optional[Dict]:
        """Load baseline for comparison."""
        baseline_file = self.baselines_dir / f"{endpoint_name}_baseline.json"
        
        if not baseline_file.exists():
            return None
        
        try:
            with open(baseline_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load baseline for {endpoint_name}: {e}")
            return None
    
    def compare_with_baseline(self, result: Dict) -> Dict:
        """Compare current result with saved baseline."""
        endpoint_name = result["name"]
        baseline = self.load_baseline(endpoint_name)
        
        comparison = {
            "endpoint": endpoint_name,
            "has_baseline": baseline is not None,
            "structure_changed": False,
            "status_code_changed": False,
            "breaking_changes": [],
            "warnings": [],
            "info": []
        }
        
        if not baseline:
            comparison["info"].append("No baseline available - this is the first check")
            return comparison
        
        # Compare structure
        current_hash = self._structure_hash(result["response_structure"])
        baseline_hash = baseline["structure_hash"]
        
        if current_hash != baseline_hash:
            comparison["structure_changed"] = True
            comparison["breaking_changes"].append({
                "type": "structure_change",
                "message": "API response structure has changed",
                "baseline_structure": baseline["structure"],
                "current_structure": result["response_structure"]
            })
        
        # Compare status code
        if result["status_code"] != baseline["status_code"]:
            comparison["status_code_changed"] = True
            severity = "breaking_changes" if result["status_code"] and result["status_code"] >= 500 else "warnings"
            comparison[severity].append({
                "type": "status_code_change",
                "message": f"Status code changed from {baseline['status_code']} to {result['status_code']}",
                "baseline_code": baseline["status_code"],
                "current_code": result["status_code"]
            })
        
        # Check for new required fields (in case of object structures)
        if (result["response_structure"].get("type") == "object" and 
            baseline["structure"].get("type") == "object"):
            
            baseline_keys = set(baseline["structure"].get("keys", []))
            current_keys = set(result["response_structure"].get("keys", []))
            
            missing_keys = baseline_keys - current_keys
            new_keys = current_keys - baseline_keys
            
            if missing_keys:
                comparison["breaking_changes"].append({
                    "type": "missing_fields",
                    "message": f"Fields removed from API response: {list(missing_keys)}",
                    "missing_fields": list(missing_keys)
                })
            
            if new_keys:
                comparison["info"].append({
                    "type": "new_fields",
                    "message": f"New fields added to API response: {list(new_keys)}",
                    "new_fields": list(new_keys)
                })
        
        return comparison
    
    async def monitor_all_endpoints(self) -> Dict:
        """Monitor all configured endpoints."""
        logging.info("🔍 Starting API monitoring...")
        
        results = []
        comparisons = []
        
        for endpoint in self.endpoints:
            logging.info(f"Testing {endpoint.name}...")
            result = await self.test_endpoint(endpoint)
            results.append(result)
            
            comparison = self.compare_with_baseline(result)
            comparisons.append(comparison)
        
        # Generate summary
        total_endpoints = len(results)
        available_endpoints = len([r for r in results if r["available"]])
        endpoints_with_breaking_changes = len([c for c in comparisons if c["breaking_changes"]])
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_endpoints": total_endpoints,
            "available_endpoints": available_endpoints,
            "endpoints_with_breaking_changes": endpoints_with_breaking_changes,
            "overall_status": "healthy" if endpoints_with_breaking_changes == 0 else "issues_detected",
            "results": results,
            "comparisons": comparisons
        }
        
        return summary
    
    def generate_report(self, summary: Dict) -> str:
        """Generate a human-readable report."""
        report = []
        report.append("🔍 API MONITORING REPORT")
        report.append("=" * 50)
        report.append(f"Timestamp: {summary['timestamp']}")
        report.append(f"Overall Status: {summary['overall_status'].upper()}")
        report.append(f"Available Endpoints: {summary['available_endpoints']}/{summary['total_endpoints']}")
        
        if summary['endpoints_with_breaking_changes'] > 0:
            report.append(f"⚠️ Endpoints with Breaking Changes: {summary['endpoints_with_breaking_changes']}")
        
        report.append("")
        report.append("ENDPOINT DETAILS:")
        report.append("-" * 30)
        
        for i, result in enumerate(summary['results']):
            comparison = summary['comparisons'][i]
            
            status_icon = "✅" if result["available"] else "❌"
            report.append(f"{status_icon} {result['name']}")
            report.append(f"   URL: {result['url']}")
            report.append(f"   Status: {result['status']} (HTTP {result['status_code']})")
            
            if comparison['breaking_changes']:
                report.append("   🚨 BREAKING CHANGES:")
                for change in comparison['breaking_changes']:
                    report.append(f"      - {change['message']}")
            
            if comparison['warnings']:
                report.append("   ⚠️ WARNINGS:")
                for warning in comparison['warnings']:
                    report.append(f"      - {warning['message']}")
            
            report.append("")
        
        return "\n".join(report)


async def main():
    """Main entry point for API monitor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Dietly Scraper API Monitor")
    parser.add_argument("--save-baselines", action="store_true", help="Save current responses as baselines")
    parser.add_argument("--output", help="Save monitoring report to JSON file")
    parser.add_argument("--report", help="Save human-readable report to text file")
    parser.add_argument("--baselines-dir", default="scripts/api_baselines", help="Directory for baseline files")
    
    args = parser.parse_args()
    
    monitor = APIMonitor(Path(args.baselines_dir))
    summary = await monitor.monitor_all_endpoints()
    
    # Save baselines if requested
    if args.save_baselines:
        for result in summary['results']:
            if result['available']:
                monitor.save_baseline(result['name'], result)
        logging.info("💾 Baselines updated")
    
    # Generate and display report
    report = monitor.generate_report(summary)
    print(report)
    
    # Save outputs
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2)
        logging.info(f"Monitoring data saved to {args.output}")
    
    if args.report:
        with open(args.report, 'w') as f:
            f.write(report)
        logging.info(f"Report saved to {args.report}")
    
    # Exit with appropriate code
    exit_code = 0 if summary['overall_status'] == 'healthy' else 1
    if summary['endpoints_with_breaking_changes'] > 0:
        exit_code = 2  # Critical issues
    
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main()) 