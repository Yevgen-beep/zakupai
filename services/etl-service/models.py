from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ETLBatchUpload(Base):
    """SQLAlchemy model for batch uploaded transaction data"""

    __tablename__ = "etl_batch_uploads"

    id = Column(Integer, primary_key=True)
    bin = Column(String(12), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    batch_id = Column(UUID(as_uuid=True), nullable=False)


class BatchUploadRow(BaseModel):
    """Pydantic model for validating individual CSV/Excel rows"""

    bin: str = Field(..., description="Business Identification Number")
    amount: float = Field(..., ge=0, description="Transaction amount")
    status: str = Field(..., description="Transaction status")

    @validator("bin")
    def validate_bin(cls, v):
        if not v or not v.isdigit() or len(v) != 12:
            raise ValueError("BIN must be exactly 12 digits")
        return v

    @validator("status")
    def validate_status(cls, v):
        allowed_statuses = {"NEW", "APPROVED", "REJECTED"}
        if v.upper() not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v.upper()


class BatchUploadError(BaseModel):
    """Error information for failed row validation"""

    row: int = Field(..., description="Row number (1-based)")
    error: str = Field(..., description="Error message")


class BatchUploadRequest(BaseModel):
    """Request model for batch upload endpoint"""

    pass  # File will be handled via UploadFile


class BatchUploadResponse(BaseModel):
    """Response model for batch upload endpoint"""

    success: bool = Field(..., description="Whether the upload was successful")
    batch_id: str = Field(..., description="UUID of the batch upload")
    rows_processed: int = Field(
        ..., description="Number of successfully processed rows"
    )
    errors: list[BatchUploadError] = Field(
        default=[], description="List of validation errors"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "batch_id": "550e8400-e29b-41d4-a716-446655440000",
                "rows_processed": 352,
                "errors": [
                    {"row": 5, "error": "Invalid BIN format"},
                    {"row": 23, "error": "Amount must be >= 0"},
                ],
            }
        }
    }
