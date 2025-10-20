#!/usr/bin/env python3
"""
Тестирование интеграции Приоритета 1:
- API Gateway сервис
- ChromaDB + embedding-api
- Семантический поиск по тендерам
"""

import asyncio

import aiohttp


class Priority1Tester:
    """Тестер интеграций Приоритета 1"""

    def __init__(self):
        self.gateway_url = "http://localhost:7005"
        self.embedding_url = "http://localhost:7010"
        self.chromadb_url = "http://localhost:8010"

    async def test_goszakup_api_gateway(self):
        """Тест универсального API Gateway"""
        print("🔍 Тестирование Goszakup API Gateway...")

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
                "params": {"keyword": "компьютер", "limit": 5, "api_version": "auto"},
            },
        ]

        async with aiohttp.ClientSession() as session:
            for case in test_cases:
                try:
                    print(f"  📋 {case['name']}...")

                    async with session.get(
                        f"{self.gateway_url}/search", params=case["params"], timeout=30
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            print(f"    ✅ API: {data.get('api_used')}")
                            print(f"    📊 Найдено: {data.get('total_found')} лотов")
                            print(f"    ⏱️ Время: {data.get('query_time_ms')}мс")
                        else:
                            print(f"    ❌ Ошибка: {resp.status}")

                except Exception as e:
                    print(f"    ❌ Исключение: {e}")

    async def test_chromadb_integration(self):
        """Тест ChromaDB интеграции"""
        print("\n🗄️ Тестирование ChromaDB интеграции...")

        async with aiohttp.ClientSession() as session:
            # 1. Тест v2 heartbeat
            print("  💓 Проверка v2 heartbeat...")
            try:
                async with session.get(f"{self.chromadb_url}/api/v2/heartbeat") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(
                            f"    ✅ ChromaDB v2 heartbeat: {data.get('nanosecond heartbeat', 'OK')}"
                        )
                    else:
                        print(f"    ❌ Ошибка heartbeat: {resp.status}")
            except Exception as e:
                print(f"    ❌ Исключение heartbeat: {e}")

            # 2. Список коллекций
            print("  📋 Проверка коллекций...")
            try:
                async with session.get(
                    f"{self.embedding_url}/chroma/collections"
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"    ✅ Найдено коллекций: {data.get('count', 0)}")
                    else:
                        print(f"    ❌ Ошибка: {resp.status}")
            except Exception as e:
                print(f"    ❌ Исключение: {e}")

            # 2. Индексация тестовых документов
            print("  📝 Индексация тестовых лотов...")
            test_lots = [
                {
                    "document_id": "lot_001",
                    "text": "Закупка офисной мебели: столы, стулья, шкафы для государственного учреждения",
                    "metadata": {
                        "lot_number": "001",
                        "amount": 500000,
                        "customer": "ГУ Алматы",
                    },
                },
                {
                    "document_id": "lot_002",
                    "text": "Поставка компьютерной техники: ноутбуки, мониторы, принтеры",
                    "metadata": {
                        "lot_number": "002",
                        "amount": 1200000,
                        "customer": "Министерство образования",
                    },
                },
                {
                    "document_id": "lot_003",
                    "text": "Ремонт и покраска фасада здания лакокрасочными материалами",
                    "metadata": {
                        "lot_number": "003",
                        "amount": 800000,
                        "customer": "Акимат",
                    },
                },
            ]

            for lot in test_lots:
                try:
                    async with session.post(
                        f"{self.embedding_url}/chroma/index",
                        json={"collection_name": "test_lots", **lot},
                    ) as resp:
                        if resp.status == 200:
                            print(f"    ✅ Индексирован: {lot['document_id']}")
                        else:
                            print(
                                f"    ❌ Ошибка индексации {lot['document_id']}: {resp.status}"
                            )
                except Exception as e:
                    print(f"    ❌ Исключение при индексации: {e}")

            # 3. Семантический поиск
            print("  🔍 Тестирование семантического поиска...")
            search_queries = [
                "офисная мебель",
                "компьютеры и техника",
                "строительные работы",
                "лак и краска",
            ]

            for query in search_queries:
                try:
                    async with session.post(
                        f"{self.embedding_url}/chroma/search",
                        json={
                            "collection_name": "test_lots",
                            "query": query,
                            "top_k": 3,
                        },
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            print(f"    🔍 Запрос: '{query}'")
                            print(
                                f"    📊 Найдено: {data.get('total_found')} результатов"
                            )

                            for result in data.get("results", [])[:2]:
                                score = result.get("score", 0)
                                text = result.get("text", "")[:60] + "..."
                                print(f"      📄 Релевантность: {score:.3f} - {text}")
                        else:
                            print(f"    ❌ Ошибка поиска '{query}': {resp.status}")
                except Exception as e:
                    print(f"    ❌ Исключение при поиске: {e}")

    async def test_integration_pipeline(self):
        """Тест полной интеграции: поиск → индексация → семантический поиск"""
        print("\n🔄 Тестирование полной интеграции...")

        async with aiohttp.ClientSession() as session:
            # 1. Поиск лотов через API Gateway
            print("  1️⃣ Поиск лотов через API Gateway...")
            try:
                async with session.get(
                    f"{self.gateway_url}/search",
                    params={"keyword": "мебель", "limit": 2},
                ) as resp:
                    if resp.status == 200:
                        search_data = await resp.json()
                        lots = search_data.get("results", [])
                        print(f"    ✅ Найдено лотов через API: {len(lots)}")

                        # 2. Индексация найденных лотов в ChromaDB
                        print("  2️⃣ Индексация в ChromaDB...")
                        for i, lot in enumerate(lots[:2]):
                            index_data = {
                                "collection_name": "live_lots",
                                "document_id": f"live_{lot.get('lot_number', f'unknown_{i}')}",
                                "text": f"{lot.get('name_ru', '')} {lot.get('description_ru', '')}",
                                "metadata": {
                                    "lot_number": lot.get("lot_number"),
                                    "amount": lot.get("amount"),
                                    "customer": lot.get("customer_name"),
                                    "source": lot.get("source"),
                                },
                            }

                            async with session.post(
                                f"{self.embedding_url}/chroma/index", json=index_data
                            ) as index_resp:
                                if index_resp.status == 200:
                                    print(
                                        f"    ✅ Индексирован лот: {index_data['document_id']}"
                                    )

                        # 3. Семантический поиск по индексированным данным
                        print("  3️⃣ Семантический поиск...")
                        async with session.post(
                            f"{self.embedding_url}/chroma/search",
                            json={
                                "collection_name": "live_lots",
                                "query": "офисная мебель столы стулья",
                                "top_k": 3,
                            },
                        ) as search_resp:
                            if search_resp.status == 200:
                                semantic_data = await search_resp.json()
                                print(
                                    f"    ✅ Семантический поиск: {semantic_data.get('total_found')} результатов"
                                )
                            else:
                                print(
                                    f"    ❌ Ошибка семантического поиска: {search_resp.status}"
                                )
                    else:
                        print(f"    ❌ Ошибка API Gateway: {resp.status}")
            except Exception as e:
                print(f"    ❌ Исключение в интеграционном тесте: {e}")

    async def check_services_health(self):
        """Проверка здоровья всех сервисов"""
        print("🏥 Проверка состояния сервисов...")

        services = [
            ("Goszakup API Gateway", f"{self.gateway_url}/health"),
            ("Embedding API", f"{self.embedding_url}/health"),
            ("ChromaDB", f"{self.chromadb_url}/api/v2/heartbeat"),
        ]

        async with aiohttp.ClientSession() as session:
            for name, url in services:
                try:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            print(f"  ✅ {name}: OK")
                        else:
                            print(f"  ❌ {name}: {resp.status}")
                except Exception as e:
                    print(f"  ❌ {name}: {e}")

    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🚀 Запуск тестирования интеграции Приоритета 1\n")

        await self.check_services_health()
        await self.test_goszakup_api_gateway()
        await self.test_chromadb_integration()
        await self.test_integration_pipeline()

        print("\n✨ Тестирование завершено!")


async def main():
    """Главная функция"""
    tester = Priority1Tester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
