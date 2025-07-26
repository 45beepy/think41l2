from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import os
from dotenv import load_dotenv
import json

from . import models, schemas
from .database import engine, get_db

from groq import Groq
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

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

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the AI Conversational Agent API!"}

@app.get("/users/", response_model=List[schemas.User])
async def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

# --- NEW: Get all conversations for a user ---
@app.get("/users/{user_id}/conversations", response_model=List[schemas.Conversation])
async def get_user_conversations(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    conversations = db.query(models.Conversation).filter(models.Conversation.user_id == user_id).order_by(models.Conversation.start_time.desc()).all()
    return conversations

# --- NEW: Get messages for a specific conversation ---
@app.get("/conversations/{conversation_id}/messages", response_model=List[schemas.Message])
async def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    
    messages = db.query(models.Message).filter(models.Message.conversation_id == conversation_id).order_by(models.Message.timestamp).all()
    return messages


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
        {"role": "system", "content": (
            "You are an e-commerce AI assistant named Bolt. Your primary goal is to help users find products and get order statuses. "
            "Always be polite and conversational. Follow these steps:\n"
            "1. Analyze the user's message to determine their intent: 'product_search', 'order_status', or 'general_chat'.\n"
            "2. If 'product_search', extract the product name or category (e.g., 't-shirt', 'laptop', 'shoes').\n"
            "3. If 'order_status', extract the Order ID.\n"
            "4. If you need more information (e.g., product name for search, Order ID for status), ask clarifying questions.\n"
            "5. Based on intent and extracted entities, use the provided tools (e.g., get_product_details, get_order_details) to fetch data. "
            "   If a tool returns 'None' or empty data, inform the user you couldn't find it.\n"
            "6. Formulate a helpful response to the user based on the retrieved data or clarifying questions.\n"
            "7. Crucially, if you need to call a tool, respond ONLY with a JSON object like this:\n"
            "   ```json\n"
            "   {\n"
            "     \"tool_call\": {\n"
            "       \"function_name\": \"get_product_details\" | \"get_order_details\",\n"
            "       \"parameters\": {\"product_name\": \"value\"} | {\"order_id\": value, \"user_id\": value}\n"
            "     }\n"
            "   }\n"
            "   ```\n"
            "   If no tool call is needed, respond with natural language.\n"
            f"   The current user's first name is {user.first_name}. Today's date is {datetime.now().strftime('%Y-%m-%d')}."
        )}
    ]
    for msg in history_messages:
        llm_role = msg.sender
        if llm_role == "ai":
            llm_role = "assistant"
        messages_for_llm.append({"role": llm_role, "content": msg.content})

    messages_for_llm.append({"role": "user", "content": user_message_content})

    ai_response_content = "I'm sorry, I encountered an internal issue. Please try again later."

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=messages_for_llm,
            model="llama3-8b-8192",
            temperature=0.0,
            max_tokens=250,
        )
        llm_raw_response = chat_completion.choices[0].message.content

        try:
            parsed_response = json.loads(llm_raw_response)
            if "tool_call" in parsed_response:
                tool_call = parsed_response["tool_call"]
                function_name = tool_call["function_name"]
                parameters = tool_call["parameters"]
                
                tool_output = None
                if function_name == "get_product_details":
                    product_name = parameters.get("product_name")
                    product_id = parameters.get("product_id")
                    tool_output = get_product_details(db, product_name=product_name, product_id=product_id)
                elif function_name == "get_order_details":
                    order_id = parameters.get("order_id")
                    tool_output = get_order_details(db, order_id=order_id, user_id=user_id)
                
                messages_for_llm.append({"role": "tool", "content": json.dumps(tool_output)})
                
                final_chat_completion = groq_client.chat.completions.create(
                    messages=messages_for_llm,
                    model="llama3-8b-8192",
                    temperature=0.7,
                    max_tokens=250,
                )
                ai_response_content = final_chat_completion.choices[0].message.content

            else:
                ai_response_content = llm_raw_response

        except json.JSONDecodeError:
            ai_response_content = llm_raw_response
            
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