from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False)
    file_path = Column(Text, nullable=True)
    workspace = Column(Text, nullable=False)
    language = Column(String(50), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    metadata_ = Column("metadata", Text, nullable=True)  # JSON-encoded string to avoid SQLAlchemy metadata collision
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True)

    session = relationship("Session", back_populates="events")
