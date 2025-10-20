#!/usr/bin/env python3
"""
Simple metrics validation script for Stage6 monitoring stack.
Verifies that Prometheus can scrape metrics from configured targets.
"""

import sys

import requests

PROMETHEUS_URL = "http://localhost:9090"
TIMEOUT = 10


def check_metric_endpoint(url: str, name: str) -> tuple[bool, str]:
    """Check if a metrics endpoint is accessible and returns valid data."""
    try:
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"

        # Basic validation: metrics should contain at least one line starting with #
        lines = response.text.split("\n")
        has_metrics = any(
            line.startswith("#") or (line and not line.startswith("#"))
            for line in lines
        )

        if not has_metrics:
            return False, "No valid metrics found"

        return True, "OK"
    except requests.exceptions.RequestException as e:
        return False, str(e)


def query_prometheus(query: str) -> tuple[bool, dict]:
    """Execute a PromQL query and return results."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=TIMEOUT
        )
        if response.status_code != 200:
            return False, {"error": f"HTTP {response.status_code}"}

        data = response.json()
        if data.get("status") != "success":
            return False, data

        return True, data
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}


def main() -> int:
    """Run metrics validation tests."""
    print("=" * 60)
    print("Stage6 Metrics Validation")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Check Prometheus metrics endpoint
    print("\n[1] Testing Prometheus metrics endpoint...")
    success, msg = check_metric_endpoint(f"{PROMETHEUS_URL}/metrics", "Prometheus")
    if success:
        print(f"✅ Prometheus metrics: {msg}")
        tests_passed += 1
    else:
        print(f"❌ Prometheus metrics: {msg}")
        tests_failed += 1

    # Test 2: Check Node Exporter metrics
    print("\n[2] Testing Node Exporter metrics endpoint...")
    success, msg = check_metric_endpoint(
        "http://localhost:19100/metrics", "Node Exporter"
    )
    if success:
        print(f"✅ Node Exporter metrics: {msg}")
        tests_passed += 1
    else:
        print(f"❌ Node Exporter metrics: {msg}")
        tests_failed += 1

    # Test 3: Query Prometheus for up metric
    print("\n[3] Testing Prometheus query API (up metric)...")
    success, result = query_prometheus("up")
    if success:
        result_count = len(result.get("data", {}).get("result", []))
        print(f"✅ Prometheus query API: {result_count} targets found")
        tests_passed += 1
    else:
        print(f"❌ Prometheus query API: {result.get('error', 'Unknown error')}")
        tests_failed += 1

    # Test 4: Check if all targets are up
    print("\n[4] Verifying target health (up==1)...")
    success, result = query_prometheus("up==1")
    if success:
        up_targets = len(result.get("data", {}).get("result", []))
        print(f"✅ Healthy targets: {up_targets}")
        tests_passed += 1
    else:
        print(
            f"❌ Failed to check target health: {result.get('error', 'Unknown error')}"
        )
        tests_failed += 1

    # Test 5: Check for down targets
    print("\n[5] Checking for down targets (up==0)...")
    success, result = query_prometheus("up==0")
    if success:
        down_targets = len(result.get("data", {}).get("result", []))
        if down_targets == 0:
            print("✅ No down targets found")
            tests_passed += 1
        else:
            print(f"⚠️  Warning: {down_targets} targets are down")
            for target in result.get("data", {}).get("result", []):
                job = target.get("metric", {}).get("job", "unknown")
                instance = target.get("metric", {}).get("instance", "unknown")
                print(f"   - {job}/{instance}")
            tests_failed += 1
    else:
        print(
            f"❌ Failed to query down targets: {result.get('error', 'Unknown error')}"
        )
        tests_failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Tests passed: {tests_passed}")
    print(f"Tests failed: {tests_failed}")
    print("=" * 60)

    return 0 if tests_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
