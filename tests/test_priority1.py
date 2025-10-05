#!/usr/bin/env python3
"""
Priority 1 Integration Tests with detailed reporting
Compatible with pytest but with informative stdout output like bash scripts
"""

import asyncio
import json

import aiohttp
import pytest


def log(message: str):
    """Helper function for formatted output"""
    print(message, flush=True)


class TestPriority1Integration:
    """Priority 1 Integration Test Suite with detailed reporting"""

    # Service URLs
    gateway_url = "http://localhost:7005"
    embedding_url = "http://localhost:7010"
    chromadb_url = "http://localhost:8010"

    @pytest.mark.asyncio
    async def test_01_service_health(self):
        """Test service health endpoints"""
        log("🏥 Testing service health...")

        services = [
            ("Gateway", f"{self.gateway_url}/health"),
            ("Embedding API", f"{self.embedding_url}/health"),
            ("ChromaDB", f"{self.chromadb_url}/api/v2/heartbeat"),
        ]

        async with aiohttp.ClientSession() as session:
            for name, url in services:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    assert resp.status == 200, (
                        f"{name} health check failed with status {resp.status}"
                    )

                    try:
                        data = await resp.json()
                        log(
                            f"✅ {name}: {resp.status} {json.dumps(data, ensure_ascii=False)}"
                        )
                    except Exception:
                        # Fallback if response is not JSON
                        text = await resp.text()
                        log(f"✅ {name}: {resp.status} {text[:50]}...")

    @pytest.mark.asyncio
    async def test_02_graphql_search(self):
        """Test GraphQL search functionality"""
        log("🔍 Testing API Gateway...")

        params = {"keyword": "лак", "limit": 3, "api_version": "graphql_v2"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.gateway_url}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                assert resp.status == 200, (
                    f"GraphQL search failed with status {resp.status}"
                )

                data = await resp.json()
                api_used = data.get("api_used", "unknown")
                total_found = data.get("total_found", 0)

                log(f"✅ GraphQL поиск: Found={total_found}, API={api_used}")

                # Basic validation
                assert total_found >= 0, "Total found should be non-negative"
                assert "results" in data, "Response should contain results field"

    @pytest.mark.asyncio
    async def test_03_rest_search(self):
        """Test REST search functionality"""

        params = {"keyword": "мебель", "limit": 3, "api_version": "rest_v3"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.gateway_url}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                assert resp.status == 200, (
                    f"REST search failed with status {resp.status}"
                )

                data = await resp.json()
                api_used = data.get("api_used", "unknown")
                total_found = data.get("total_found", 0)

                log(f"✅ REST поиск: Found={total_found}, API={api_used}")

                # Basic validation
                assert total_found >= 0, "Total found should be non-negative"
                assert "results" in data, "Response should contain results field"

    @pytest.mark.asyncio
    async def test_04_chromadb_heartbeat(self):
        """Test ChromaDB heartbeat and collections"""
        log("🗄️ Testing ChromaDB integration...")

        async with aiohttp.ClientSession() as session:
            # Test ChromaDB heartbeat
            async with session.get(
                f"{self.chromadb_url}/api/v2/heartbeat",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                assert resp.status == 200, (
                    f"ChromaDB heartbeat failed with status {resp.status}"
                )

                try:
                    data = await resp.json()
                    log(
                        f"✅ Heartbeat: {resp.status} {json.dumps(data, ensure_ascii=False)}"
                    )
                except Exception:
                    text = await resp.text()
                    log(f"✅ Heartbeat: {resp.status} {text[:50]}...")

            # Test collections endpoint
            async with session.get(
                f"{self.embedding_url}/chroma/collections",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                assert resp.status == 200, (
                    f"Collections endpoint failed with status {resp.status}"
                )

                data = await resp.json()
                count = data.get("count", 0)
                log(f"✅ Collections: {count} found")

                assert count >= 0, "Collection count should be non-negative"

    @pytest.mark.asyncio
    async def test_05_semantic_search(self):
        """Test semantic search pipeline (indexing + search)"""
        log("🧠 Testing semantic search...")

        # Test document for indexing
        test_document = {
            "collection_name": "test_priority1_pytest",
            "document_id": "pytest_test_001",
            "text": "Закупка офисной мебели: столы, стулья, шкафы для государственного учреждения",
            "metadata": {
                "lot_number": "PYTEST001",
                "amount": 500000,
                "customer": "ГУ Тест Pytest",
            },
        }

        async with aiohttp.ClientSession() as session:
            # Step 1: Index test document
            async with session.post(
                f"{self.embedding_url}/chroma/index",
                json=test_document,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                assert resp.status == 200, (
                    f"Document indexing failed with status {resp.status}"
                )
                log("✅ Document indexing: OK")

            # Step 2: Search for the indexed document
            search_query = {
                "collection_name": "test_priority1_pytest",
                "query": "офисная мебель столы",
                "top_k": 5,
            }

            async with session.post(
                f"{self.embedding_url}/chroma/search",
                json=search_query,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                assert resp.status == 200, (
                    f"Semantic search failed with status {resp.status}"
                )

                data = await resp.json()
                total_found = data.get("total_found", 0)
                results = data.get("results", [])

                log(f"✅ Results={total_found}")

                # Validation: should find at least our test document
                assert total_found > 0, f"Expected at least 1 result, got {total_found}"
                assert len(results) > 0, "Results list should not be empty"

                # Optional: log first result for debugging
                if results:
                    first_result = results[0]
                    score = first_result.get("score", 0)
                    log(f"   Best match score: {score:.3f}")


# Global test completion tracking
_all_tests_passed = True


def pytest_runtest_logreport(report):
    """Pytest hook to track test results"""
    global _all_tests_passed
    if report.when == "call" and report.failed:
        _all_tests_passed = False


def pytest_sessionfinish(session, exitstatus):
    """Pytest hook called after all tests complete"""
    global _all_tests_passed
    if exitstatus == 0 and _all_tests_passed:
        log("\n✅ All Priority 1 tests passed!")


# For direct execution compatibility
def test_priority1_sync():
    """Synchronous wrapper for direct execution"""
    log("🚀 Starting Priority 1 Integration Tests...")

    # Create test instance
    test_instance = TestPriority1Integration()

    # Get event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        # Run tests in order
        log("Running test_01_service_health...")
        loop.run_until_complete(test_instance.test_01_service_health())

        log("Running test_02_graphql_search...")
        loop.run_until_complete(test_instance.test_02_graphql_search())

        log("Running test_03_rest_search...")
        loop.run_until_complete(test_instance.test_03_rest_search())

        log("Running test_04_chromadb_heartbeat...")
        loop.run_until_complete(test_instance.test_04_chromadb_heartbeat())

        log("Running test_05_semantic_search...")
        loop.run_until_complete(test_instance.test_05_semantic_search())

        log("\n✅ All Priority 1 tests passed!")

    except Exception as e:
        log(f"\n❌ Priority 1 test failed: {type(e).__name__}: {e}")
        raise
    finally:
        if not loop.is_running():
            loop.close()


if __name__ == "__main__":
    test_priority1_sync()
