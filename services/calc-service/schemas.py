"""
Pydantic schemas for calc-service input validation.
Stage 7 Phase 1: Security Quick Wins
"""

from pydantic import BaseModel, Field, field_validator
import re


class ProfitRequest(BaseModel):
    """Request schema for profit calculation with strict validation."""

    lot_id: int = Field(..., gt=0, description="Lot ID must be positive integer")
    supplier_id: int = Field(..., gt=0, description="Supplier ID must be positive integer")
    region: str = Field(..., max_length=50, min_length=1, description="Region name")

    @field_validator('region')
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate region contains only allowed characters."""
        if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9\s\-\_]+$', v):
            raise ValueError('Region contains invalid characters')
        return v.strip()


class RiskScoreRequest(BaseModel):
    """Request schema for risk score calculation with strict validation."""

    supplier_bin: str = Field(
        ...,
        pattern=r'^\d{12}$',
        description="Supplier BIN must be exactly 12 digits"
    )
    year: int = Field(
        ...,
        ge=2015,
        le=2030,
        description="Year must be between 2015 and 2030"
    )

    @field_validator('supplier_bin')
    @classmethod
    def validate_bin(cls, v: str) -> str:
        """Additional validation for BIN."""
        if not v.isdigit():
            raise ValueError('BIN must contain only digits')
        if len(v) != 12:
            raise ValueError('BIN must be exactly 12 digits')
        return v
