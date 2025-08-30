#!/usr/bin/env python3
"""
Hot lots notification cron job
Runs every 15 minutes to find and notify about hot lots
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add bot directory to path
sys.path.append(os.path.dirname(__file__))

from client_new import LotPipeline, ZakupaiHTTPClient
from db_new import close_db, init_db, save_hot_lot
from notifications import run_notification_cron

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hot_lots_cron")


async def find_and_save_hot_lots():
    """
    Find hot lots matching criteria and save to database
    Criteria: margin ≥ 15%, risk ≥ 60%, deadline ≤ 3 days
    """
    gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
    api_key = os.getenv("ZAKUPAI_API_KEY", "changeme")

    if not api_key or api_key == "changeme":
        logger.error("ZAKUPAI_API_KEY not configured")
        return 0

    try:
        client = ZakupaiHTTPClient(gateway_url, api_key)
        pipeline = LotPipeline(client)

        # Find hot lots
        hot_lots_result = await pipeline.find_hot_lots()

        if not hot_lots_result or "lots" not in hot_lots_result:
            logger.info("No hot lots found from API")
            return 0

        lots = hot_lots_result["lots"]
        saved_count = 0

        for lot_data in lots:
            try:
                # Validate criteria locally
                margin = lot_data.get("margin", 0)
                risk_score = lot_data.get("risk_score", 0)
                deadline_str = lot_data.get("deadline")

                if not deadline_str:
                    continue

                # Parse deadline
                try:
                    deadline = datetime.fromisoformat(
                        deadline_str.replace("Z", "+00:00")
                    )
                    days_until_deadline = (deadline - datetime.now()).days
                except:
                    continue

                # Apply criteria
                if (
                    margin >= 15.0
                    and risk_score >= 60.0
                    and days_until_deadline <= 3
                    and days_until_deadline > 0
                ):
                    # Save to database
                    saved = await save_hot_lot(
                        {
                            "lot_id": lot_data.get(
                                "id", str(lot_data.get("lot_id", ""))
                            ),
                            "title": lot_data.get("title", ""),
                            "price": lot_data.get("price", 0),
                            "margin": margin,
                            "risk_score": risk_score,
                            "deadline": deadline,
                            "customer": lot_data.get("customer", ""),
                        }
                    )

                    if saved:
                        saved_count += 1
                        logger.info(
                            f"Saved hot lot: {lot_data.get('id')} (margin={margin:.1f}%, risk={risk_score:.1f}%)"
                        )

            except Exception as e:
                logger.error(
                    f"Failed to process lot {lot_data.get('id', 'unknown')}: {e}"
                )

        logger.info(
            f"Hot lots cron: found {len(lots)} lots, saved {saved_count} hot lots"
        )
        return saved_count

    except Exception as e:
        logger.error(f"Hot lots search failed: {e}")
        return 0


async def run_cron():
    """Main cron runner"""
    logger.info("Starting hot lots cron job")

    try:
        await init_db()

        # Find and save hot lots
        saved_count = await find_and_save_hot_lots()

        # Send notifications if we have new hot lots
        if saved_count > 0:
            await run_notification_cron()
        else:
            logger.info("No new hot lots to notify about")

        await close_db()

        logger.info(f"Hot lots cron completed successfully (saved: {saved_count})")

    except Exception as e:
        logger.error(f"Hot lots cron failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Add timeout to prevent hanging
    try:
        asyncio.run(asyncio.wait_for(run_cron(), timeout=300))  # 5 minute timeout
    except TimeoutError:
        logger.error("Cron job timed out after 5 minutes")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Cron job interrupted")
        sys.exit(0)
