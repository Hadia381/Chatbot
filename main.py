# Standard Library Imports
import os
import ast
import json
import random
from pathlib import Path
from datetime import datetime
from typing import List

# Third-Party Libraries
import requests
import bcrypt
import pytz
from dotenv import load_dotenv

# FastAPI Imports
from fastapi import FastAPI, Form, Header, Depends, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Pydantic
from pydantic import BaseModel, Field

# SQLAlchemy
from sqlalchemy.orm import Session
from sqlalchemy import func

# Local Imports
from database import SessionLocal, User, Company, Log, QueryLog
from jwt_utilities import create_access_token, verify_access_token

# LangChain
from langchain.chat_models import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.document_loaders import UnstructuredURLLoader, JSONLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

# OpenAI
from openai import ChatCompletion, OpenAIError

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (change in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Token verification
def verify_token(authorization: str):
    if not authorization:
        return JSONResponse(
            content={"success": False, "status": 401, "message": "Authentication token is missing"},
            status_code=401
        )

    token_parts = authorization.split()
    if len(token_parts) != 2 or token_parts[0].lower() != "bearer":
        return JSONResponse(
            content={"success": False, "status": 401, "message": "Invalid token format"},
            status_code=401
        )

    user_id = verify_access_token(token_parts[1])
    
    if user_id is None:
        return JSONResponse(
            content={"success": False, "status": 401, "message": "Invalid or expired token"},
            status_code=401
        )

    return user_id


# Password verification
def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# Login API
@app.post("/login")
def login_user(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user or not verify_password(password, db_user.password_hash):
        return JSONResponse(
            content={"success": False, "status": 401, "message": "Invalid Email or Password"},
            status_code=401
        )

    token = create_access_token({"sub": str(db_user.id)})
    return JSONResponse(
        content={"success": True, "status": 200, "message": "Login successful", "token": token, "user": {"id": db_user.id, "email": db_user.email}}
    )



def generate_secret_key():
    """Generate a 14-digit random secret key."""
    return ''.join(str(random.randint(0, 9)) for _ in range(14))

class VerificationRequest(BaseModel):
    companyName: str
    secretKey: str

@app.post("/add-company-details/")
def add_company_details(
    companyName: str = Form(...),
    companyType: str = Form(None),
    companyLinks: str = Form(None),
    companyLocation: str = Form(None),
    companyAbout: str = Form(None),
    companyProducts: str = Form(None),
    companyServices: str = Form(None),
    logoUrl: str = Form(None),  # ✅ Add logo URL input
    chat_Url: str = Form(None),
    secretKey: str = Form(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    # Token validation
    user_id = verify_token(authorization)
    if isinstance(user_id, JSONResponse):
        return user_id

    # Case-insensitive check for existing company
    existing_company = db.query(Company).filter(func.lower(Company.name) == companyName.lower()).first()
    if existing_company:
        return JSONResponse(
            content={"success": False, "status": 400, "message": f"Company {companyName} already exists"},
            status_code=400
        )

    # Add new company
    db_company = Company(
        name=companyName,
        type=companyType,
        links=companyLinks,
        location=companyLocation,
        about=companyAbout,
        products=companyProducts,
        services=companyServices,
        logo_url=logoUrl,               # ✅ Set logo
        secret_key=secretKey,
        chat_url=chat_Url
    )
    db.add(db_company)
    db.commit()
    db.refresh(db_company)

    return JSONResponse(
        content={"success": True, "status": 200, "message": f"Company {db_company.name} added successfully", "data": {
            "id": db_company.id,
            "name": db_company.name,
            "type": db_company.type,
            "location": db_company.location,
            "about": db_company.about,
            "products": db_company.products,
            "services": db_company.services,
            "links": db_company.links,
            "logo_url": db_company.logo_url,       # ✅ Include in response
            "chat_Url": db_company.chat_url,
            "secret_key": db_company.secret_key
        }}
    )


@app.post("/edit-company-details/{id}")
def edit_company_details(
    id: int,
    companyName: str = Form(None),
    companyType: str = Form(None),
    companyLocation: str = Form(None),
    companyAbout: str = Form(None),
    companyProducts: str = Form(None),
    companyServices: str = Form(None),
    companyLinks: str = Form(None),
    logoUrl: str = Form(None),               # ✅ Add logo input
    chat_Url: str = Form(None),
    secretKey: str = Form(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    # Token validation
    user_id = verify_token(authorization)
    if isinstance(user_id, JSONResponse):
        return user_id

    # Fetch company details
    db_company = db.query(Company).filter(Company.id == id).first()
    if not db_company:
        return JSONResponse(
            content={"success": False, "status": 404, "message": "Company not found"},
            status_code=404
        )

    # Update only provided fields
    if companyName:
        db_company.name = companyName
    if companyType:
        db_company.type = companyType
    if companyLocation:
        db_company.location = companyLocation
    if companyAbout:
        db_company.about = companyAbout
    if companyProducts:
        db_company.products = companyProducts
    if companyServices:
        db_company.services = companyServices
    if companyLinks:
        db_company.links = companyLinks
    if logoUrl:
        db_company.logo_url = logoUrl                 # ✅ Update logo
    if chat_Url:
        db_company.chat_url = chat_Url
    if secretKey:
        db_company.secret_key = secretKey

    db.commit()
    db.refresh(db_company)

    return JSONResponse(
        content={"success": True, "status": 200, "message": f"Company {db_company.name} updated successfully", "data": {
            "id": db_company.id,
            "name": db_company.name,
            "type": db_company.type,
            "location": db_company.location,
            "about": db_company.about,
            "products": db_company.products,
            "services": db_company.services,
            "links": db_company.links,
            "logo_url": db_company.logo_url,       # ✅ Include in response
            "chat_url": db_company.chat_url,
            "secret_key": db_company.secret_key
        }}
    )

# ✅ Get All Companies API
@app.get("/all-companies")
def get_all_companies(db: Session = Depends(get_db), authorization: str = Header(None)):
    user_id = verify_token(authorization)
    if isinstance(user_id, JSONResponse):
        return user_id

    companies = db.query(Company.id, Company.name).all()
    return JSONResponse(
        content={"success": True, "status": 200, "message": "Companies retrieved", 
                 "companies": [{"id": c.id, "name": c.name} for c in companies]}
    )

@app.get("/get-single-company-details/{id}")
def get_single_company_details(
    id: int,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    user_id = verify_token(authorization)
    if isinstance(user_id, JSONResponse):
        return user_id

    db_company = db.query(Company).filter(Company.id == id).first()
    if not db_company:
        return JSONResponse(
            content={"success": False, "status": 404, "message": f"Company with ID '{id}' not found"},
            status_code=404
        )

    return JSONResponse(
        content={
            "success": True,
            "status": 200,
            "message": "Company details retrieved",
            "data": {
                "id": db_company.id,
                "name": db_company.name,
                "type": db_company.type,
                "location": db_company.location,
                "about": db_company.about,
                "products": db_company.products,
                "services": db_company.services,
                "links": db_company.links,
                "logo_url": db_company.logo_url,  # ✅ Include logo URL
                "chatUrl": db_company.chat_url,
                "secretKey": db_company.secret_key
            }
        }
    )

# ✅ Delete Company API
@app.delete("/delete-company-details/{id}")
def delete_company_details(id: int, db: Session = Depends(get_db), authorization: str = Header(None)):
    user_id = verify_token(authorization)
    if isinstance(user_id, JSONResponse):
        return user_id

    db_company = db.query(Company).filter(Company.id == id).first()
    if not db_company:
        return JSONResponse(
            content={"success": False, "status": 404, "message": f"Company with ID '{id}' not found"},
            status_code=404
        )

    db.delete(db_company)
    db.commit()

    return JSONResponse(
        content={"success": True, "status": 200, "message": f"Company '{db_company.name}' deleted successfully"}
    )

from fastapi import Form

@app.post("/initiate-chat/")
def initiate_chat(
    companyName: str = Form(...), 
    secretKey: str = Form(...), 
    db: Session = Depends(get_db)
):
    print(f"📌 Received Data: {{'companyName': companyName, 'secretKey': secretKey}}")  # Debugging

    company_name_cleaned = companyName.strip().lower()
    secret_key_cleaned = secretKey.strip()

    company = db.query(Company).filter(
        Company.name.ilike(company_name_cleaned),  
        Company.secret_key == secret_key_cleaned
    ).first()

    if not company:
        return JSONResponse(content={"status": 401, "message": "Verification Unsuccessful. Kindly enter the correct secret key."}, status_code=401)

    # ✅ Store log entry with local time
    local_timezone = pytz.timezone("Asia/Karachi")
    local_time = datetime.now(local_timezone)

    log_entry = Log(
        company_id=company.id,
        entry_time=local_time
    )

    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    # ✅ Ensure valid URL is returned
    company_url = company.links if company.links and company.links.startswith("http") else None

    return JSONResponse(content={
        "message": "Verification successful",
        "status": 200,
        "companyName": company.name,
        "companyUrl": company_url,
        "logId": log_entry.id,
        "secret_key":company.secret_key
    })


from fastapi import Form

@app.post("/log-query/")
def log_query(
    log_id: str = Form(...),  # ✅ Ensure log_id is sent as a string in form data
    query_text: str = Form(...),
    response_text: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Stores chatbot query and response in both database and text file.
    """
    try:
        log_id = int(log_id)  # Convert back to integer

        print(f"📌 Received Data: log_id={log_id}, query_text={query_text}, response_text={response_text}")

        # ✅ Fetch log entry
        log_entry = db.query(Log).filter(Log.id == log_id).first()
        if not log_entry:
            print(f"❌ Invalid log ID: {log_id}")
            return JSONResponse({"message": "Invalid log ID", "status": 400})

        # ✅ Save query and response in database
        karachi_timezone = pytz.timezone('Asia/Karachi')
        query_log = QueryLog(
            log_id=log_entry.id,
            query_text=query_text,
            response_text=response_text,
            timestamp=datetime.now(karachi_timezone)
        )
        db.add(query_log)
        db.commit()

        print(f"✅ Query Logged: log_id={log_id}")

        # ✅ Append log to text file
        with open("chat_logs.txt", "a", encoding="utf-8") as f:
            f.write(f"Log ID: {log_id}\n")
            f.write(f"Query: {query_text}\n")
            f.write(f"Response: {response_text}\n")
            f.write(f"Time: {datetime.now(karachi_timezone)}\n")
            f.write("=" * 50 + "\n")

        return JSONResponse(content={"message": "Query logged successfully", "status": 200})

    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse(content={"message": "Internal server error", "status": 500})

from datetime import datetime
import pytz
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage, HumanMessage, AIMessage
@app.get("/get-logs/", response_model=dict)
def get_logs(authorization: str = Header(None), db: Session = Depends(get_db)):
    # Token validation
    user_id = verify_token(authorization)
    if isinstance(user_id, JSONResponse):
        return user_id  # Token is invalid

    karachi_timezone = pytz.timezone('Asia/Karachi')
    logs = db.query(Log).order_by(Log.entry_time.desc()).all()

    if not logs:
        raise HTTPException(status_code=404, detail="No logs found.")

    formatted_logs = []

    for log in logs:
        company = log.company
        company_name = company.name if company else "Unknown Company"
        log_entry_time = log.entry_time.astimezone(karachi_timezone).strftime("%m/%d/%Y at %I:%M:%S %p")

        # ✅ Add login action ONCE per log entry
        formatted_logs.append({
            "action": f'{company_name} logged in chat system at {log_entry_time}'
        })

        # ✅ Add queries (if any)
        for query_log in log.queries:
            query_time = query_log.timestamp.astimezone(karachi_timezone).strftime("%I:%M:%S %p")
            formatted_logs.append({
                "action": f'A query: "{query_log.query_text}" was asked at {log_entry_time} and was answered with "{query_log.response_text}" at {query_time}.'
            })

    return JSONResponse(content={
        "success": True,
        "status": 200,
        "message": "Logs Fetched Successfully",
        "logs": formatted_logs
    })


# Function to load saved documents
def load_saved_data(file_path="extracted_data.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as json_file:
            json_data = json.load(json_file)
        return [Document(page_content=value) for key, value in json_data.items()]
    except Exception as e:
        print(f"Error loading saved data: {e}")
        return []

# Split documents into chunks
def split_documents(documents):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
    return text_splitter.split_documents(documents)
# 🔒 In-memory chat memory store (per company)
chat_memory_store = {}
@app.post("/chat-with/")
def chat_with(
    query: str = Form(...),
    companyName: str = Form(...),
    db: Session = Depends(get_db)
):
    # ✅ Verify company
    company = db.query(Company).filter(Company.name.ilike(companyName)).first()
    if not company:
        return JSONResponse({
            "send_msg": query,
            "receive_msg": "You are not authorized to perform this function."
        }, status_code=403)

    # ✅ Create or get the log entry for the company
    log_entry = db.query(Log).filter(Log.company_id == company.id, Log.exit_time == None).first()
    if not log_entry:
        log_entry = Log(company_id=company.id, entry_time=datetime.utcnow())
        db.add(log_entry)
        db.commit()

    # ✅ Fetch chat history
    queries = db.query(QueryLog).filter(QueryLog.log_id == log_entry.id).all()
    chat_history = [(q.query_text.lower(), q.response_text) for q in queries]
    last_topic = None
    for q, r in reversed(chat_history):
        if "product" in q:
            last_topic = "products"
            break
        elif "service" in q:
            last_topic = "services"
            break

    # ✅ Prepare fields
    company_details = {
        "companyName": company.name or "Not Provided",
        "companyType": company.type or "Not Provided",
        "companyLocation": company.location or "Not Provided",
        "companyLinks": company.links or "Not Provided",
        "companyAbout": company.about or "Not Provided",
        "companyProducts": company.products or "Not Provided",
        "companyServices": company.services or "Not Provided",
    }

    lower_query = query.lower().strip()
    greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
    follow_ups = ["yes", "tell me more", "okay", "sure"]
    exits = ["bye", "exit", "thanks", "thank you"]

    # ✅ Handle greeting
    if lower_query in greetings and not chat_history:
        response = f"Hello! Welcome to {company_details['companyName']}. How can I assist you today?"

    # ✅ Handle follow-up like 'yes'
    elif lower_query in follow_ups:
        if last_topic == "products":
            response = f"Sure! Here's more detail about our products:\n{company_details['companyProducts']}"
        elif last_topic == "services":
            response = f"Absolutely! Here's more about our services:\n{company_details['companyServices']}"
        else:
            response = f"Can you please tell me what you'd like to know more about?"

    # ✅ Handle exit phrases
    elif lower_query in exits:
        response = "Thank you for chatting! Let me know if you need anything else."

    else:
        # ✅ Smart prompt
        prompt = f"""
You are a friendly and professional virtual assistant for {company_details['companyName']}. Keep your answer concise in 3,4 lines. Your goal is to assist users with inquiries in a polite, conversational manner using ONLY the following company information:

**Company Details:**
- Name: {company_details['companyName']}
- Type: {company_details['companyType']}
- Location: {company_details['companyLocation']}
- Links: {company_details['companyLinks']}
- About: {company_details['companyAbout']}
- Products: {company_details['companyProducts']}
- Services: {company_details['companyServices']}

**Response Guidelines:**
1. If the user greets you (e.g., "Hello", "Hi"), reply with a warm greeting: "Hello! Welcome to {company_details['companyName']}. How can I assist you today?"
2. For other queries, skip the "Welcome" message and directly respond with helpful information.
3. For product/service inquiries, provide a personalized response:
   - "We offer a variety of services, including {company_details['companyServices']}. Feel free to ask for more details about any of them!"
4. When answering about services, incorporate a friendly tone:
   - "At {company_details['companyName']}, we provide {company_details['companyServices']}, aimed to offer the best experience. Would you like more details on any of these services?"
5. For general inquiries, suggest relevant next steps:
   - "If you're looking for more information about our offerings, you can explore {company_details['companyLinks']}!"
6. Keep responses clear, concise, and engaging, using short sentences to maintain a friendly tone.
7. Avoid saying you're an AI; simply focus on assisting with the company's details.
8. When the query is outside your scope, redirect helpfully: "I can help with details about {company_details['companyName']}. Visit {company_details['companyLinks']} for more!"
9. If a user asks for products or services, share the categories or examples first. If they ask for more, provide detailed info.
"""

        messages = [SystemMessage(content=prompt)]
        for q, r in chat_history:
            messages.append(HumanMessage(content=q))
            messages.append(AIMessage(content=r))
        messages.append(HumanMessage(content=query))

        llm = ChatOpenAI(model="gpt-4-turbo")  # Cheaper & supports 128K tokens if needed

        ai_msg = llm(messages)
        response = ai_msg.content.strip()

    # ✅ Log the query and response
    if log_entry:
        try:
            response_json = {
                "send_msg": query,
                "receive_msg": response,
                "type": "text"
            }
            requests.post(
                "http://127.0.0.1:8000/log-query/",
                data={
                    "log_id": str(log_entry.id),
                    "query_text": query,
                    "response_text": response
                },
                timeout=10
            )
        except requests.exceptions.RequestException as e:
            print(f"Failed to log query: {e}")

    return JSONResponse(content=response_json)



