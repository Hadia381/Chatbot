from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import bcrypt
from datetime import datetime

# SQLite Database URL
DATABASE_URL = "sqlite:///./chatbot.db"

# Create Engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a Local Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base Class for Models
Base = declarative_base()

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=True)
    location = Column(String, nullable=True)
    about = Column(String, nullable=True)
    products = Column(String, nullable=True)
    services = Column(String, nullable=True)
    links = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)  # ✅ Add this line
    chat_url = Column(String, nullable=True)
    secret_key = Column(String, nullable=True)

    logs = relationship("Log", back_populates="company", cascade="all, delete-orphan")


    
# User Model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

# ✅ Fix: Define Log Model AFTER Company
class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="logs")  # ✅ Fix applied
    queries = relationship("QueryLog", back_populates="log", cascade="all, delete-orphan")

# ✅ Fix: Define Query Log Model AFTER Log
class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer, ForeignKey("logs.id"), nullable=False)
    query_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    log = relationship("Log", back_populates="queries")

# ✅ Fix: Ensure all tables are created properly
Base.metadata.create_all(bind=engine)

# Function to hash passwords
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Insert Pre-Registered Users
def insert_users():
    db = SessionLocal()
    users = [
        {"email": "eman@gmail.com", "password": "password123"},
        {"email": "hadia@gmail.com", "password": "securepass"},
        {"email": "murtaza@ioptime.com", "password": "adminpass"},
    ]

    for user in users:
        existing_user = db.query(User).filter(User.email == user["email"]).first()
        if not existing_user:
            hashed_password = hash_password(user["password"])
            db_user = User(email=user["email"], password_hash=hashed_password)
            db.add(db_user)

    db.commit()
    db.close()
    print("✅ Users inserted successfully!")



