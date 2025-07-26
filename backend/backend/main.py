from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from . import models, schemas
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Conversational Agent Backend",
    description="Backend service for handling user conversations and product queries.",
    version="0.1.0",
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the AI Conversational Agent API!"}

@app.get("/users/", response_model=List[schemas.User])
async def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@app.post("/api/chat", response_model=schemas.ChatResponse, status_code=status.HTTP_200_OK)
async def chat_endpoint(request: schemas.ChatRequest, db: Session = Depends(get_db)):
    user_id = request.user_id
    user_message_content = request.message
    conversation_id = request.conversation_id

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    conversation = None
    if conversation_id:
        conversation = db.query(models.Conversation).filter(models.Conversation.id == conversation_id, models.Conversation.user_id == user_id).first()
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found for this user")
    else:
        conversation = models.Conversation(user_id=user_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    user_message = models.Message(
        conversation_id=conversation.id,
        sender="user",
        content=user_message_content,
        timestamp=datetime.now()
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    ai_response_content = f"Echo: {user_message_content}"
    if user_message_content.lower() == "hi":
        ai_response_content = f"Hello {user.first_name}! How can I assist you with your e-commerce needs today?"
    elif "product" in user_message_content.lower():
         ai_response_content = "I can help you find products. What kind of product are you looking for?"
    elif "order" in user_message_content.lower():
        ai_response_content = "I can help with orders. Please provide your order ID."

    ai_message = models.Message(
        conversation_id=conversation.id,
        sender="ai",
        content=ai_response_content,
        timestamp=datetime.now()
    )
    db.add(ai_message)
    db.commit()
    db.refresh(ai_message)

    return schemas.ChatResponse(
        conversation_id=conversation.id,
        user_message=user_message_content,
        ai_response=ai_response_content,
        message_id=ai_message.id
    )