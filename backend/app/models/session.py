from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from app.db.session import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    summary = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_seconds = Column(Integer, nullable=False, default=0)
    workspace = Column(String, nullable=False, index=True)
    files = Column(Text, nullable=True)  # JSON-encoded list of file paths
    pending_work = Column(Text, nullable=True)
    decisions = Column(Text, nullable=True)

    events = relationship(
        "Event", back_populates="session", cascade="all, delete-orphan"
    )
