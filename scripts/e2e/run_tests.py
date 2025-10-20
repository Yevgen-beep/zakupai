#!/usr/bin/env python3
"""E2E test runner for ZakupAI pipeline"""

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Configuration
GATEWAY_URL = "http://localhost:8080"
API_KEY = "changeme"
SCRIPT_DIR = Path(__file__).parent
SAMPLE_CSV = SCRIPT_DIR / "sample.csv"


class E2ETestRunner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": API_KEY})
        self.results = {
            "start_time": datetime.now().isoformat(),
            "steps": {},
            "summary": {},
            "success": False,
        }

    def log_step(self, step, success, data=None, error=None):
        self.results["steps"][step] = {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "data": data,
            "error": error,
        }
        if not success:
            print(f"❌ {step}: {error}", file=sys.stderr)
        else:
            print(f"✅ {step}")

    def wait_for_services(self, timeout=60):
        """Wait for all services to be healthy"""
        services = ["calc", "risk", "doc", "emb"]
        start_time = time.time()

        while time.time() - start_time < timeout:
            all_healthy = True
            for service in services:
                try:
                    resp = requests.get(f"{GATEWAY_URL}/{service}/health", timeout=5)
                    if resp.status_code != 200:
                        all_healthy = False
                        break
                except Exception as e:
                    print(f"Health check failed for {service}: {e}")
                    all_healthy = False
                    break

            if all_healthy:
                return True
            time.sleep(2)

        return False

    def import_prices(self):
        """Import prices from sample CSV"""
        try:
            prices_data = []
            with open(SAMPLE_CSV) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    prices_data.append(
                        {
                            "sku": row["sku"],
                            "price": float(row["price"]),
                            "source": row["source"],
                            "captured_at": row["captured_at"],
                        }
                    )

            resp = self.session.post(
                f"{GATEWAY_URL}/calc/import-prices", json={"prices": prices_data}
            )
            resp.raise_for_status()

            result = resp.json()
            self.log_step(
                "import_prices",
                True,
                {"imported": len(prices_data), "response": result},
            )
            return result

        except Exception as e:
            self.log_step("import_prices", False, error=str(e))
            return None

    def create_lot(self):
        """Create test lot"""
        try:
            lot_data = {
                "id": "TEST001",
                "title": "Тестовая закупка компьютерного оборудования",
                "price": 1500000,
                "customer": "Тестовый заказчик",
                "deadline": "2024-12-31T23:59:59Z",
                "description": "Закупка оборудования для e2e теста",
                "plan_id": "PLAN_TEST_001",
                "items": [
                    {"sku": "LAPTOP001", "quantity": 2, "unit": "шт"},
                    {"sku": "MOUSE001", "quantity": 10, "unit": "шт"},
                    {"sku": "KB001", "quantity": 5, "unit": "шт"},
                    {"sku": "MONITOR001", "quantity": 3, "unit": "шт"},
                ],
            }

            resp = self.session.post(f"{GATEWAY_URL}/calc/lots", json=lot_data)
            resp.raise_for_status()

            result = resp.json()
            self.log_step("create_lot", True, {"lot_id": result.get("id")})
            return result

        except Exception as e:
            self.log_step("create_lot", False, error=str(e))
            return None

    def calculate_margin(self, lot_id):
        """Calculate lot margins"""
        try:
            resp = self.session.post(
                f"{GATEWAY_URL}/calc/calc", json={"lot_id": lot_id}
            )
            resp.raise_for_status()

            result = resp.json()
            self.log_step(
                "calculate_margin",
                True,
                {
                    "lot_id": lot_id,
                    "total_cost": result.get("total_cost"),
                    "margin_percent": result.get("margin_percent"),
                },
            )
            return result

        except Exception as e:
            self.log_step("calculate_margin", False, error=str(e))
            return None

    def analyze_risk(self, lot_id):
        """Analyze lot risk"""
        try:
            resp = self.session.post(
                f"{GATEWAY_URL}/risk/analyze", json={"lot_id": lot_id}
            )
            resp.raise_for_status()

            result = resp.json()
            self.log_step(
                "analyze_risk",
                True,
                {
                    "lot_id": lot_id,
                    "risk_score": result.get("risk_score"),
                    "risk_level": result.get("risk_level"),
                },
            )
            return result

        except Exception as e:
            self.log_step("analyze_risk", False, error=str(e))
            return None

    def verify_database_records(self, lot_id):
        """Verify records were written to database"""
        try:
            # Check lot_prices table
            resp = self.session.get(f"{GATEWAY_URL}/calc/lot/{lot_id}/prices")
            resp.raise_for_status()
            prices = resp.json()

            # Check risk_evaluations table
            resp = self.session.get(f"{GATEWAY_URL}/risk/lot/{lot_id}")
            resp.raise_for_status()
            risk_eval = resp.json()

            self.log_step(
                "verify_database",
                True,
                {
                    "prices_count": len(prices),
                    "risk_evaluation_exists": bool(risk_eval),
                },
            )
            return {"prices": prices, "risk_evaluation": risk_eval}

        except Exception as e:
            self.log_step("verify_database", False, error=str(e))
            return None

    def run(self):
        """Execute full e2e test pipeline"""
        print("🚀 Starting ZakupAI E2E Tests")

        # Wait for services
        if not self.wait_for_services():
            self.log_step("wait_services", False, error="Services not ready")
            return self.finalize(False)
        self.log_step("wait_services", True)

        # Import prices
        import_result = self.import_prices()
        if not import_result:
            return self.finalize(False)

        # Create lot
        lot_result = self.create_lot()
        if not lot_result:
            return self.finalize(False)
        lot_id = lot_result["id"]

        # Calculate margins
        margin_result = self.calculate_margin(lot_id)
        if not margin_result:
            return self.finalize(False)

        # Analyze risk
        risk_result = self.analyze_risk(lot_id)
        if not risk_result:
            return self.finalize(False)

        # Verify database records
        db_result = self.verify_database_records(lot_id)
        if not db_result:
            return self.finalize(False)

        return self.finalize(True)

    def finalize(self, success):
        """Finalize test results"""
        self.results["end_time"] = datetime.now().isoformat()
        self.results["success"] = success

        # Generate summary
        successful_steps = sum(
            1 for step in self.results["steps"].values() if step["success"]
        )
        total_steps = len(self.results["steps"])

        self.results["summary"] = {
            "status": "PASS" if success else "FAIL",
            "steps_passed": successful_steps,
            "steps_total": total_steps,
            "duration_seconds": (
                datetime.fromisoformat(self.results["end_time"])
                - datetime.fromisoformat(self.results["start_time"])
            ).total_seconds(),
        }

        # Print final result
        print(json.dumps(self.results, indent=2))

        # Return exit code
        return 0 if success else 1


if __name__ == "__main__":
    runner = E2ETestRunner()
    sys.exit(runner.run())
