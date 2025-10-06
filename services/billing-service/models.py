"""
SQLAlchemy models for billing-service
"""

from sqlalchemy.ext.declarative import declarative_base

# Create the base class for all models
Base = declarative_base()

# TODO: Add actual model definitions here when implementing billing database tables
# Example:
# from sqlalchemy import Column, Integer, String, DateTime, Numeric
# from sqlalchemy.dialects.postgresql import UUID
#
# class BillingRecord(Base):
#     __tablename__ = "billing_records"
#
#     id = Column(Integer, primary_key=True)
#     user_id = Column(UUID(as_uuid=True), nullable=False)
#     amount = Column(Numeric(10, 2), nullable=False)
#     # ... other fields
