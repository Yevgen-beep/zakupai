import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db_new import get_all_active_users, get_unnotified_hot_lots, mark_lots_notified
from models_new import NotificationMessage

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending hot lot notifications"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_hot_lot_notifications(self) -> int:
        """
        Send hot lot notifications to all active users
        Returns: number of notifications sent
        """
        try:
            # Get hot lots and active users
            hot_lots = await get_unnotified_hot_lots()
            if not hot_lots:
                logger.info("No hot lots to notify")
                return 0

            active_users = await get_all_active_users()
            if not active_users:
                logger.info("No active users to notify")
                return 0

            logger.info(f"Found {len(hot_lots)} hot lots for {len(active_users)} users")

            sent_count = 0

            # Send notifications for each hot lot
            for hot_lot in hot_lots:
                sent_to_users = await self._send_lot_notification(hot_lot, active_users)
                sent_count += sent_to_users

                # Small delay between lots to avoid rate limits
                await asyncio.sleep(0.5)

            # Mark lots as notified
            lot_ids = [lot.lot_id for lot in hot_lots]
            await mark_lots_notified(lot_ids)

            logger.info(f"Sent {sent_count} hot lot notifications")
            return sent_count

        except Exception as e:
            logger.error(f"Failed to send hot lot notifications: {e}")
            return 0

    async def _send_lot_notification(
        self, hot_lot: NotificationMessage, user_ids: list[int]
    ) -> int:
        """Send single lot notification to all users"""
        message_text = hot_lot.to_markdown()
        keyboard = self._create_lot_keyboard(hot_lot.lot_id)

        sent_count = 0
        tasks = []

        # Create tasks for parallel sending (batched to avoid rate limits)
        for i in range(0, len(user_ids), 10):  # Batch size of 10
            batch = user_ids[i : i + 10]
            for user_id in batch:
                task = self._send_to_user(user_id, message_text, keyboard)
                tasks.append(task)

            # Execute batch
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successful sends
            for result in results:
                if result is True:
                    sent_count += 1

            tasks.clear()

            # Delay between batches
            if i + 10 < len(user_ids):
                await asyncio.sleep(1.0)

        return sent_count

    async def _send_to_user(
        self, user_id: int, message: str, keyboard: InlineKeyboardMarkup
    ) -> bool:
        """Send notification to single user"""
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_notification=False,
            )
            return True

        except TelegramForbiddenError:
            logger.warning(f"Bot blocked by user {user_id}")
            return False
        except TelegramBadRequest as e:
            logger.warning(f"Bad request for user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            return False

    def _create_lot_keyboard(self, lot_id: str) -> InlineKeyboardMarkup:
        """Create inline keyboard for lot notification"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 Анализ", callback_data=f"analyze_{lot_id}"
                    ),
                    InlineKeyboardButton(text="📄 PDF", callback_data=f"pdf_{lot_id}"),
                ],
                [
                    InlineKeyboardButton(
                        text="📋 JSON", callback_data=f"json_{lot_id}"
                    ),
                    InlineKeyboardButton(
                        text="🔍 Goszakup",
                        url=f"https://goszakup.gov.kz/ru/announce/index/{lot_id}",
                    ),
                ],
            ]
        )

        return keyboard


async def run_notification_cron():
    """
    Cron job function to run every 15 minutes
    """
    logger.info("Starting hot lot notification cron")

    from main_new import get_bot  # Import here to avoid circular imports

    try:
        bot = await get_bot()
        notification_service = NotificationService(bot)

        sent_count = await notification_service.send_hot_lot_notifications()

        if sent_count > 0:
            logger.info(f"Notification cron completed: {sent_count} notifications sent")
        else:
            logger.info("Notification cron completed: no notifications sent")

    except Exception as e:
        logger.error(f"Notification cron failed: {e}")


if __name__ == "__main__":
    # Test notification service
    async def test_notifications():
        import os

        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            print("TELEGRAM_BOT_TOKEN not set")
            return

        bot = Bot(
            token=token, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )

        # Create test notification
        test_lot = NotificationMessage(
            lot_id="TEST123",
            title="Тестовый горячий лот",
            price=1500000,
            margin=22.5,
            risk_score=68.0,
            deadline=datetime.now(),
            customer="Тестовый заказчик",
        )

        service = NotificationService(bot)

        # Test message formatting
        message = test_lot.to_markdown()
        print("Test message:")
        print(message)
        print("\n" + "=" * 50 + "\n")

        # Test keyboard
        service._create_lot_keyboard("TEST123")
        print("Keyboard created successfully")

        await bot.session.close()

    asyncio.run(test_notifications())
