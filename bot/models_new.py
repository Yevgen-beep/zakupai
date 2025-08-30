from datetime import datetime

from pydantic import BaseModel, Field, validator
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class TgKey(Base):
    __tablename__ = "tg_keys"

    user_id = Column(BigInteger, primary_key=True)
    api_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index("idx_tg_keys_user_id", "user_id"),
        Index("idx_tg_keys_created_at", "created_at"),
    )


class HotLot(Base):
    __tablename__ = "hot_lots"

    id = Column(String, primary_key=True)
    title = Column(Text)
    price = Column(BigInteger)
    margin = Column(BigInteger)  # percentage * 100
    risk_score = Column(BigInteger)  # percentage * 100
    deadline = Column(DateTime)
    customer = Column(String)
    created_at = Column(DateTime, default=func.now())
    notified_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_hot_lots_deadline", "deadline"),
        Index("idx_hot_lots_margin", "margin"),
        Index("idx_hot_lots_risk", "risk_score"),
    )


# Pydantic models for validation


class LotRequest(BaseModel):
    lot_id: str = Field(..., min_length=1, max_length=20)

    @validator("lot_id")
    def validate_lot_id(cls, v):
        if not v.isdigit():
            raise ValueError("lot_id must be numeric")
        return v


class HotLotCriteria(BaseModel):
    margin_min: float = Field(15.0, ge=0, le=100)
    risk_score_min: float = Field(60.0, ge=0, le=100)
    deadline_days: int = Field(3, ge=1, le=30)
    limit: int = Field(20, ge=1, le=100)


class LotAnalysisResult(BaseModel):
    lot_id: str
    title: str | None = None
    price: int | None = None
    margin: float | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    deadline: datetime | None = None
    customer: str | None = None
    tldr: str | None = None
    errors: list[str] = Field(default_factory=list)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class NotificationMessage(BaseModel):
    lot_id: str
    title: str
    price: int
    margin: float
    risk_score: float
    deadline: datetime
    customer: str | None = None

    def to_markdown(self) -> str:
        """Convert to Telegram markdown format"""
        deadline_str = self.deadline.strftime("%d.%m.%Y %H:%M")
        price_formatted = f"{self.price:,.0f}"

        # Risk level emoji
        risk_emoji = (
            "🟢" if self.risk_score < 30 else "🟡" if self.risk_score < 70 else "🔴"
        )

        # Margin emoji
        margin_emoji = "💰" if self.margin >= 25 else "💵"

        return f"""🔥 **Горячий лот #{self.lot_id}**

📝 **{self.title}**

{margin_emoji} **Маржа:** {self.margin:.1f}%
{risk_emoji} **Риск:** {self.risk_score:.1f}%
💸 **Цена:** {price_formatted} тенге
⏰ **Дедлайн:** {deadline_str}
🏢 **Заказчик:** {self.customer or 'N/A'}

_Найден в {datetime.now().strftime("%H:%M")}_"""


class ApiKeyValidation(BaseModel):
    user_id: int = Field(..., gt=0)
    api_key: str = Field(..., min_length=10, max_length=200)

    @validator("api_key")
    def validate_api_key_format(cls, v):
        # Basic API key format validation
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Invalid API key format")
        return v


class UserStats(BaseModel):
    user_id: int
    registered_at: datetime
    last_updated: datetime
    is_active: bool
    total_requests: int = 0
    last_request_at: datetime | None = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
