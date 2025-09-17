import asyncio
import os
from datetime import UTC, datetime, timedelta

import httpx
import redis.asyncio as redis
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

# Database setup
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://zakupai:password123@localhost:5432/zakupai"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# RNU API configuration
RNU_API_BASE_URL = "https://api.goszakup.gov.kz/rnu/validate"
RNU_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
RNU_REDIS_PREFIX = "rnu:"


class RNUValidationError(Exception):
    """Custom exception for RNU validation errors"""

    pass


class RNUClient:
    """Client for RNU supplier validation with caching"""

    def __init__(self):
        self.redis_client = None
        self.http_client = None

    async def __aenter__(self):
        self.redis_client = redis.from_url(REDIS_URL)
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis_client:
            await self.redis_client.close()
        if self.http_client:
            await self.http_client.aclose()

    def validate_bin(self, supplier_bin: str) -> bool:
        """Validate BIN format (12 digits)"""
        return supplier_bin.isdigit() and len(supplier_bin) == 12

    async def get_from_redis_cache(self, supplier_bin: str) -> dict | None:
        """Get validation result from Redis cache"""
        try:
            cache_key = f"{RNU_REDIS_PREFIX}{supplier_bin}"
            cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                import json

                result = json.loads(cached_data)
                result["source"] = "cache"

                logger.info(
                    "Cache hit for RNU validation",
                    supplier_bin=supplier_bin,
                    is_blocked=result["is_blocked"],
                )
                return result

        except Exception as e:
            logger.warning(
                "Failed to get from Redis cache",
                supplier_bin=supplier_bin,
                error=str(e),
            )

        return None

    async def get_from_database_cache(self, supplier_bin: str) -> dict | None:
        """Get validation result from PostgreSQL cache"""
        try:
            with SessionLocal() as db:
                query = text(
                    """
                    SELECT supplier_bin, is_blocked, validated_at, expires_at
                    FROM rnu_validation_cache
                    WHERE supplier_bin = :supplier_bin
                    AND expires_at > now()
                """
                )

                result = db.execute(query, {"supplier_bin": supplier_bin}).fetchone()

                if result:
                    validation_result = {
                        "supplier_bin": result.supplier_bin,
                        "is_blocked": result.is_blocked,
                        "validated_at": result.validated_at.replace(
                            tzinfo=UTC
                        ).isoformat(),
                        "source": "cache",
                    }

                    # Update Redis cache
                    await self.save_to_redis_cache(supplier_bin, validation_result)

                    logger.info(
                        "Database cache hit for RNU validation",
                        supplier_bin=supplier_bin,
                        is_blocked=result.is_blocked,
                    )
                    return validation_result

        except Exception as e:
            logger.warning(
                "Failed to get from database cache",
                supplier_bin=supplier_bin,
                error=str(e),
            )

        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def call_rnu_api(self, supplier_bin: str) -> dict:
        """Call RNU API with retry logic"""
        url = f"{RNU_API_BASE_URL}/{supplier_bin}"

        try:
            response = await self.http_client.get(url)

            if response.status_code == 200:
                api_result = response.json()

                # Map API response to our format
                validation_result = {
                    "supplier_bin": supplier_bin,
                    "is_blocked": api_result.get("blocked", False),
                    "validated_at": datetime.now(UTC).isoformat(),
                    "source": "api",
                }

                logger.info(
                    "Successful RNU API call",
                    supplier_bin=supplier_bin,
                    is_blocked=validation_result["is_blocked"],
                    response_status=response.status_code,
                )

                return validation_result

            elif response.status_code == 404:
                # Supplier not found in registry - treat as not blocked
                validation_result = {
                    "supplier_bin": supplier_bin,
                    "is_blocked": False,
                    "validated_at": datetime.now(UTC).isoformat(),
                    "source": "api",
                }

                logger.info(
                    "Supplier not found in RNU registry",
                    supplier_bin=supplier_bin,
                    response_status=response.status_code,
                )

                return validation_result

            elif response.status_code == 429:
                logger.warning(
                    "RNU API rate limit exceeded",
                    supplier_bin=supplier_bin,
                    response_status=response.status_code,
                )
                raise RNUValidationError("Rate limit exceeded")

            else:
                logger.error(
                    "RNU API returned error status",
                    supplier_bin=supplier_bin,
                    response_status=response.status_code,
                    response_text=response.text,
                )
                raise RNUValidationError(f"API returned status {response.status_code}")

        except httpx.TimeoutException:
            logger.error("RNU API timeout", supplier_bin=supplier_bin, url=url)
            raise RNUValidationError("API timeout") from None

        except httpx.RequestError as e:
            logger.error(
                "RNU API request error",
                supplier_bin=supplier_bin,
                url=url,
                error=str(e),
            )
            raise RNUValidationError(f"API request failed: {str(e)}") from e

    async def save_to_redis_cache(self, supplier_bin: str, result: dict):
        """Save validation result to Redis cache"""
        try:
            cache_key = f"{RNU_REDIS_PREFIX}{supplier_bin}"
            import json

            # Remove source field for caching
            cache_data = {k: v for k, v in result.items() if k != "source"}

            await self.redis_client.setex(
                cache_key, RNU_CACHE_TTL_SECONDS, json.dumps(cache_data)
            )

            logger.debug(
                "Saved to Redis cache",
                supplier_bin=supplier_bin,
                ttl=RNU_CACHE_TTL_SECONDS,
            )

        except Exception as e:
            logger.warning(
                "Failed to save to Redis cache", supplier_bin=supplier_bin, error=str(e)
            )

    async def save_to_database_cache(self, supplier_bin: str, result: dict):
        """Save validation result to PostgreSQL cache"""
        try:
            expires_at = datetime.now(UTC) + timedelta(seconds=RNU_CACHE_TTL_SECONDS)
            validated_at = datetime.fromisoformat(
                result["validated_at"].replace("Z", "+00:00")
            )

            with SessionLocal() as db:
                # Use UPSERT to handle conflicts
                query = text(
                    """
                    INSERT INTO rnu_validation_cache
                    (supplier_bin, is_blocked, validated_at, expires_at)
                    VALUES (:supplier_bin, :is_blocked, :validated_at, :expires_at)
                    ON CONFLICT (supplier_bin)
                    DO UPDATE SET
                        is_blocked = EXCLUDED.is_blocked,
                        validated_at = EXCLUDED.validated_at,
                        expires_at = EXCLUDED.expires_at
                """
                )

                db.execute(
                    query,
                    {
                        "supplier_bin": supplier_bin,
                        "is_blocked": result["is_blocked"],
                        "validated_at": validated_at,
                        "expires_at": expires_at,
                    },
                )
                db.commit()

                logger.debug(
                    "Saved to database cache",
                    supplier_bin=supplier_bin,
                    expires_at=expires_at.isoformat(),
                )

        except Exception as e:
            logger.error(
                "Failed to save to database cache",
                supplier_bin=supplier_bin,
                error=str(e),
            )

    async def validate_supplier(self, supplier_bin: str) -> dict:
        """
        Validate supplier BIN through RNU registry with caching

        Returns:
            Dict with supplier_bin, is_blocked, validated_at, source
        """
        request_id = f"rnu_{supplier_bin}_{int(datetime.now().timestamp())}"

        logger.info(
            "Starting RNU validation", supplier_bin=supplier_bin, request_id=request_id
        )

        # Validate BIN format
        if not self.validate_bin(supplier_bin):
            raise RNUValidationError("Invalid BIN format: must be 12 digits")

        try:
            # Try Redis cache first (fastest)
            result = await self.get_from_redis_cache(supplier_bin)
            if result:
                return result

            # Try database cache (fast)
            result = await self.get_from_database_cache(supplier_bin)
            if result:
                return result

            # Call API (slowest)
            result = await self.call_rnu_api(supplier_bin)

            # Save to both caches
            await asyncio.gather(
                self.save_to_redis_cache(supplier_bin, result),
                self.save_to_database_cache(supplier_bin, result),
                return_exceptions=True,
            )

            logger.info(
                "Completed RNU validation",
                supplier_bin=supplier_bin,
                is_blocked=result["is_blocked"],
                source=result["source"],
                request_id=request_id,
            )

            return result

        except RNUValidationError:
            logger.error(
                "RNU validation failed",
                supplier_bin=supplier_bin,
                request_id=request_id,
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error in RNU validation",
                supplier_bin=supplier_bin,
                request_id=request_id,
                error=str(e),
            )
            raise RNUValidationError(f"Validation failed: {str(e)}") from e


# Singleton pattern for reuse
_rnu_client = None


async def get_rnu_client() -> RNUClient:
    """Dependency injection for RNU client"""
    global _rnu_client
    if _rnu_client is None:
        _rnu_client = RNUClient()
        await _rnu_client.__aenter__()
    return _rnu_client
