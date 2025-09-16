#!/usr/bin/env python3
"""
Optimized Priority 1 Integration Tests
- Fail-fast на первой ошибке
- Timeout для каждого теста (60s)
- Краткий отчёт (✅/❌) для каждого сервиса
- Совместимость с pytest и CI/CD
"""

import asyncio

import aiohttp
import pytest


class TestPriority1Integration:
    """Priority 1 Integration Test Suite"""

    # Service URLs
    gateway_url = "http://localhost:7005"
    embedding_url = "http://localhost:7010"
    chromadb_url = "http://localhost:8010"

    @pytest.mark.asyncio
    async def test_services_health(self):
        """Test service health endpoints - должен быть первым"""
        services = [
            ("Goszakup API Gateway", f"{self.gateway_url}/health"),
            ("Embedding API", f"{self.embedding_url}/health"),
            ("ChromaDB", f"{self.chromadb_url}/api/v2/heartbeat"),
        ]

        results = []

        async with aiohttp.ClientSession() as session:
            for name, url in services:
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            print(f"✅ {name}: OK")
                            results.append(True)
                        else:
                            print(f"❌ {name}: HTTP {resp.status}")
                            results.append(False)
                except Exception as e:
                    print(f"❌ {name}: {type(e).__name__}")
                    results.append(False)

        # Fail-fast: если хотя бы один сервис недоступен
        assert all(
            results
        ), f"Service health check failed. Results: {dict(zip([s[0] for s in services], results, strict=False))}"

    @pytest.mark.asyncio
    async def test_goszakup_api_gateway(self):
        """Test Goszakup API Gateway search functionality"""
        test_cases = [
            {
                "name": "GraphQL поиск",
                "params": {"keyword": "лак", "limit": 3, "api_version": "graphql_v2"},
            },
            {
                "name": "REST поиск",
                "params": {"keyword": "мебель", "limit": 3, "api_version": "rest_v3"},
            },
            {
                "name": "Авто-выбор API",
                "params": {"keyword": "компьютер", "limit": 3, "api_version": "auto"},
            },
        ]

        results = []

        async with aiohttp.ClientSession() as session:
            for case in test_cases:
                try:
                    async with session.get(
                        f"{self.gateway_url}/search",
                        params=case["params"],
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            api_used = data.get("api_used", "unknown")
                            total_found = data.get("total_found", 0)
                            print(
                                f"✅ {case['name']}: API={api_used}, Found={total_found}"
                            )
                            # Считаем успешным, если API ответил корректно (даже если найдено 0 результатов)
                            results.append(True)
                        else:
                            print(f"❌ {case['name']}: HTTP {resp.status}")
                            results.append(False)
                except Exception as e:
                    print(f"❌ {case['name']}: {type(e).__name__}")
                    results.append(False)

        # Fail-fast: если хотя бы один тест провалился
        assert all(
            results
        ), f"API Gateway tests failed. Results: {[case['name'] for case, result in zip(test_cases, results, strict=False) if not result]}"

    @pytest.mark.asyncio
    async def test_chromadb_integration(self):
        """Test ChromaDB integration with embedding service"""
        async with aiohttp.ClientSession() as session:
            # 1. Test ChromaDB heartbeat
            try:
                async with session.get(
                    f"{self.chromadb_url}/api/v2/heartbeat",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    heartbeat_ok = resp.status == 200
                    if heartbeat_ok:
                        data = await resp.json()
                        print("✅ ChromaDB heartbeat: OK")
                    else:
                        print(f"❌ ChromaDB heartbeat: HTTP {resp.status}")
            except Exception as e:
                print(f"❌ ChromaDB heartbeat: {type(e).__name__}")
                heartbeat_ok = False

            assert heartbeat_ok, "ChromaDB heartbeat failed"

            # 2. Test collections endpoint
            try:
                async with session.get(
                    f"{self.embedding_url}/chroma/collections",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    collections_ok = resp.status == 200
                    if collections_ok:
                        data = await resp.json()
                        count = data.get("count", 0)
                        print(f"✅ Collections endpoint: {count} collections")
                    else:
                        print(f"❌ Collections endpoint: HTTP {resp.status}")
            except Exception as e:
                print(f"❌ Collections endpoint: {type(e).__name__}")
                collections_ok = False

            assert collections_ok, "Collections endpoint failed"

    @pytest.mark.asyncio
    async def test_semantic_search_pipeline(self):
        """Test semantic search indexing and retrieval"""
        # Test data for indexing
        test_lot = {
            "collection_name": "test_priority1",
            "document_id": "test_lot_001",
            "text": "Закупка офисной мебели: столы, стулья, шкафы для государственного учреждения",
            "metadata": {
                "lot_number": "TEST001",
                "amount": 500000,
                "customer": "ГУ Тест",
            },
        }

        async with aiohttp.ClientSession() as session:
            # 1. Index test document
            try:
                async with session.post(
                    f"{self.embedding_url}/chroma/index",
                    json=test_lot,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    index_ok = resp.status == 200
                    if index_ok:
                        print("✅ Document indexing: OK")
                    else:
                        print(f"❌ Document indexing: HTTP {resp.status}")
            except Exception as e:
                print(f"❌ Document indexing: {type(e).__name__}")
                index_ok = False

            assert index_ok, "Document indexing failed"

            # 2. Search for indexed document
            search_query = {
                "collection_name": "test_priority1",
                "query": "офисная мебель столы",
                "top_k": 3,
            }

            try:
                async with session.post(
                    f"{self.embedding_url}/chroma/search",
                    json=search_query,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    search_ok = resp.status == 200
                    if search_ok:
                        data = await resp.json()
                        total_found = data.get("total_found", 0)
                        print(f"✅ Semantic search: {total_found} results")
                        # Должен найти хотя бы наш тестовый документ
                        assert total_found > 0, "No documents found in semantic search"
                    else:
                        print(f"❌ Semantic search: HTTP {resp.status}")
                        search_ok = False
            except Exception as e:
                print(f"❌ Semantic search: {type(e).__name__}")
                search_ok = False

            assert search_ok, "Semantic search failed"

    @pytest.mark.asyncio
    async def test_end_to_end_integration(self):
        """Test complete integration pipeline: Gateway -> ChromaDB -> Semantic Search"""
        async with aiohttp.ClientSession() as session:
            # 1. Search lots via API Gateway
            try:
                async with session.get(
                    f"{self.gateway_url}/search",
                    params={"keyword": "мебель", "limit": 1},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    gateway_ok = resp.status == 200
                    if gateway_ok:
                        search_data = await resp.json()
                        lots = search_data.get("results", [])
                        print(f"✅ Gateway search: {len(lots)} lots found")

                        if lots:
                            # 2. Index first lot in ChromaDB
                            lot = lots[0]
                            index_data = {
                                "collection_name": "e2e_test",
                                "document_id": f"e2e_{lot.get('lot_number', 'unknown')}",
                                "text": f"{lot.get('name_ru', '')} {lot.get('description_ru', '')}",
                                "metadata": {
                                    "lot_number": lot.get("lot_number"),
                                    "amount": lot.get("amount"),
                                    "customer": lot.get("customer_name"),
                                },
                            }

                            async with session.post(
                                f"{self.embedding_url}/chroma/index",
                                json=index_data,
                                timeout=aiohttp.ClientTimeout(total=15),
                            ) as index_resp:
                                index_ok = index_resp.status == 200
                                if index_ok:
                                    print("✅ E2E indexing: OK")
                                else:
                                    print(f"❌ E2E indexing: HTTP {index_resp.status}")

                            assert index_ok, "E2E indexing failed"
                        else:
                            print("⚠️ No lots found for E2E test, skipping indexing")
                    else:
                        print(f"❌ Gateway search: HTTP {resp.status}")
            except Exception as e:
                print(f"❌ E2E integration: {type(e).__name__}")
                gateway_ok = False

            assert gateway_ok, "E2E integration test failed"


def test_priority1_sync():
    """Synchronous wrapper for all async tests - for compatibility"""
    print("🚀 Running Priority 1 Integration Tests...")

    # Create test instance and run health check first
    test_instance = TestPriority1Integration()

    # Run tests in specific order with fail-fast behavior
    loop = asyncio.get_event_loop()

    try:
        # Test 1: Health checks (most critical)
        print("🏥 Testing service health...")
        loop.run_until_complete(test_instance.test_services_health())

        # Test 2: API Gateway functionality
        print("🔍 Testing API Gateway...")
        loop.run_until_complete(test_instance.test_goszakup_api_gateway())

        # Test 3: ChromaDB integration
        print("🗄️ Testing ChromaDB integration...")
        loop.run_until_complete(test_instance.test_chromadb_integration())

        # Test 4: Semantic search pipeline
        print("🧠 Testing semantic search...")
        loop.run_until_complete(test_instance.test_semantic_search_pipeline())

        # Test 5: End-to-end integration
        print("🔄 Testing E2E integration...")
        loop.run_until_complete(test_instance.test_end_to_end_integration())

        print("✅ All Priority 1 tests passed!")

    except Exception as e:
        print(f"❌ Priority 1 test failed: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    test_priority1_sync()
