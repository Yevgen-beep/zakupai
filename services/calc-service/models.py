"""
SQLAlchemy models for calc-service
"""

from sqlalchemy.ext.declarative import declarative_base

# Create the base class for all models
Base = declarative_base()

# TODO: Add actual model definitions here when implementing calculation database tables
# Example:
# from sqlalchemy import Column, Integer, String, DateTime, Numeric
# from sqlalchemy.dialects.postgresql import UUID
#
# class CalculationResult(Base):
#     __tablename__ = "calculation_results"
#
#     id = Column(Integer, primary_key=True)
#     request_id = Column(UUID(as_uuid=True), nullable=False)
#     result = Column(Numeric(18, 8), nullable=False)
#     # ... other fields
