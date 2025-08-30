import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from models_new import ApiKeyValidation, Base, HotLot, NotificationMessage, TgKey
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

# Global async engine and session factory
_engine = None
_session_factory = None


async def init_db():
    """Initialize database connection and create tables"""
    global _engine, _session_factory

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://zakupai:password123@localhost:5432/zakupai",
    )

    _engine = create_async_engine(
        database_url, echo=False, pool_size=5, max_overflow=10, pool_pre_ping=True
    )

    _session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized successfully")


async def close_db():
    """Close database connections"""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database connections closed")


@asynccontextmanager
async def get_session():
    """Get async database session"""
    if not _session_factory:
        await init_db()

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            await session.close()


async def save_api_key(user_id: int, api_key: str) -> bool:
    """Save or update user API key"""
    try:
        # Validate input
        validation = ApiKeyValidation(user_id=user_id, api_key=api_key)

        async with get_session() as session:
            stmt = insert(TgKey).values(
                user_id=validation.user_id,
                api_key=validation.api_key,
                updated_at=func.now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "api_key": stmt.excluded.api_key,
                    "updated_at": stmt.excluded.updated_at,
                    "is_active": True,
                },
            )

            await session.execute(stmt)
            logger.info(f"API key saved for user {user_id}")
            return True

    except Exception as e:
        logger.error(f"Failed to save API key for user {user_id}: {e}")
        return False


async def get_api_key(user_id: int) -> str | None:
    """Get user API key"""
    try:
        async with get_session() as session:
            stmt = select(TgKey.api_key).where(
                and_(TgKey.user_id == user_id, TgKey.is_active == True)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    except Exception as e:
        logger.error(f"Failed to get API key for user {user_id}: {e}")
        return None


async def get_all_active_users() -> list[int]:
    """Get all active user IDs for notifications"""
    try:
        async with get_session() as session:
            stmt = select(TgKey.user_id).where(TgKey.is_active == True)
            result = await session.execute(stmt)
            return [row[0] for row in result.fetchall()]

    except Exception as e:
        logger.error(f"Failed to get active users: {e}")
        return []


async def save_hot_lot(lot_data: dict) -> bool:
    """Save hot lot to database"""
    try:
        async with get_session() as session:
            hot_lot = HotLot(
                id=lot_data["lot_id"],
                title=lot_data.get("title"),
                price=lot_data.get("price", 0),
                margin=int(
                    lot_data.get("margin", 0) * 100
                ),  # Store as integer (percentage * 100)
                risk_score=int(lot_data.get("risk_score", 0) * 100),
                deadline=lot_data.get("deadline"),
                customer=lot_data.get("customer"),
            )

            stmt = insert(HotLot).values(**lot_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "title": stmt.excluded.title,
                    "price": stmt.excluded.price,
                    "margin": stmt.excluded.margin,
                    "risk_score": stmt.excluded.risk_score,
                    "deadline": stmt.excluded.deadline,
                    "customer": stmt.excluded.customer,
                },
            )

            await session.execute(stmt)
            return True

    except Exception as e:
        logger.error(f"Failed to save hot lot {lot_data.get('lot_id')}: {e}")
        return False


async def get_unnotified_hot_lots() -> list[NotificationMessage]:
    """Get hot lots that haven't been notified yet"""
    try:
        async with get_session() as session:
            # Get lots from last 24h that haven't been notified
            cutoff = datetime.now() - timedelta(hours=24)

            stmt = (
                select(HotLot)
                .where(
                    and_(
                        HotLot.notified_at.is_(None),
                        HotLot.created_at >= cutoff,
                        HotLot.deadline >= datetime.now(),
                        HotLot.margin >= 1500,  # 15% * 100
                        HotLot.risk_score >= 6000,  # 60% * 100
                    )
                )
                .order_by(HotLot.margin.desc(), HotLot.created_at.desc())
            )

            result = await session.execute(stmt)
            hot_lots = result.scalars().all()

            notifications = []
            for lot in hot_lots:
                notifications.append(
                    NotificationMessage(
                        lot_id=lot.id,
                        title=lot.title or f"Лот #{lot.id}",
                        price=lot.price,
                        margin=lot.margin / 100.0,  # Convert back to percentage
                        risk_score=lot.risk_score / 100.0,
                        deadline=lot.deadline,
                        customer=lot.customer,
                    )
                )

            return notifications

    except Exception as e:
        logger.error(f"Failed to get unnotified hot lots: {e}")
        return []


async def mark_lots_notified(lot_ids: list[str]) -> bool:
    """Mark lots as notified"""
    try:
        async with get_session() as session:
            stmt = (
                update(HotLot)
                .where(HotLot.id.in_(lot_ids))
                .values(notified_at=func.now())
            )

            await session.execute(stmt)
            return True

    except Exception as e:
        logger.error(f"Failed to mark lots as notified: {e}")
        return False


async def cleanup_old_hot_lots(days_old: int = 7) -> int:
    """Clean up old hot lots"""
    try:
        async with get_session() as session:
            cutoff = datetime.now() - timedelta(days=days_old)

            stmt = delete(HotLot).where(HotLot.created_at < cutoff)

            result = await session.execute(stmt)
            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} old hot lots")
            return deleted_count

    except Exception as e:
        logger.error(f"Failed to cleanup old hot lots: {e}")
        return 0


async def health_check() -> bool:
    """Database health check"""
    try:
        async with get_session() as session:
            await session.execute(select(1))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# Test utilities
async def create_test_data():
    """Create test data for development"""
    if os.getenv("ENVIRONMENT") != "development":
        return

    try:
        # Test user
        await save_api_key(123456789, "test-api-key-123")

        # Test hot lot
        test_lot = {
            "lot_id": "TEST001",
            "title": "Тестовый горячий лот",
            "price": 1000000,
            "margin": 20.0,
            "risk_score": 65.0,
            "deadline": datetime.now() + timedelta(days=2),
            "customer": "Тестовый заказчик",
        }
        await save_hot_lot(test_lot)

        logger.info("Test data created")

    except Exception as e:
        logger.error(f"Failed to create test data: {e}")


if __name__ == "__main__":

    async def test_db():
        await init_db()
        await create_test_data()

        # Test operations
        is_healthy = await health_check()
        print(f"Health: {'OK' if is_healthy else 'FAILED'}")

        # Test API key operations
        saved = await save_api_key(999, "test-key-999")
        print(f"Save API key: {'OK' if saved else 'FAILED'}")

        retrieved = await get_api_key(999)
        print(f"Get API key: {'OK' if retrieved == 'test-key-999' else 'FAILED'}")

        # Test hot lots
        hot_lots = await get_unnotified_hot_lots()
        print(f"Hot lots: {len(hot_lots)} found")

        await close_db()

    asyncio.run(test_db())
