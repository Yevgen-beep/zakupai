"""Mock data generator for testing web panel"""

import csv
import io
import random  # nosec B311 - non-cryptographic randomness acceptable for mock data
from datetime import datetime, timedelta


def generate_mock_csv():
    """Generate mock CSV data for testing"""
    products = [
        ("LAPTOP001", "Ноутбук Dell Inspiron 15", "Компьютеры"),
        ("LAPTOP002", "Ноутбук HP Pavilion", "Компьютеры"),
        ("MOUSE001", "Мышь Logitech MX Master", "Периферия"),
        ("MOUSE002", "Мышь беспроводная", "Периферия"),
        ("KB001", "Клавиатура механическая", "Периферия"),
        ("KB002", "Клавиатура мембранная", "Периферия"),
        ("MONITOR001", 'Монитор Samsung 24"', "Мониторы"),
        ("MONITOR002", 'Монитор LG 27"', "Мониторы"),
        ("PRINTER001", "Принтер HP LaserJet", "Принтеры"),
        ("PRINTER002", "МФУ Canon", "Принтеры"),
        ("DESK001", "Стол офисный", "Мебель"),
        ("CHAIR001", "Кресло компьютерное", "Мебель"),
        ("PAPER001", "Бумага А4, 500 листов", "Канцелярия"),
        ("PEN001", "Ручка шариковая синяя", "Канцелярия"),
        ("STAPLER001", "Степлер настольный", "Канцелярия"),
    ]

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["sku", "price", "name", "category", "unit"])

    # Data rows
    for sku, name, category in products:
        # Generate realistic prices based on category
        if category == "Компьютеры":
            price = random.randint(300000, 800000)  # nosec B311 - mock price generation
        elif category == "Мониторы":
            price = random.randint(60000, 150000)  # nosec B311 - mock price generation
        elif category == "Принтеры":
            price = random.randint(30000, 100000)  # nosec B311 - mock price generation
        elif category == "Мебель":
            price = random.randint(40000, 120000)  # nosec B311 - mock price generation
        elif category == "Периферия":
            price = random.randint(3000, 25000)  # nosec B311 - mock price generation
        else:  # Канцелярия
            price = random.randint(100, 5000)  # nosec B311 - mock price generation

        unit = "шт"
        writer.writerow([sku, price, name, category, unit])

    return output.getvalue()


def mock_goszakup_lot(lot_id: str):
    """Generate mock Goszakup lot data"""
    lots = {
        "123456": {
            "id": "123456",
            "title": "Поставка канцелярских товаров для государственных нужд",
            "price": 1500000,
            "customer": "Министерство образования РК",
            "deadline": "2024-12-31T23:59:59",
            "status": "active",
            "description": "Поставка канцелярских товаров согласно техническому заданию",
            "plan_id": "PLAN2024001",
        },
        "654321": {
            "id": "654321",
            "title": "Закупка компьютерного оборудования",
            "price": 5000000,
            "customer": "Акимат г. Алматы",
            "deadline": "2024-11-30T18:00:00",
            "status": "active",
            "description": "Закупка ноутбуков, принтеров и сопутствующего оборудования",
            "plan_id": "PLAN2024002",
        },
    }

    return lots.get(
        lot_id,
        {
            "id": lot_id,
            "title": f"Тестовый лот #{lot_id}",
            "price": random.randint(
                500000, 3000000
            ),  # nosec B311 - mock price generation
            "customer": "Тестовый заказчик",
            "deadline": (datetime.now() + timedelta(days=30)).isoformat(),
            "status": "active",
            "description": f"Описание тестового лота {lot_id}",
            "plan_id": f"PLAN{lot_id}",
        },
    )


def mock_tldr_data(lot_id: str):
    """Generate mock TL;DR data"""
    lot = mock_goszakup_lot(lot_id)
    return {
        "lot_id": lot_id,
        "lines": [
            f"Лот: {lot['title']}",
            f"Цена: {lot['price']:,} тенге",
            f"Заказчик: {lot['customer']}",
            "Статус: Активный",
            f"Срок подачи: {lot['deadline'][:10]}",
        ],
        "ts": datetime.now().isoformat(),
    }


def mock_risk_data(lot_id: str):
    """Generate mock risk assessment data"""
    # Different risk scores for different lots
    risk_scores = {
        "123456": 0.25,  # Low risk
        "654321": 0.55,  # Medium risk
    }

    score = risk_scores.get(lot_id, random.uniform(0.2, 0.8))  # nosec B311

    if score < 0.3:
        explanation = "Низкий риск: надежный заказчик, простые требования"
    elif score < 0.7:
        explanation = "Средний риск: средний уровень сложности, стандартные требования"
    else:
        explanation = "Высокий риск: сложные требования, короткие сроки"

    return {
        "lot_id": lot_id,
        "risk_score": score,
        "explanation": explanation,
        "factors": [
            {"name": "customer_reliability", "weight": 0.3, "value": 0.8},
            {"name": "timeline_feasibility", "weight": 0.25, "value": 0.6},
            {"name": "technical_complexity", "weight": 0.25, "value": 0.4},
            {"name": "market_competition", "weight": 0.2, "value": 0.7},
        ],
    }


def mock_margin_data(lot_price: float):
    """Generate mock margin calculation"""
    cost_price = lot_price * random.uniform(
        0.7, 0.9
    )  # nosec B311 - mock margin calculation
    profit = lot_price - cost_price
    margin_percentage = (profit / lot_price) * 100

    return {
        "selling_price": lot_price,
        "cost_price": cost_price,
        "profit_amount": profit,
        "margin_percentage": margin_percentage,
    }


if __name__ == "__main__":
    # Generate and print mock CSV
    print("Mock CSV Data:")
    print(generate_mock_csv())

    print("\nMock Lot Data (123456):")
    print(mock_goszakup_lot("123456"))

    print("\nMock Risk Data:")
    print(mock_risk_data("123456"))
