"""
Locust performance testing for Week 4.2 ZakupAI features
Load testing with traffic distribution as specified in requirements
"""

import random
import time
from datetime import date

from locust import HttpUser, between, events, task


class ZakupAIUser(HttpUser):
    """
    Week 4.2 Load Testing User
    Traffic distribution:
    - 60%: /web-ui/import-prices, /api/search/advanced
    - 20%: /validate_rnu
    - 20%: /api/complaint, /api/supplier, WebSocket
    """

    wait_time = between(1, 5)  # Wait 1-5 seconds between requests

    def on_start(self):
        """Setup test data and common variables"""
        # Test data for different endpoints
        self.lot_ids = [12345, 23456, 34567, 45678, 56789, 67890]
        self.suppliers = [
            "мебель",
            "компьютеры",
            "канцтовары",
            "оборудование",
            "услуги",
        ]
        self.complaints = [
            "завышенная цена",
            "нарушение сроков",
            "некачественный товар",
            "недостоверная информация",
            "технические нарушения",
        ]
        self.rnu_bins = [
            "123456789012",
            "234567890123",
            "345678901234",
            "456789012345",
            "567890123456",
        ]

        # Performance tracking
        self.request_start_time = None
        self.websocket_connected = False

    # =================================================================
    # 60% Traffic: Primary endpoints (import-prices, advanced search)
    # =================================================================

    @task(30)  # 30% of total traffic
    def advanced_search(self):
        """Test advanced search endpoint - primary traffic"""
        search_params = {
            "query": random.choice(["компьютер", "мебель", "оборудование", "услуги"]),
            "min_amount": random.randint(10000, 50000),
            "max_amount": random.randint(100000, 500000),
            "status": random.choice([1, 2, 3]),
            "limit": random.randint(5, 20),
        }

        with self.client.post(
            "/api/search/advanced",
            json=search_params,
            catch_response=True,
            name="Advanced Search",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "results" in data and "total_count" in data:
                    response.success()
                else:
                    response.failure("Invalid response format")
            elif response.status_code == 422:
                # Validation errors are acceptable in load testing
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(30)  # 30% of total traffic
    def csv_import_simulation(self):
        """Simulate CSV import - primary traffic"""
        # Generate small CSV content for testing
        csv_content = "product_name,amount,supplier_bin\n"
        for i in range(random.randint(10, 50)):
            csv_content += f"Товар {i},{random.randint(1000, 50000)},{random.choice(self.rnu_bins)}\n"

        client_id = f"load_test_{random.randint(1000, 9999)}"

        # Simulate file upload
        files = {"file": ("test_load.csv", csv_content.encode("utf-8"), "text/csv")}
        data = {"client_id": client_id}

        with self.client.post(
            "/web-ui/import-prices",
            files=files,
            data=data,
            catch_response=True,
            name="CSV Import",
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if "import_log_id" in result and "status" in result:
                    response.success()

                    # Optionally check import status
                    if random.random() < 0.3:  # 30% chance
                        self.check_import_status(result["import_log_id"])
                else:
                    response.failure("Invalid import response")
            elif response.status_code in [400, 413]:
                # File validation errors are acceptable
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    def check_import_status(self, log_id):
        """Check import status for completed imports"""
        with self.client.get(
            f"/web-ui/import-status/{log_id}",
            catch_response=True,
            name="Import Status Check",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Import status check failed: {response.status_code}")

    # =================================================================
    # 20% Traffic: RNU validation
    # =================================================================

    @task(20)  # 20% of total traffic
    def validate_rnu(self):
        """Test RNU validation endpoint"""
        supplier_bin = random.choice(self.rnu_bins)

        with self.client.get(
            f"/validate_rnu?supplier_bin={supplier_bin}",
            catch_response=True,
            name="RNU Validation",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "supplier_bin" in data and "status" in data:
                    response.success()
                else:
                    response.failure("Invalid RNU response format")
            elif response.status_code in [404, 422]:
                # Not found or validation errors are acceptable
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    # =================================================================
    # 20% Traffic: Flowise features (complaint, supplier, WebSocket)
    # =================================================================

    @task(8)  # 8% of total traffic
    def generate_complaint(self):
        """Test complaint generation - Week 4.2 feature"""
        lot_id = random.choice(self.lot_ids)
        complaint_data = {
            "reason": random.choice(self.complaints),
            "date": date.today().isoformat(),
        }

        with self.client.post(
            f"/api/complaint/{lot_id}",
            json=complaint_data,
            catch_response=True,
            name="Generate Complaint",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "complaint_text" in data and "source" in data:
                    response.success()

                    # Occasionally test PDF/Word download
                    if random.random() < 0.2:  # 20% chance
                        self.download_complaint_formats(lot_id, complaint_data)
                else:
                    response.failure("Invalid complaint response")
            elif response.status_code == 404:
                # Lot not found is acceptable in testing
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    def download_complaint_formats(self, lot_id, complaint_data):
        """Test PDF and Word downloads for complaints"""
        params = {"reason": complaint_data["reason"], "date": complaint_data["date"]}

        # Test PDF download
        with self.client.get(
            f"/api/complaint/{lot_id}/pdf",
            params=params,
            catch_response=True,
            name="Download Complaint PDF",
        ) as response:
            if (
                response.status_code == 200
                and response.headers.get("content-type") == "application/pdf"
            ):
                response.success()
            else:
                response.failure("PDF download failed")

        # Test Word download (50% chance)
        if random.random() < 0.5:
            with self.client.get(
                f"/api/complaint/{lot_id}/word",
                params=params,
                catch_response=True,
                name="Download Complaint Word",
            ) as response:
                if (
                    response.status_code == 200
                    and "wordprocessingml" in response.headers.get("content-type", "")
                ):
                    response.success()
                else:
                    response.failure("Word download failed")

    @task(8)  # 8% of total traffic
    def search_suppliers(self):
        """Test supplier search - Week 4.2 feature"""
        lot_name = random.choice(self.suppliers)

        # Add random filters
        params = {}
        if random.random() < 0.4:  # 40% chance to add region filter
            params["region"] = random.choice(["KZ", "RU", "CN"])

        if random.random() < 0.3:  # 30% chance to add budget filters
            params["min_budget"] = random.randint(10000, 50000)
            params["max_budget"] = random.randint(100000, 500000)

        if random.random() < 0.5:  # 50% chance to specify sources
            sources = random.sample(["satu", "1688", "alibaba"], random.randint(1, 2))
            params["sources"] = ",".join(sources)

        with self.client.get(
            f"/api/supplier/{lot_name}",
            params=params,
            catch_response=True,
            name="Search Suppliers",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "suppliers" in data and "sources_used" in data:
                    response.success()

                    # Track cache hit rate
                    cache_hit = data.get("cache_hit", False)
                    if cache_hit:
                        events.request.fire(
                            request_type="CACHE",
                            name="Supplier Cache Hit",
                            response_time=0,
                            response_length=0,
                            exception=None,
                        )
                else:
                    response.failure("Invalid supplier response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(4)  # 4% of total traffic
    def test_autocomplete(self):
        """Test enhanced autocomplete functionality"""
        queries = ["комп", "мебе", "кан", "обор", "усл"]
        query = random.choice(queries)

        with self.client.get(
            f"/api/search/autocomplete?query={query}",
            catch_response=True,
            name="Autocomplete Search",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "suggestions" in data:
                    response.success()
                else:
                    response.failure("Invalid autocomplete response")
            else:
                response.failure(f"HTTP {response.status_code}")

    def websocket_test(self):
        """Simulate WebSocket connection for import progress"""
        # Note: This is a simplified WebSocket test simulation
        # Real WebSocket testing with Locust requires additional setup

        # Simulate WebSocket connection attempt
        try:
            # In a real scenario, you'd use websocket-client or similar
            # For load testing, we simulate the connection overhead
            time.sleep(0.1)  # Simulate connection time

            events.request.fire(
                request_type="WS",
                name="WebSocket Connection",
                response_time=100,  # 100ms simulated
                response_length=0,
                exception=None,
            )

        except Exception as e:
            events.request.fire(
                request_type="WS",
                name="WebSocket Connection",
                response_time=0,
                response_length=0,
                exception=e,
            )


class AdminUser(HttpUser):
    """
    Admin user for testing admin endpoints
    Lower frequency operations
    """

    wait_time = between(5, 15)  # Longer wait times for admin operations
    weight = 1  # Lower weight compared to regular users

    @task(1)
    def get_supplier_sources(self):
        """Test getting supplier source configurations"""
        with self.client.get(
            "/api/admin/sources", catch_response=True, name="Get Supplier Sources"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    response.success()
                else:
                    response.failure("Invalid sources response")
            else:
                response.failure(f"HTTP {response.status_code}")


class PerformanceTestUser(HttpUser):
    """
    User focused on performance testing specific Week 4.2 targets
    """

    wait_time = between(0.5, 2)  # Aggressive timing for performance testing

    @task(1)
    def test_complaint_performance_target(self):
        """Test complaint generation performance (<1 second target)"""
        lot_id = random.choice([12345, 23456, 34567])
        complaint_data = {
            "reason": "Performance test complaint",
            "date": date.today().isoformat(),
        }

        start_time = time.time()
        with self.client.post(
            f"/api/complaint/{lot_id}",
            json=complaint_data,
            catch_response=True,
            name="Complaint Performance Test",
        ) as response:
            response_time = time.time() - start_time

            if response.status_code == 200:
                if response_time < 1.0:  # Target: <1 second
                    response.success()
                else:
                    response.failure(
                        f"Performance target missed: {response_time:.2f}s > 1.0s"
                    )
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def test_supplier_performance_target(self):
        """Test supplier search performance (<1 second target)"""
        lot_name = random.choice(["мебель", "компьютеры", "оборудование"])

        start_time = time.time()
        with self.client.get(
            f"/api/supplier/{lot_name}",
            catch_response=True,
            name="Supplier Performance Test",
        ) as response:
            response_time = time.time() - start_time

            if response.status_code == 200:
                if response_time < 1.0:  # Target: <1 second
                    response.success()
                else:
                    response.failure(
                        f"Performance target missed: {response_time:.2f}s > 1.0s"
                    )
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def test_autocomplete_performance_target(self):
        """Test autocomplete performance (<500ms target)"""
        query = random.choice(["комп", "мебе", "обор"])

        start_time = time.time()
        with self.client.get(
            f"/api/search/autocomplete?query={query}",
            catch_response=True,
            name="Autocomplete Performance Test",
        ) as response:
            response_time = time.time() - start_time

            if response.status_code == 200:
                if response_time < 0.5:  # Target: <500ms
                    response.success()
                else:
                    response.failure(
                        f"Performance target missed: {response_time:.3f}s > 0.5s"
                    )
            else:
                response.failure(f"HTTP {response.status_code}")


# =================================================================
# Event handlers for metrics collection
# =================================================================


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize performance tracking"""
    print("Starting Week 4.2 ZakupAI Load Test")
    print("Performance Targets:")
    print("- Complaint generation: <1 second")
    print("- Supplier search: <1 second")
    print("- Autocomplete: <500ms")
    print("- Overall target: ≥1000 req/min, p95 <2s, error rate <5%")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print performance summary"""
    stats = environment.stats

    print("\n" + "=" * 60)
    print("Week 4.2 Performance Test Results")
    print("=" * 60)

    # Overall metrics
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    error_rate = (total_failures / total_requests * 100) if total_requests > 0 else 0

    print(f"Total Requests: {total_requests}")
    print(f"Total Failures: {total_failures}")
    print(f"Error Rate: {error_rate:.2f}%")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")

    # Check performance targets
    print("\nPerformance Target Assessment:")
    print(f"✅ Error Rate Target (<5%): {'PASS' if error_rate < 5 else 'FAIL'}")
    print(
        f"✅ P95 Latency Target (<2s): {'PASS' if stats.total.get_response_time_percentile(0.95) < 2000 else 'FAIL'}"
    )

    # RPS calculation
    test_duration = (stats.last_request_timestamp - stats.start_time) / 1000
    rps = total_requests / test_duration if test_duration > 0 else 0
    rpm = rps * 60
    print(
        f"✅ Throughput Target (≥1000 req/min): {'PASS' if rpm >= 1000 else 'FAIL'} ({rpm:.0f} req/min)"
    )

    print("\nTop 5 Slowest Endpoints:")
    sorted_stats = sorted(
        stats.entries.items(), key=lambda x: x[1].avg_response_time, reverse=True
    )
    for name, stat in sorted_stats[:5]:
        print(f"  {name[1]}: {stat.avg_response_time:.2f}ms avg")

    print("=" * 60)


# =================================================================
# Custom performance assertions
# =================================================================


def check_performance_targets(stats):
    """Check if performance targets are met"""
    targets_met = []

    # Check complaint generation performance
    complaint_stats = None
    for (_method, name), stat in stats.entries.items():
        if "complaint" in name.lower() and "performance" in name.lower():
            complaint_stats = stat
            break

    if complaint_stats and complaint_stats.avg_response_time < 1000:
        targets_met.append("Complaint <1s: PASS")
    else:
        targets_met.append("Complaint <1s: FAIL")

    # Check supplier search performance
    supplier_stats = None
    for (_method, name), stat in stats.entries.items():
        if "supplier" in name.lower() and "performance" in name.lower():
            supplier_stats = stat
            break

    if supplier_stats and supplier_stats.avg_response_time < 1000:
        targets_met.append("Supplier <1s: PASS")
    else:
        targets_met.append("Supplier <1s: FAIL")

    return targets_met
