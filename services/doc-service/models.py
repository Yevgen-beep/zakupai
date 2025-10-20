"""
SQLAlchemy models for doc-service
"""

from sqlalchemy.ext.declarative import declarative_base

# Create the base class for all models
Base = declarative_base()

# TODO: Add actual model definitions here when implementing document service database tables
# Example:
# from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
# from sqlalchemy.dialects.postgresql import UUID
#
# class Document(Base):
#     __tablename__ = "documents"
#
#     id = Column(Integer, primary_key=True)
#     document_id = Column(UUID(as_uuid=True), nullable=False)
#     filename = Column(String(255), nullable=False)
#     content = Column(Text)
#     processed = Column(Boolean, default=False)
#     # ... other fields
