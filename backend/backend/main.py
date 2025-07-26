from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import os
from dotenv import load_dotenv

from . import models, schemas
from .database import engine, get_db

from groq import Groq

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file or environment variables")

groq_client = Groq(api_key=GROQ_API_KEY)

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

def get_product_details(db: Session, product_name: str = None, product_id: int = None):
    query = db.query(models.Product)
    if product_id:
        product = query.filter(models.Product.id == product_id).first()
    elif product_name:
        product = query.filter(models.Product.name.ilike(f"%{product_name}%")).first()
    else:
        return None
    
    if product:
        return {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "brand": product.brand,
            "retail_price": float(product.retail_price),
            "department": product.department,
            "sku": product.sku
        }
    return None

def get_order_details(db: Session, order_id: int, user_id: int):
    order = db.query(models.Order).filter(models.Order.order_id == order_id, models.Order.user_id == user_id).first()
    if not order:
        return None

    order_items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).all()
    
    items_summary = []
    for item in order_items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        product_name = product.name if product else "Unknown Product"
        items_summary.append({
            "product_name": product_name,
            "status": item.status,
            "sale_price": float(item.sale_price)
        })

    return {
        "order_id": order.order_id,
        "status": order.status,
        "num_of_item": order.num_of_item,
        "created_at": order.created_at,
        "items": items_summary
    }

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
        print(f"Created new conversation with ID: {conversation.id}")

    user_message = models.Message(
        conversation_id=conversation.id,
        sender="user",
        content=user_message_content,
        timestamp=datetime.now()
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    history_messages = db.query(models.Message).filter(
        models.Message.conversation_id == conversation.id
    ).order_by(models.Message.timestamp).all()

    messages_for_llm = [
        {"role": "system", "content": f"You are a helpful e-commerce AI assistant named Bolt. Your goal is to assist users with product or order-related queries based on provided data. If a user asks about an order, ask for the Order ID and confirm their user name or email. If they ask about a product, ask for specific details like name or category. If data is provided, use it. Today's date is {datetime.now().strftime('%Y-%m-%d')}."}
    ]
    for msg in history_messages:
        llm_role = msg.sender
        if llm_role == "ai":
            llm_role = "assistant"
        messages_for_llm.append({"role": llm_role, "content": msg.content})

    messages_for_llm.append({"role": "user", "content": user_message_content})

    ai_response_content = "I'm sorry, I'm having trouble understanding right now. Please try again later."

    try:
        
        if "product" in user_message_content.lower() and ("find" in user_message_content.lower() or "look for" in user_message_content.lower()):
            product_name_query = None
            if "t-shirt" in user_message_content.lower():
                product_name_query = "t-shirt"
            elif "cap" in user_message_content.lower():
                product_name_query = "cap"

            if product_name_query:
                product_data = get_product_details(db, product_name=product_name_query)
                if product_data:
                    messages_for_llm.append({"role": "system", "content": f"User asked about product '{product_name_query}'. Found product data: {product_data}"})
                else:
                    messages_for_llm.append({"role": "system", "content": f"User asked about product '{product_name_query}'. No product data found."})
            else:
                 messages_for_llm.append({"role": "system", "content": "User asked about product, but specific product name not clearly identified. Prompt user for more details."})

        if "order" in user_message_content.lower() and "status" in user_message_content.lower():
            import re
            order_id_match = re.search(r'order id (\d+)', user_message_content.lower())
            if not order_id_match:
                order_id_match = re.search(r'orderid (\d+)', user_message_content.lower())
            
            order_id = int(order_id_match.group(1)) if order_id_match else None

            if order_id:
                order_data = get_order_details(db, order_id=order_id, user_id=user_id)
                if order_data:
                    messages_for_llm.append({"role": "system", "content": f"User asked about order ID {order_id}. Found order data: {order_data}"})
                else:
                    messages_for_llm.append({"role": "system", "content": f"User asked about order ID {order_id}. No order data found for user {user_id}."})
            else:
                messages_for_llm.append({"role": "system", "content": "User asked about order status, but order ID not clearly identified. Prompt user for order ID."})


        chat_completion = groq_client.chat.completions.create(
            messages=messages_for_llm,
            model="llama3-8b-8192",
            temperature=0.7,
            max_tokens=250,
        )
        ai_response_content = chat_completion.choices[0].message.content

    except Exception as e:
        print(f"Error during LLM call or data retrieval: {e}")
        ai_response_content = "I'm sorry, I encountered an internal issue. Please try again later."

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