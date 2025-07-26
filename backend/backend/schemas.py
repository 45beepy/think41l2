from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal, List

class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    age: Optional[int] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    street_address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    traffic_source: Optional[str] = None
    created_at: Optional[datetime] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int

    class Config:
        from_attributes = True

class MessageBase(BaseModel):
    sender: Literal['user', 'ai']
    content: str

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    conversation_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class ConversationBase(BaseModel):
    user_id: int
    title: Optional[str] = None

class ConversationCreate(ConversationBase):
    pass

class Conversation(ConversationBase):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    messages: List[Message] = []

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    user_id: int
    message: str
    conversation_id: Optional[int] = None

class ChatResponse(BaseModel):
    conversation_id: int
    user_message: str
    ai_response: str
    message_id: int