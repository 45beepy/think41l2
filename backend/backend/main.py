from fastapi import FastAPI, Depends, HTTPException
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

@app.get("/users/")
async def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users