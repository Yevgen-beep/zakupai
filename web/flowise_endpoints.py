# =============================================================================
# Week 4.2: Flowise Endpoints for FastAPI Integration
# =============================================================================

import json
import time
import uuid
from datetime import datetime

import structlog
from fastapi import HTTPException
from fastapi.responses import Response

from flowise_week4_2 import (
    ComplaintRequest,
    ComplaintResponse,
    SupplierRequest,
    SupplierResponse,
    SupplierSource,
    generate_complaint_via_flowise_enhanced,
    generate_complaint_word,
    generate_enhanced_complaint_pdf,
    get_active_supplier_sources,
    get_lot_info_enhanced,
    search_suppliers_modular,
    store_complaint_in_db,
)

logger = structlog.get_logger()


def create_flowise_endpoints(app, SessionLocal, redis_client):
    """Create and register Week 4.2 Flowise endpoints"""

    # ---------- Week 4.2 Endpoints ----------
    @app.post("/api/complaint/{lot_id}", response_model=ComplaintResponse)
    async def generate_complaint(lot_id: int, request: ComplaintRequest):
        """
        Generate complaint document with enhanced features
        Week 4.2: Redis caching, Flowise integration, fallback, PDF/Word export
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())

        logger.info(
            "Complaint generation request",
            action="complaint_generate",
            request_id=request_id,
            lot_id=lot_id,
            reason=request.reason[:100],  # Truncate for logging
        )

        try:
            # Check Redis cache first
            cache_key = f"complaint:{lot_id}:{hash(request.reason) % 1000000}"

            try:
                cached_complaint = redis_client.get(cache_key)
                if cached_complaint:
                    cached_data = json.loads(cached_complaint)
                    latency_ms = int((time.time() - start_time) * 1000)

                    logger.info(
                        "Complaint cache hit",
                        action="complaint_generate",
                        request_id=request_id,
                        lot_id=lot_id,
                        source="cache",
                        latency_ms=latency_ms,
                    )

                    return ComplaintResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

            # Get lot information
            with SessionLocal() as db:
                lot_info = await get_lot_info_enhanced(lot_id, db)
                if not lot_info:
                    raise HTTPException(status_code=404, detail="Lot not found")

                # Generate complaint
                complaint_result = await generate_complaint_via_flowise_enhanced(
                    lot_id, lot_info, request.reason, request.date
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # Create response
                response = ComplaintResponse(
                    lot_id=lot_id,
                    complaint_text=complaint_result["text"],
                    reason=request.reason,
                    date=request.date,
                    source=complaint_result["source"],
                    generated_at=datetime.now().isoformat(),
                    formats_available=["pdf", "word"],
                )

                # Cache the result
                try:
                    COMPLAINT_CACHE_TTL = 24  # hours
                    redis_client.setex(
                        cache_key,
                        COMPLAINT_CACHE_TTL * 3600,
                        json.dumps(response.dict()),
                    )
                except Exception as e:
                    logger.warning(f"Cache write error: {e}")

                # Store in database
                try:
                    await store_complaint_in_db(
                        lot_id,
                        request.reason,
                        request.date,
                        response.complaint_text,
                        response.source,
                        db,
                    )
                except Exception as e:
                    logger.warning(f"Database storage error: {e}")

                logger.info(
                    "Complaint generated",
                    action="complaint_generate",
                    request_id=request_id,
                    lot_id=lot_id,
                    source=response.source,
                    latency_ms=latency_ms,
                )

                return response

        except HTTPException:
            raise
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Complaint generation error",
                action="complaint_generate",
                request_id=request_id,
                lot_id=lot_id,
                error=str(e),
                latency_ms=latency_ms,
            )
            raise HTTPException(
                status_code=500, detail="Failed to generate complaint"
            ) from e

    @app.get("/api/complaint/{lot_id}/pdf")
    async def download_complaint_pdf(lot_id: int, reason: str, date: str):
        """
        Download complaint as PDF with enhanced formatting
        Week 4.2: ZakupAI logo, proper fonts, 1cm margins
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())

        try:
            # Get cached complaint or generate new one
            complaint_request = ComplaintRequest(reason=reason, date=date)
            complaint_response = await generate_complaint(lot_id, complaint_request)

            # Generate enhanced PDF
            pdf_buffer = generate_enhanced_complaint_pdf(
                complaint_response.complaint_text, lot_id, reason, date
            )

            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "PDF generated",
                action="complaint_generate",
                lot_id=lot_id,
                format="pdf",
                latency_ms=latency_ms,
                request_id=request_id,
            )

            return Response(
                content=pdf_buffer.getvalue(),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=complaint_{lot_id}_{date.replace('-', '')}.pdf"
                },
            )

        except Exception as e:
            logger.error(
                "PDF generation error",
                action="complaint_generate",
                lot_id=lot_id,
                format="pdf",
                error=str(e),
                request_id=request_id,
            )
            raise HTTPException(status_code=500, detail="Failed to generate PDF") from e

    @app.get("/api/complaint/{lot_id}/word")
    async def download_complaint_word(lot_id: int, reason: str, date: str):
        """
        Download complaint as Word document
        Week 4.2: python-docx with proper formatting
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())

        try:
            # Get cached complaint or generate new one
            complaint_request = ComplaintRequest(reason=reason, date=date)
            complaint_response = await generate_complaint(lot_id, complaint_request)

            # Generate Word document
            word_buffer = generate_complaint_word(
                complaint_response.complaint_text, lot_id, reason, date
            )

            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Word document generated",
                action="complaint_generate",
                lot_id=lot_id,
                format="word",
                latency_ms=latency_ms,
                request_id=request_id,
            )

            return Response(
                content=word_buffer.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": f"attachment; filename=complaint_{lot_id}_{date.replace('-', '')}.docx"
                },
            )

        except Exception as e:
            logger.error(
                "Word generation error",
                action="complaint_generate",
                lot_id=lot_id,
                format="word",
                error=str(e),
                request_id=request_id,
            )
            raise HTTPException(
                status_code=500, detail="Failed to generate Word document"
            ) from e

    @app.get("/api/supplier/{lot_name}", response_model=SupplierResponse)
    async def find_suppliers(
        lot_name: str,
        region: str | None = None,
        min_budget: float | None = None,
        max_budget: float | None = None,
        sources: str | None = None,
    ):
        """
        Find suppliers with modular sources
        Week 4.2: Satu.kz, 1688, Alibaba with rate limiting and fallbacks
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Parse sources from comma-separated string
        source_list = sources.split(",") if sources else None

        request = SupplierRequest(
            region=region,
            min_budget=min_budget,
            max_budget=max_budget,
            sources=source_list,
        )

        logger.info(
            "Supplier search request",
            action="supplier_search",
            request_id=request_id,
            lot_name=lot_name,
            region=request.region,
            sources=request.sources,
        )

        try:
            with SessionLocal() as db:
                # Get active supplier sources from database
                sources = await get_active_supplier_sources(request.sources, db)

                # Search suppliers using modular approach
                suppliers, cache_hit = await search_suppliers_modular(
                    lot_name, sources, request, redis_client
                )

            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Supplier search completed",
                action="supplier_search",
                request_id=request_id,
                lot_name=lot_name,
                suppliers_found=len(suppliers),
                sources_used=[s["name"] for s in sources],
                cache_hit=cache_hit,
                latency_ms=latency_ms,
            )

            return SupplierResponse(
                lot_name=lot_name,
                suppliers=suppliers,
                total_found=len(suppliers),
                sources_used=[s["name"] for s in sources],
                cache_hit=cache_hit,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Supplier search error",
                action="supplier_search",
                request_id=request_id,
                lot_name=lot_name,
                error=str(e),
                latency_ms=latency_ms,
            )
            raise HTTPException(
                status_code=500, detail="Failed to search suppliers"
            ) from e

    # ---------- Admin Endpoints for Supplier Sources ----------
    @app.get("/api/admin/sources", response_model=list[SupplierSource])
    async def get_supplier_sources():
        """Get all supplier source configurations"""
        try:
            with SessionLocal() as db:
                from sqlalchemy import text

                result = db.execute(
                    text("SELECT * FROM supplier_sources ORDER BY name")
                ).fetchall()

                return [
                    SupplierSource(
                        id=row.id,
                        name=row.name,
                        url_template=row.url_template,
                        parser_type=row.parser_type,
                        auth_type=row.auth_type,
                        credentials_ref=row.credentials_ref,
                        rate_limit=row.rate_limit,
                        fallback_type=row.fallback_type,
                        active=row.active,
                    )
                    for row in result
                ]
        except Exception as e:
            logger.error(f"Failed to get supplier sources: {e}")
            raise HTTPException(status_code=500, detail="Failed to get sources") from e

    @app.post("/api/admin/sources", response_model=SupplierSource)
    async def create_supplier_source(source: SupplierSource):
        """Create new supplier source configuration"""
        try:
            with SessionLocal() as db:
                from sqlalchemy import text

                result = db.execute(
                    text(
                        """
                        INSERT INTO supplier_sources
                        (name, url_template, parser_type, auth_type, credentials_ref, rate_limit, fallback_type, active)
                        VALUES (:name, :url_template, :parser_type, :auth_type, :credentials_ref, :rate_limit, :fallback_type, :active)
                        RETURNING *
                    """
                    ),
                    {
                        "name": source.name,
                        "url_template": source.url_template,
                        "parser_type": source.parser_type,
                        "auth_type": source.auth_type,
                        "credentials_ref": source.credentials_ref,
                        "rate_limit": source.rate_limit,
                        "fallback_type": source.fallback_type,
                        "active": source.active,
                    },
                )
                db.commit()
                row = result.fetchone()

                return SupplierSource(
                    id=row.id,
                    name=row.name,
                    url_template=row.url_template,
                    parser_type=row.parser_type,
                    auth_type=row.auth_type,
                    credentials_ref=row.credentials_ref,
                    rate_limit=row.rate_limit,
                    fallback_type=row.fallback_type,
                    active=row.active,
                )
        except Exception as e:
            logger.error(f"Failed to create supplier source: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to create source"
            ) from e

    return app
