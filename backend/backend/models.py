from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(255))
    last_name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    age = Column(Integer)
    gender = Column(String(1))
    state = Column(String(255))
    street_address = Column(String(255))
    postal_code = Column(String(50))
    city = Column(String(255))
    country = Column(String(255))
    latitude = Column(String(10,8))
    longitude = Column(String(11,8))
    traffic_source = Column(String(255))
    created_at = Column(DateTime)

    conversations = relationship("Conversation", back_populates="user")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime, nullable=True)
    title = Column(String(255), nullable=True)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    sender = Column(Enum('user', 'ai'), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=func.now())

    conversation = relationship("Conversation", back_populates="messages")