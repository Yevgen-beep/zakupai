#!/usr/bin/env python3
"""
Утилита для настройки webhook Telegram бота
"""

import asyncio
import sys
from pathlib import Path

# Добавляем текущую директорию в Python path
sys.path.insert(0, str(Path(__file__).parent))

import aiohttp
from config import config

TOKEN = config.telegram.bot_token
WEBHOOK_URL = config.telegram.webhook_url or ""
WEBHOOK_SECRET = config.telegram.webhook_secret or ""


async def get_webhook_info():
    """Получить информацию о текущем webhook"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data["ok"]:
                    webhook_info = data["result"]
                    print(
                        f"🔗 Current webhook URL: {webhook_info.get('url', 'Not set')}"
                    )
                    print(
                        f"📨 Pending updates: {webhook_info.get('pending_update_count', 0)}"
                    )
                    print(
                        f"⏰ Last error date: {webhook_info.get('last_error_date', 'None')}"
                    )
                    print(
                        f"❌ Last error message: {webhook_info.get('last_error_message', 'None')}"
                    )
                    return webhook_info
                else:
                    print(f"❌ Error: {data.get('description', 'Unknown error')}")
                    return None
            else:
                print(f"❌ HTTP Error: {response.status}")
                return None


async def set_webhook():
    """Установить webhook"""
    if not WEBHOOK_URL:
        print("❌ TELEGRAM_WEBHOOK_URL not configured")
        return False

    payload = {
        "url": WEBHOOK_URL,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    }

    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook", json=payload
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data["ok"]:
                    print(f"✅ Webhook set successfully to: {WEBHOOK_URL}")
                    return True
                else:
                    print(
                        f"❌ Error setting webhook: {data.get('description', 'Unknown error')}"
                    )
                    return False
            else:
                print(f"❌ HTTP Error: {response.status}")
                return False


async def delete_webhook():
    """Удалить webhook"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://api.telegram.org/bot{TOKEN}/deleteWebhook",
            json={"drop_pending_updates": True},
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data["ok"]:
                    print("✅ Webhook deleted successfully")
                    return True
                else:
                    print(
                        f"❌ Error deleting webhook: {data.get('description', 'Unknown error')}"
                    )
                    return False
            else:
                print(f"❌ HTTP Error: {response.status}")
                return False


async def test_webhook():
    """Тест webhook endpoint"""
    if not WEBHOOK_URL:
        print("❌ TELEGRAM_WEBHOOK_URL not configured")
        return False

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WEBHOOK_URL.replace("/bot", "/health")) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Health check passed: {data}")
                    return True
                else:
                    print(f"❌ Health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Health check error: {type(e).__name__}: {e}")
        return False


async def main():
    """Основная функция"""
    print("🤖 ZakupAI Telegram Bot Webhook Setup")
    print("=" * 50)
    print(f"Token: {TOKEN[:10]}...{TOKEN[-10:]}")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Secret: {'✅ set' if WEBHOOK_SECRET else '❌ not set'}")
    print(f"Environment: {config.security.environment}")
    print()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python webhook_setup.py info     - Show current webhook info")
        print("  python webhook_setup.py set      - Set webhook")
        print("  python webhook_setup.py delete   - Delete webhook")
        print("  python webhook_setup.py test     - Test webhook endpoint")
        return

    command = sys.argv[1].lower()

    if command == "info":
        await get_webhook_info()
    elif command == "set":
        success = await set_webhook()
        if success:
            print("\n📋 Webhook info after setup:")
            await get_webhook_info()
    elif command == "delete":
        success = await delete_webhook()
        if success:
            print("\n📋 Webhook info after deletion:")
            await get_webhook_info()
    elif command == "test":
        await test_webhook()
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
