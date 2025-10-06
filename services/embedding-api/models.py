"""
SQLAlchemy models for embedding-api
"""

from sqlalchemy.ext.declarative import declarative_base

# Create the base class for all models
Base = declarative_base()

# TODO: Add actual model definitions here when implementing embedding API database tables
# Example:
# from sqlalchemy import Column, Integer, String, DateTime, Text
# from sqlalchemy.dialects.postgresql import UUID, ARRAY
#
# class Embedding(Base):
#     __tablename__ = "embeddings"
#
#     id = Column(Integer, primary_key=True)
#     content_hash = Column(String(64), nullable=False, unique=True)
#     content = Column(Text, nullable=False)
#     embedding_vector = Column(ARRAY(Float))
#     # ... other fields
