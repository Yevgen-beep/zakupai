import asyncio
import logging
import os
import random
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from typing import Any

import aiohttp
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# File handler with rotation
file_handler = RotatingFileHandler("etl.log", maxBytes=10 * 1024 * 1024, backupCount=5)
file_handler.setLevel(logging.DEBUG)

# Stream handler
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


class ETLService:
    def __init__(self):
        self.api_url = "https://ows.goszakup.gov.kz/v3/graphql"
        self.api_token = os.getenv("API_TOKEN")
        self.database_url = os.getenv("DATABASE_URL")

        if not self.api_token:
            raise ValueError("API_TOKEN not found in environment variables")
        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment variables")

        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def validate_dates(self, date_from: str, date_to: str) -> tuple[str, str]:
        """Validate and adjust dates with proper format and range checking"""
        try:
            # Parse input dates
            start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            end_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD: {e}") from e

        # Check minimum date
        min_date = datetime(2020, 1, 1).date()
        if start_date < min_date:
            raise ValueError(f"start_date cannot be earlier than {min_date}")

        # Ensure end_date doesn't exceed today
        today = datetime.utcnow().date()
        if end_date > today:
            end_date = today
            logger.info(f"Adjusted end_date to today: {end_date}")

        # Ensure start_date is not after end_date
        if start_date > end_date:
            start_date = end_date
            logger.info(f"Adjusted start_date to end_date: {start_date}")

        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def make_graphql_request(self, query: str) -> dict:
        """Make GraphQL request with retry logic - simplified to match CURL format"""
        if not self.session:
            raise ValueError("Session not initialized. Use async context manager.")

        payload = {"query": query}
        logger.debug(f"GraphQL Query: {query}")

        try:
            async with self.session.post(self.api_url, json=payload) as response:
                if response.status == 403:
                    logger.warning("Received 403 status, retrying...")
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=403,
                    )
                elif response.status == 429:
                    logger.warning("Rate limited, retrying...")
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=429,
                    )

                response.raise_for_status()
                result = await response.json()

                logger.debug(f"API Response: {result}")

                if "errors" in result:
                    logger.error(f"GraphQL errors: {result['errors']}")
                    raise Exception(f"GraphQL errors: {result['errors']}")

                await asyncio.sleep(1 + random.uniform(0, 0.5))  # nosec B311
                return result
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise

    async def fetch_lots(
        self, date_from: str, date_to: str, limit: int = 200
    ) -> tuple[list[dict], list[str]]:
        """Fetch lots exactly as in working CURL example"""
        lots = []
        errors = []

        logger.info(f"Starting Lots fetch for {date_from} to {date_to}")

        try:
            # Simple query like CURL - no pagination for now
            query = f"{{ Lots(limit:{limit}) {{ id nameRu amount lastUpdateDate }} }}"

            try:
                result = await self.make_graphql_request(query)

                if result.get("data", {}).get("Lots"):
                    batch = result["data"]["Lots"]
                    lots.extend(batch)
                    logger.info(f"Lots: fetched {len(batch)} records")

            except Exception as e:
                error_msg = f"Lots failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        except Exception as e:
            error_msg = f"Lots fetch failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        logger.info(f"Fetched {len(lots)} lots total")
        return lots, errors

    async def fetch_trdbuy(
        self, date_from: str, date_to: str, limit: int = 200
    ) -> tuple[list[dict], list[str]]:
        """Fetch TrdBuy exactly as in working CURL example"""
        trdbuy = []
        errors = []

        logger.info(f"Starting TrdBuy fetch for {date_from} to {date_to}")

        try:
            # Simple query like CURL - no pagination for now
            query = f'{{ TrdBuy(limit:{limit}, filter:{{publishDate:["{date_from}","{date_to}"]}}) {{ id nameRu totalSum publishDate endDate customerBin customerNameRu }} }}'

            try:
                result = await self.make_graphql_request(query)

                if result.get("data", {}).get("TrdBuy"):
                    batch = result["data"]["TrdBuy"]
                    trdbuy.extend(batch)
                    logger.info(f"TrdBuy: fetched {len(batch)} records")

            except Exception as e:
                error_msg = f"TrdBuy failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        except Exception as e:
            error_msg = f"TrdBuy fetch failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        logger.info(f"Fetched {len(trdbuy)} TrdBuy records total")
        return trdbuy, errors

    async def fetch_contracts(
        self, date_from: str, date_to: str, limit: int = 200
    ) -> tuple[list[dict], list[str]]:
        """Fetch Contract exactly as in working CURL example"""
        contracts = []
        errors = []

        logger.info(f"Starting Contract fetch for {date_from} to {date_to}")

        try:
            # Simple query like CURL - no pagination for now, remove supplierNameRu
            query = f'{{ Contract(limit:{limit}, filter:{{signDate:["{date_from}","{date_to}"]}}) {{ id contractNumber contractSum signDate supplierBiin }} }}'

            try:
                result = await self.make_graphql_request(query)

                if result.get("data", {}).get("Contract"):
                    batch = result["data"]["Contract"]
                    contracts.extend(batch)
                    logger.info(f"Contract: fetched {len(batch)} records")

            except Exception as e:
                error_msg = f"Contract failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        except Exception as e:
            error_msg = f"Contract fetch failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        logger.info(f"Fetched {len(contracts)} contracts total")
        return contracts, errors

    async def fetch_subjects(self, limit: int = 200) -> tuple[list[dict], list[str]]:
        """Fetch Subjects exactly as in working CURL example"""
        subjects = []
        errors = []

        logger.info("Starting Subjects fetch (all records)")

        try:
            # Simple query like CURL - no extensions
            query = f"{{ Subjects(limit:{limit}) {{ pid bin nameRu }} }}"

            try:
                result = await self.make_graphql_request(query)

                if result.get("data", {}).get("Subjects"):
                    batch = result["data"]["Subjects"]
                    subjects.extend(batch)
                    logger.info(f"Subjects: fetched {len(batch)} records")

            except Exception as e:
                error_msg = f"Subjects failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        except Exception as e:
            error_msg = f"Subjects fetch failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        logger.info(f"Fetched {len(subjects)} subjects total")
        return subjects, errors

    async def fetch_rnu(self, limit: int = 200) -> tuple[list[dict], list[str]]:
        """Fetch Rnu exactly as in working CURL example"""
        rnu = []
        errors = []

        logger.info("Starting RNU fetch (all records)")

        try:
            # Simple query like CURL - no extensions
            query = f"{{ Rnu(limit:{limit}) {{ id supplierBiin supplierNameRu startDate endDate }} }}"

            try:
                result = await self.make_graphql_request(query)

                if result.get("data", {}).get("Rnu"):
                    batch = result["data"]["Rnu"]
                    rnu.extend(batch)
                    logger.info(f"RNU: fetched {len(batch)} records")

            except Exception as e:
                error_msg = f"RNU failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        except Exception as e:
            error_msg = f"RNU fetch failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        logger.info(f"Fetched {len(rnu)} RNU records total")
        return rnu, errors

    def bulk_insert_to_postgres(
        self, table_name: str, data: list[dict], conflict_columns: list[str] = None
    ):
        """Insert data to PostgreSQL with ON CONFLICT DO NOTHING"""
        if not data:
            logger.info(f"No data to insert into {table_name}")
            return

        # Clean data - remove extensions field if present and convert keys to lowercase
        clean_data = []
        for record in data:
            clean_record = {}
            for k, v in record.items():
                if k != "extensions":
                    # Convert field names to lowercase for PostgreSQL compatibility
                    clean_record[k.lower()] = v
            clean_data.append(clean_record)

        conn = psycopg2.connect(self.database_url)
        try:
            cur = conn.cursor()

            # Get column names from first record
            columns = list(clean_data[0].keys())

            # Create table if it doesn't exist
            self._create_table_if_not_exists(cur, table_name, columns, clean_data[0])

            # Prepare values
            values = []
            for record in clean_data:
                values.append(tuple(record.get(col) for col in columns))

            # Insert query with ON CONFLICT DO NOTHING
            columns_str = ", ".join(columns)

            if conflict_columns:
                conflict_str = ", ".join(conflict_columns)
                query = f"""
                    INSERT INTO {table_name} ({columns_str})
                    VALUES %s
                    ON CONFLICT ({conflict_str}) DO NOTHING
                """  # nosec B608
            else:
                query = f"""
                    INSERT INTO {table_name} ({columns_str})
                    VALUES %s
                    ON CONFLICT DO NOTHING
                """  # nosec B608

            # Execute batch insert with execute_values
            psycopg2.extras.execute_values(cur, query, values)

            # Create indexes if they don't exist
            self._create_indexes(cur, table_name, columns)

            conn.commit()
            logger.info(
                f"Successfully inserted {len(clean_data)} records into {table_name}"
            )

        except Exception as e:
            conn.rollback()
            logger.error(f"Error inserting data into {table_name}: {e}")
            # Don't raise - save partial data
        finally:
            conn.close()

    def _create_table_if_not_exists(
        self, cur, table_name: str, columns: list[str], sample_data: dict
    ):
        """Create table if it doesn't exist with proper schema"""
        table_schemas = {
            "lots": """
                CREATE TABLE IF NOT EXISTS lots (
                    id BIGINT PRIMARY KEY,
                    nameRu TEXT,
                    amount NUMERIC,
                    lastUpdateDate TIMESTAMP
                )
            """,
            "trdbuy": """
                CREATE TABLE IF NOT EXISTS trdbuy (
                    id BIGINT PRIMARY KEY,
                    nameRu TEXT,
                    totalSum NUMERIC,
                    publishDate TIMESTAMP,
                    endDate TIMESTAMP,
                    customerBin VARCHAR(12),
                    customerNameRu TEXT
                )
            """,
            "contracts": """
                CREATE TABLE IF NOT EXISTS contracts (
                    id BIGINT PRIMARY KEY,
                    contractNumber VARCHAR(100),
                    contractSum NUMERIC,
                    signDate TIMESTAMP,
                    supplierBiin VARCHAR(12)
                )
            """,
            "subjects": """
                CREATE TABLE IF NOT EXISTS subjects (
                    pid BIGINT PRIMARY KEY,
                    bin VARCHAR(12) UNIQUE,
                    nameRu TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "rnu": """
                CREATE TABLE IF NOT EXISTS rnu (
                    id BIGINT PRIMARY KEY,
                    supplierBiin VARCHAR(12),
                    supplierNameRu TEXT,
                    startDate TIMESTAMP,
                    endDate TIMESTAMP
                )
            """,
        }

        if table_name in table_schemas:
            cur.execute(table_schemas[table_name])
        else:
            # Fallback to dynamic table creation
            columns_def = []
            for col in columns:
                value = sample_data[col]
                if col in ["id", "pid"]:
                    columns_def.append(f"{col} BIGINT")
                elif isinstance(value, int):
                    columns_def.append(f"{col} BIGINT")
                elif isinstance(value, float):
                    columns_def.append(f"{col} NUMERIC")
                elif isinstance(value, bool):
                    columns_def.append(f"{col} BOOLEAN")
                else:
                    columns_def.append(f"{col} TEXT")

            query = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    {", ".join(columns_def)}
                )
            """  # nosec B608
            cur.execute(query)

    def _create_indexes(self, cur, table_name: str, columns: list[str]):
        """Create indexes on important columns"""
        index_columns = ["bin", "id", "pid", "supplierBiin", "customerBin"]
        for col in index_columns:
            if col in columns:
                try:
                    index_name = f"idx_{table_name}_{col}"
                    query = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({col})"  # nosec B608
                    cur.execute(query)
                except Exception as e:
                    logger.warning(f"Could not create index on {table_name}.{col}: {e}")

    async def run_etl(self, days: int = 7, test_limit: int = 3) -> dict[str, Any]:
        """Run ETL process with exact CURL query format"""
        start_time = time.time()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        errors = []
        records = {}

        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            date_from = start_date.strftime("%Y-%m-%d")
            date_to = end_date.strftime("%Y-%m-%d")

            logger.info(f"Starting ETL for date range: {date_from} to {date_to}")
            logger.info(f"Using limit: {test_limit}")

            # Fetch dated data sequentially to avoid overwhelming API
            logger.info("Fetching Lots...")
            lots_data, lots_errors = await self.fetch_lots(
                date_from, date_to, test_limit
            )
            errors.extend(lots_errors)
            if lots_data:
                self.bulk_insert_to_postgres("lots", lots_data, ["id"])
            records["lots"] = len(lots_data)

            logger.info("Fetching TrdBuy...")
            trdbuy_data, trdbuy_errors = await self.fetch_trdbuy(
                date_from, date_to, test_limit
            )
            errors.extend(trdbuy_errors)
            if trdbuy_data:
                self.bulk_insert_to_postgres("trdbuy", trdbuy_data, ["id"])
            records["trdbuy"] = len(trdbuy_data)

            logger.info("Fetching Contracts...")
            contracts_data, contracts_errors = await self.fetch_contracts(
                date_from, date_to, test_limit
            )
            errors.extend(contracts_errors)
            if contracts_data:
                self.bulk_insert_to_postgres("contracts", contracts_data, ["id"])
            records["contracts"] = len(contracts_data)

            logger.info("Fetching Subjects...")
            subjects_data, subjects_errors = await self.fetch_subjects(test_limit)
            errors.extend(subjects_errors)
            if subjects_data:
                self.bulk_insert_to_postgres("subjects", subjects_data, ["pid"])
            records["subjects"] = len(subjects_data)

            logger.info("Fetching RNU...")
            rnu_data, rnu_errors = await self.fetch_rnu(test_limit)
            errors.extend(rnu_errors)
            if rnu_data:
                self.bulk_insert_to_postgres("rnu", rnu_data, ["id"])
            records["rnu"] = len(rnu_data)

            duration = time.time() - start_time

            # Determine final status
            if errors:
                status = "partial_success" if any(records.values()) else "error"
            else:
                status = "success"

            logger.info(
                f"ETL process completed in {duration:.2f}s with status: {status}"
            )

            return {
                "status": status,
                "records": records,
                "errors": errors,
                "timestamp": timestamp,
                "duration": f"{duration:.2f}s",
            }

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"ETL process failed: {e}")
            errors.append(f"ETL process failed: {e}")
            return {
                "status": "error",
                "records": records,
                "errors": errors,
                "timestamp": timestamp,
                "duration": f"{duration:.2f}s",
            }
